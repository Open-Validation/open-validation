"""Stage A: give every English council a code, a folder and an _lpa.yaml.

Run:  python scripts/build_lpas.py            (match names, then build folders)
      python scripts/build_lpas.py --match-only

What it does, step by step:
  1. Reads the workbook sheet 'Councils reference' (England rows only).
  2. Matches each council name to MHCLG's organisation register
     (inputs/organisation/*.csv) and writes scripts/lpa_match.csv.
     Rows you edit by hand and mark match-method 'manual' are kept as they are.
     Anything it can't match confidently is printed and the script stops.
  3. Creates specification/planning-requirement/<CODE>/_lpa.yaml for every council
     (keeping any audit, review marks and contact details already there) and
     writes data/lpa.csv.

Stage B (build_from_workbook.py) then adds the audit and the requirement files.
"""

import argparse
import re
import sys
from datetime import date

import openpyxl

from common import DATA, INPUTS, SCRIPTS, SPEC, WORKBOOK, link_url, load_yaml, read_csv, \
    sheet_rows, write_csv, write_yaml

MATCH_FILE = SCRIPTS / "lpa_match.csv"
MATCH_COLUMNS = ["workbook-name", "code", "ons-code", "register-name", "organisation", "match-method"]

from review import LPA_COLUMNS  # the column list lives in review.py

# Words that don't help tell councils apart.
NOISE = r"\b(the|council|borough|district|metropolitan|county|city of|city|corporation|royal|" \
        r"london|of|unitary|authority|national park|bc|dc|mbc|cc)\b"


def normalise(name):
    """'Borough Council of King's Lynn & West Norfolk' -> 'kings lynn and west norfolk'."""
    n = name.lower().replace("&", " and ").replace("'", "").replace("’", "")
    n = re.sub(r"[^a-z ]", " ", n)
    n = re.sub(NOISE, " ", n)
    return re.sub(r"\s+", " ", n).strip()


# MHCLG's codes for national parks and development corporations are Wikidata
# ids (e.g. Q72617988), which aren't readable as folder names. We use the
# authorities' own short names instead. The Wikidata id is kept in the
# 'organisation' column of scripts/lpa_match.csv, so the data can still be
# matched back to MHCLG's register.
SHORT_CODES = {
    "Q4972284": "BROADS",    # Broads Authority
    "Q5225646": "DNPA",      # Dartmoor National Park Authority
    "Q72617784": "ENPA",     # Exmoor National Park Authority
    "Q27159704": "LDNPA",    # Lake District National Park Authority
    "Q72617158": "NFNPA",    # New Forest National Park Authority
    "Q72617669": "NYMNPA",   # North York Moors National Park Authority
    "Q72617890": "NNPA",     # Northumberland National Park Authority
    "Q72617988": "PDNPA",    # Peak District National Park Authority
    "Q20198711": "SDNPA",    # South Downs National Park Authority
    "Q27178932": "YDNPA",    # Yorkshire Dales National Park Authority
    "Q20648596": "OPDC",     # Old Oak and Park Royal Development Corporation
    "Q6670544": "LLDC",      # London Legacy Development Corporation
    "Q72463795": "EDC",      # Ebbsfleet Development Corporation
}


def register():
    """Current English LPAs from MHCLG's register: list of dicts with code, ons, name, org."""
    today = date.today().isoformat()
    rows = []
    org = INPUTS / "organisation"
    for r in read_csv(org / "local-authority.csv"):
        if r["end-date"] and r["end-date"] <= today:
            continue  # abolished council
        rows.append({"code": r["reference"], "ons": r["local-planning-authority"],
                     "name": r["name"], "org": r["organisation"]})
    for file, prefix in (("national-park-authority.csv", "national-park-authority"),
                         ("development-corporation.csv", "development-corporation")):
        for r in read_csv(org / file):
            if r["end-date"] or not r["local-planning-authority"]:
                continue
            rows.append({"code": SHORT_CODES.get(r["reference"], r["reference"]),
                         "ons": r["local-planning-authority"],
                         "name": r["name"], "org": f"{prefix}:{r['reference']}"})
    return rows


def england_councils():
    """England rows from 'Councils reference', as dicts keyed by header."""
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True)
    return [r for r in sheet_rows(wb["Councils reference"]) if r.get("Nation") == "England"], wb


def match(councils):
    """Match every workbook council to the register. Returns (rows, problems)."""
    kept = {r["workbook-name"]: r for r in read_csv(MATCH_FILE)} if MATCH_FILE.exists() else {}
    reg = register()
    by_exact = {r["name"].lower(): r for r in reg}
    by_norm = {}
    for r in reg:
        by_norm.setdefault(normalise(r["name"]), []).append(r)

    rows, problems = [], []
    for c in councils:
        name = c["Council"]
        if kept.get(name, {}).get("match-method") == "manual":
            rows.append(kept[name])
            continue
        hit, method = by_exact.get(name.lower()), "exact name"
        if not hit:
            cands = by_norm.get(normalise(name), [])
            if len(cands) == 1:
                hit, method = cands[0], "normalised name"
            elif len(cands) > 1:
                problems.append(f"{name}: several possible matches: " + ", ".join(x["name"] for x in cands))
        if not hit:
            problems.append(f"{name}: no match in MHCLG's register")
            rows.append({"workbook-name": name, "match-method": "UNMATCHED"})
            continue
        rows.append({"workbook-name": name, "code": hit["code"], "ons-code": hit["ons"],
                     "register-name": hit["name"], "organisation": hit["org"], "match-method": method})

    codes = [r.get("code") for r in rows if r.get("code")]
    for code in sorted({c for c in codes if codes.count(c) > 1}):
        problems.append(f"code {code} is matched to more than one council")
    return rows, problems


def joint_lists(wb):
    """From 'Mergers & shared services' section C: {council name: [partner names]}
    for partnerships whose list status is 'joint'."""
    out = {}
    section = None
    for row in wb["Mergers & shared services"].iter_rows(values_only=True):
        first = str(row[0] or "")
        if re.match(r"^[A-E]\. ", first):
            section = first[0]
            continue
        if section == "C" and row[1] and row[2] == "joint":
            members = [m.strip() for m in str(row[1]).split(";") if m.strip()]
            for m in members:
                out[m] = [x for x in members if x != m]
    return out


def list_status(status):
    """Workbook 'Status' -> current | not-found | national-only (outdated is set from the date)."""
    s = (status or "").lower()
    if s.startswith("national"):
        return "national-only"
    if s.startswith("not found"):
        return "not-found"
    return "current"


def build(councils, matches, wb):
    code_of = {m["workbook-name"]: m for m in matches}
    joint = joint_lists(wb)
    name_to_code = {m["workbook-name"]: m["code"] for m in matches}
    rows = []
    for c in councils:
        m = code_of[c["Council"]]
        code = m["code"]
        path = SPEC / code / "_lpa.yaml"
        old = load_yaml(path) if path.exists() else {}
        old_list = old.get("validation-list") or {}

        list_date = str(c.get("List date") or "")[:10]
        status = list_status(c.get("Status"))
        if status == "current" and c.get("Outdated (>2y)?") == "Yes":
            status = "outdated"

        lpa = {
            "local-authority": code,
            "name": m["register-name"],
            "region": c.get("Region") or "",
            "type": c.get("Type") or "",
            "review-status": old.get("review-status", "ai-collated"),
            # Stage B may replace the list with the audit's current one; keep it if so.
            "validation-list": old_list or {
                "url": link_url(c.get("Validation list URL")),
                "date": list_date,
                "date-basis": c.get("Date basis") or "",
                "status": status,
            },
            "submission-standards": old.get("submission-standards", []),
        }
        if old.get("contact"):
            lpa["contact"] = old["contact"]
        partners = [name_to_code[p] for p in joint.get(c["Council"], []) if p in name_to_code]
        if partners:
            lpa["joint-list"] = {"partners": partners}
        lpa["audit"] = old.get("audit") or {"status": "not-audited"}
        notes = [c.get("Notes") or ""]
        lpa["notes"] = old.get("notes") or " ".join(n for n in notes if n).strip()
        lpa["field-status"] = old.get("field-status", {})
        # Drop empty optional keys (FORMAT.md: leave out optional keys that are empty)
        for k in ("notes",):
            if not lpa[k]:
                del lpa[k]
        write_yaml(path, lpa)

        rows.append({
            "code": code, "ons-code": m["ons-code"], "name": lpa["name"], "region": lpa["region"],
            "type": lpa["type"], "validation-list-url": lpa["validation-list"].get("url", ""),
            "list-date": lpa["validation-list"].get("date", ""),
            "list-status": lpa["validation-list"].get("status", ""),
            "coverage": "", "review-status": lpa["review-status"],
            "audit-status": lpa["audit"].get("status", "not-audited"),
            "issues-open": lpa["audit"].get("issues-open", ""),
            "joint-list": "yes" if partners else "", "partners": ";".join(partners),
            "notes": "", "entry-date": date.today().isoformat(),
        })
    old_rows = {r["code"]: r for r in read_csv(DATA / "lpa.csv")} if (DATA / "lpa.csv").exists() else {}
    for r in rows:  # keep the first entry-date we ever wrote
        if r["code"] in old_rows and old_rows[r["code"]].get("entry-date"):
            r["entry-date"] = old_rows[r["code"]]["entry-date"]
    rows.sort(key=lambda r: r["code"])
    write_csv(DATA / "lpa.csv", rows, LPA_COLUMNS)
    print(f"Wrote {len(rows)} council folders and data/lpa.csv")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--match-only", action="store_true", help="only write scripts/lpa_match.csv")
    a = p.parse_args()

    councils, wb = england_councils()
    matches, problems = match(councils)
    write_csv(MATCH_FILE, sorted(matches, key=lambda r: (r["match-method"] != "UNMATCHED", r["workbook-name"])),
              MATCH_COLUMNS)
    print(f"{len(councils)} English councils in the workbook; matches written to scripts/lpa_match.csv")
    if problems:
        print("\nPlease check these by hand (edit scripts/lpa_match.csv, set match-method to 'manual'):")
        for p_ in problems:
            print("  -", p_)
        sys.exit(1)
    if not a.match_only:
        build(councils, matches, wb)
        print("Now run: python scripts/set_status.py --recompute")


if __name__ == "__main__":
    main()

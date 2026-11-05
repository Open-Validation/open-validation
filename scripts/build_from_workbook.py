"""Stage B: build every council's requirement files from the workbook + audit.

Run:
  python scripts/build_from_workbook.py --lpa CMD,SHR
  python scripts/build_from_workbook.py --region "London,South East"
  python scripts/build_from_workbook.py              (every council)
  add --dry-run to only print what would change

How it works, for each council:
  1. Workbook: collect its rows from the 18 application-type sheets. Map each
     requirement name to an MHCLG id (scripts/requirement_map.csv) and each sheet
     to application types (scripts/sheet_map.csv). One council + one requirement
     = one file, with the application types from every sheet it appears in.
     Names with no MHCLG id go to data/unmapped-requirement.csv.
  2. Audit: inputs/audit/<slug>.json says what's wrong with the workbook. The
     audit is prose, so a person (or Claude) turns it into a corrections file,
     scripts/audit_corrections/<CODE>.yaml (format in scripts/audit_corrections/README.md).
     This script applies it: drop rows, replace or add requirements, fix triggers,
     submission standards, a newer list link.
     Without a corrections file, files the audit seems to criticise are set to
     confidence: low, with the issue in their notes.
  3. The audit also fills _lpa.yaml: current list link and date, audit summary,
     issues open.
  4. Then data/local-planning-requirement.csv is rebuilt and every status recomputed.

Safe to re-run: a cell marked above 'unverified' is never changed.
"""

import argparse
import json
import re
from collections import OrderedDict, defaultdict
from datetime import date

import openpyxl

from common import AUDIT, DATA, SCRIPTS, SPEC, WORKBOOK, link_url, load_yaml, read_csv, \
    sheet_rows, write_csv, write_yaml
import review

CORRECTIONS = SCRIPTS / "audit_corrections"
TODAY = date.today().isoformat()
AUDIT_DATE = "2026-11-05"   # the audit was run on 4-5 November 2026
NATIONAL_ONLY_IDS = {"application-form", "location-plan"}   # skip unless a local trigger is added
PROTECTED = {"human-verified", "council-verified", "council-updated"}
ISSUE_TYPES_THAT_DOUBT = {"wrong_trigger", "wrong_app_type", "not_a_requirement", "duplicate", "other"}


# ---------- reading the inputs ----------

def load_maps():
    req_map = {r["workbook-name"]: r for r in read_csv(SCRIPTS / "requirement_map.csv")}
    sheet_map = OrderedDict((r["sheet"], r["application-type"].split(";"))
                            for r in read_csv(SCRIPTS / "sheet_map.csv"))
    return req_map, sheet_map


def tidy_text(text):
    """PDF tick and bullet glyphs come through as private-use characters; show them properly."""
    text = str(text or "").replace("", "✓").replace("", "•").replace("", "▪")
    return re.sub(r"[ \t]+", " ", text).strip()


def read_workbook(sheet_map, wanted_names):
    """{council name: [row dicts]} for the type sheets, plus {council name: tab items}."""
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True)
    rows = defaultdict(list)
    for sheet in sheet_map:
        for r in sheet_rows(wb[sheet]):
            if r["Council"] in wanted_names and r.get("Requirement") not in (None, "(none)"):
                r["sheet"] = sheet
                rows[r["Council"]].append(r)
    return rows


def audits():
    """{workbook council name: audit dict}."""
    out = {}
    for f in AUDIT.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["council"]] = d
    return out


# ---------- turning workbook rows into requirement files ----------

def collect(rows, req_map, sheet_map, code, dropped=()):
    """Group a council's workbook rows by MHCLG id. Returns ({id: info}, [unmapped rows]).
    'dropped' is a set of (id, sheet) pairs that a corrections file throws away."""
    by_id, unmapped = OrderedDict(), []
    for r in rows:
        m = req_map.get(r["Requirement"], {})
        ids = [i for i in (m.get("planning-requirement") or "").split(";") if i]
        url = link_url(r.get("Source document (link)"))
        excerpt = tidy_text(r.get("Trigger / when required (verbatim excerpt)"))
        if not ids:
            unmapped.append({"local-authority": code, "local-name": r["Requirement"], "source-text": excerpt,
                             "source-url": url, "suggested-id": m.get("suggested-id", ""),
                             "sheet": r["sheet"]})
            continue
        for i in ids:
            if (i, r["sheet"]) in dropped:
                by_id.setdefault(i, new_info())["dropped"].append(r["sheet"])
                continue
            info = by_id.setdefault(i, new_info())
            info["sheets"].append(r["sheet"])
            info["names"].add(r["Requirement"])
            for t in sheet_map[r["sheet"]]:
                if t not in info["types"]:
                    info["types"].append(t)
            if excerpt:
                info["excerpts"].setdefault(excerpt, []).append(r["sheet"])
            if url:
                info["urls"].append(url)
            if "INFERRED" in str(r.get("Notes") or ""):
                info["inferred"] = True
    return by_id, unmapped


def new_info():
    return {"types": [], "excerpts": OrderedDict(), "urls": [], "inferred": False,
            "sheets": [], "names": set(), "dropped": []}


def garbled(text):
    """Rough test for excerpts that ran into the next entry or are table debris."""
    return text.count("✓") >= 2 or len(text) < 25 or text.count("•") >= 3


def source_text(excerpts):
    """One excerpt as is; several are labelled with the sheet they came from."""
    if len(excerpts) == 1:
        return next(iter(excerpts))
    return "\n\n".join(f"{', '.join(dict.fromkeys(sheets))}: {text}" for text, sheets in excerpts.items())


def workbook_file(code, rid, info):
    """A requirement file built from workbook rows alone (before the audit)."""
    st = source_text(info["excerpts"])
    notes, confidence = [], "medium"
    data = {"reference": rid, "local-authority": code}
    if info["inferred"]:
        # Rule 6: the workbook guessed the type; MHCLG's model reads 'no application-type' as all types.
        notes.append("The workbook guessed the application type ('INFERRED'), so no type is given.")
        confidence = "low"
    elif info["types"]:
        data["required-if"] = {"application-type": {"in": info["types"]}}
    if st and garbled(st):
        notes.append("The workbook's excerpt looks garbled; re-read the council's list.")
        confidence = "low"
    if info["dropped"]:
        notes.append("Rows from " + ", ".join(dict.fromkeys(info["dropped"])) + " were dropped after the audit.")
    urls = info["urls"]
    if urls:
        data["source-url"] = max(set(urls), key=urls.count)
    if st:
        data["source-text"] = st
    data["confidence"] = confidence
    data["notes"] = notes
    return data


# ---------- applying the audit ----------

def keywords(rid, names, req_rows):
    """Words that identify a requirement in the audit's prose."""
    words = set()
    texts = list(names) + [req_rows[rid]["name"]] + req_rows[rid]["synonyms"].split(";")
    for t in texts:
        first = re.split(r"[/(]", t)[0].strip().lower()
        if len(first) > 3:
            words.add(first)
    return words


def doubted_by(issue_list, words):
    """Audit issues whose text mentions this requirement and cast doubt on it."""
    hits = []
    for i in issue_list:
        if i.get("type") not in ISSUE_TYPES_THAT_DOUBT and i.get("final_status") != "Open":
            continue
        text = (i.get("detail", "") + " " + i.get("claude_response", "")).lower()
        if any(w in text for w in words):
            hits.append(i)
    return hits


def apply_corrections(files, corr, code):
    """Apply a corrections file (see scripts/audit_corrections/README.md)."""
    for d in corr.get("drop") or []:
        if d.get("sheets"):
            continue  # already dropped row by row in collect()
        if d["id"] in files:
            del files[d["id"]]
        else:
            print(f"  note: {code} corrections drop '{d['id']}', but the workbook has no such row")
    for c in corr.get("requirements") or []:
        rid, action = c["id"], c.get("action", "replace")
        given = {k: v for k, v in c.items() if k not in ("id", "action")}
        if action in ("replace", "add") or rid not in files:
            base = {"reference": rid, "local-authority": code}
            if action == "update" and rid not in files:
                print(f"  note: {code} corrections update '{rid}', which the workbook doesn't have; adding it")
            files[rid] = {**base, **given}
            files[rid].setdefault("confidence", "medium")
            files[rid]["_corrected"] = True
        else:  # update: keep the workbook's file, override the keys given
            files[rid].update(given)
            files[rid]["_corrected"] = True
    for lc in corr.get("low-confidence") or []:
        targets = list(files) if lc["id"] == "*" else [lc["id"]]
        for rid in targets:
            if rid in files:
                files[rid]["confidence"] = "low"
                files[rid].setdefault("notes", [])
                files[rid]["notes"] = as_list(files[rid]["notes"]) + [lc["note"]]
    return files


def as_list(notes):
    if not notes:
        return []
    return notes if isinstance(notes, list) else [notes]


def finish(data, audit, has_corrections, req_rows, info):
    """Confidence caps, notes and key order (FORMAT.md)."""
    notes = as_list(data.pop("notes", []))
    if not audit:
        notes.append("Not audited: built from the workbook alone.")
        data["confidence"] = "low"
    elif not audit.get("contents_checked"):
        notes.append("The audit couldn't read this council's list, so its contents weren't checked.")
        data["confidence"] = "low"
    if audit and not has_corrections and not data.get("_corrected") and info:
        hits = doubted_by(audit.get("issues", []), keywords(data["reference"], info["names"], req_rows))
        if hits:
            data["confidence"] = "low"
            for i in hits:
                notes.append(f"Audit ({i['type']}, {i.get('final_status')}): {i['detail']}")
    order = ["reference", "local-authority", "required-if", "source-url", "policy", "source-text",
             "must-include", "confidence", "notes"]
    out = {}
    for k in order:
        v = " ".join(notes) if k == "notes" else data.get(k)
        if v not in (None, "", [], {}):
            out[k] = v
    return out


# ---------- writing, without touching checked cells ----------

def protect_marked(new, old):
    """Keep the old value of any cell marked human-verified or better."""
    if not old:
        return new
    marks = old.get("field-status") or {}
    statuses = review.cell_statuses(old, old.get("reference", ""))
    keep = {c for c, s in statuses.items() if s in PROTECTED}
    if keep & {"required-if", "application-type"}:
        if "required-if" in old:
            new["required-if"] = old["required-if"]
        else:
            new.pop("required-if", None)
    for cell in keep & {"must-include", "policy", "source-text", "source-url"}:
        if cell in old:
            new[cell] = old[cell]
        else:
            new.pop(cell, None)
    new["review-status"] = old.get("review-status", "unverified")
    new["field-status"] = marks
    return new


def write_council(code, files, dry):
    folder = SPEC / code
    existing = {p.stem: p for p in folder.glob("*.yaml") if p.name != "_lpa.yaml"}
    changes = []
    for rid, data in files.items():
        path = folder / f"{rid}.yaml"
        old = review_load(path)
        data = protect_marked(data, old)
        data.setdefault("review-status", "unverified")
        data.setdefault("field-status", {})
        if dry:
            if old != data:
                changes.append(("would write" if old else "would add", rid))
        elif write_yaml(path, data):
            changes.append(("updated" if old else "added", rid))
    for rid, path in existing.items():
        if rid in files:
            continue
        old = review_load(path)
        if set(review.cell_statuses(old, rid).values()) & PROTECTED:
            print(f"  kept {code}/{rid}.yaml: no longer in the workbook/corrections, but it has checked cells")
            continue
        changes.append(("would remove" if dry else "removed", rid))
        if not dry:
            path.unlink()
    return changes


def review_load(path):
    return load_yaml(path) if path.exists() else None


# ---------- _lpa.yaml from the audit ----------

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}


def parse_date(text):
    """Pull the most precise date out of free text: 'Last updated June 2020' -> '2020-06'."""
    t = str(text or "").lower()
    m = re.search(r"(20\d\d|19\d\d)-(\d\d)-(\d\d)", t)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d\d|19\d\d)", t)
    if m:
        return f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(" + "|".join(MONTHS) + r")\s+(20\d\d|19\d\d)", t)
    if m:
        return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"
    m = re.search(r"\b(20\d\d|19\d\d)\b", t)
    return m.group(1) if m else ""


def update_lpa(code, audit, corr, dry):
    path = SPEC / code / "_lpa.yaml"
    lpa = load_yaml(path)
    marks = lpa.get("field-status") or {}
    protected = {c for c, s in review.cell_statuses(lpa, "_lpa").items() if s in PROTECTED}
    vl = dict(lpa.get("validation-list") or {})
    new_vl = dict(vl)
    if audit:
        if audit.get("current_url"):
            new_vl["url"] = audit["current_url"]
        found = parse_date(audit.get("current_date"))
        if found and audit.get("current_date"):
            new_vl["date"] = found
            new_vl["date-basis"] = f"audit: {audit['current_date']}"
    if corr.get("validation-list"):
        new_vl.update(corr["validation-list"])
    if new_vl.get("status") not in ("national-only", "not-found"):
        cutoff = f"{int(TODAY[:4]) - 2}{TODAY[4:]}"
        new_vl["status"] = "outdated" if str(new_vl.get("date") or "9999") < cutoff else "current"
    for cell, key in (("validation-list-url", "url"), ("validation-list-date", "date"),
                      ("validation-list-status", "status")):
        if cell in protected:
            new_vl[key] = vl.get(key)
    if "validation-list-date" in protected:
        new_vl["date-basis"] = vl.get("date-basis")
    lpa["validation-list"] = new_vl
    if corr.get("submission-standards") and "submission-standards" not in protected:
        lpa["submission-standards"] = corr["submission-standards"]
    if audit:
        notes = audit.get("summary", "")
        if audit.get("review_note"):
            notes += " " + audit["review_note"]
        lpa["audit"] = {"status": "audited", "checked": AUDIT_DATE,
                        "contents-checked": bool(audit.get("contents_checked")),
                        "workbook-link-current": bool(audit.get("is_workbook_link_current")),
                        "issues-open": len(audit.get("issues", [])), "notes": notes.strip()}
    else:
        lpa["audit"] = {"status": "not-audited",
                        "notes": "No audit file yet: requirement files are capped at confidence: low."}
    lpa.pop("field-status", None)
    lpa["field-status"] = marks
    if not dry:
        write_yaml(path, lpa)


# ---------- the flat index CSVs ----------

def trigger_summary(rule):
    """Plain-English summary of a required-if rule, from its description lines."""
    if rule is None:
        return "see source-text"
    if rule == "discretionary":
        return "officer discretion"
    found = []

    def walk(x):
        if isinstance(x, dict):
            if x.get("always"):
                found.append("always")
            if "description" in x:
                found.append(str(x["description"]).strip())
            elif "ref" in x:
                found.append(str(x["ref"]).replace("-", " "))
            for k, v in x.items():
                if k not in ("description",):
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif x == "discretionary":
            found.append("other cases at officer discretion")
    walk(rule)
    return "; ".join(dict.fromkeys(found)) or "application type only"


def rebuild_index():
    path = DATA / "local-planning-requirement.csv"
    old = {(r["local-authority"], r["planning-requirement"], r["application-type"]): r.get("entry-date")
           for r in read_csv(path)} if path.exists() else {}
    rows = []
    for folder in sorted(p for p in SPEC.iterdir() if p.is_dir() and p.name != "definition"):
        for f in sorted(folder.glob("*.yaml")):
            if f.name == "_lpa.yaml":
                continue
            d = load_yaml(f)
            types = review.application_types(d.get("required-if")) or ["all"]
            for t in types:
                key = (folder.name, d["reference"], t)
                rows.append({"local-authority": folder.name, "planning-requirement": d["reference"],
                             "application-type": t, "trigger-summary": trigger_summary(d.get("required-if")),
                             "policy": d.get("policy", ""), "source-url": d.get("source-url", ""),
                             "confidence": d.get("confidence", ""), "review-status": d.get("review-status", ""),
                             "entry-date": old.get(key) or TODAY})
    write_csv(path, rows, ["local-authority", "planning-requirement", "application-type", "trigger-summary",
                           "policy", "source-url", "confidence", "review-status", "entry-date"])
    print(f"Rebuilt data/local-planning-requirement.csv ({len(rows)} rows)")


def write_unmapped(done_codes, new_rows):
    path = DATA / "unmapped-requirement.csv"
    cols = ["local-authority", "local-name", "source-text", "source-url", "suggested-id"]
    keep = [r for r in read_csv(path) if r["local-authority"] not in done_codes] if path.exists() else []
    seen, rows = set(), []
    for r in keep + new_rows:
        key = (r["local-authority"], r["local-name"], r["source-text"])
        if key not in seen:
            seen.add(key)
            rows.append(r)
    rows.sort(key=lambda r: (r["local-authority"], r["local-name"]))
    write_csv(path, rows, cols)


def add_new_fields(new_fields):
    """Add fields that corrections files introduced to data/new-field.csv."""
    path = DATA / "new-field.csv"
    rows = read_csv(path)
    known = {r["field"] for r in rows}
    cols = ["field", "kind", "label", "description", "example"]
    added = []
    for f in new_fields:
        if f["field"] in known:
            continue
        kind = f.get("kind", "boolean")
        example = {"designation": f"site: {{in: [{f['field']}]}}",
                   "number": f"condition: {{field: {f['field']}, operator: '>=', value: 1}}"}.get(
                       kind, f"condition: {{field: {f['field']}, value: true}}")
        rows.append({"field": f["field"], "kind": kind, "label": f.get("label", ""),
                     "description": f.get("description", "") + f" (first used by {f['source']})",
                     "example": example})
        known.add(f["field"])
        added.append(f["field"])
    if added:
        write_csv(path, rows, cols)
        print("Added new fields to data/new-field.csv:", ", ".join(added))


def validate(code, files, corr):
    """Run check.py's rule checks on files built in memory (nothing is written)."""
    import check
    from common import application_type_ids, requirement_ids
    check.problems.clear()
    fields = check.known_fields() | {f["field"] for f in corr.get("new-fields") or []}
    ctx = {"ids": requirement_ids(), "types": application_type_ids(), "fields": fields,
           "defs": {"major-development"}}
    ended = {r["reference"] for r in read_csv(DATA / "planning-requirement.csv") if r["end-date"]}
    for rid, data in files.items():
        where = f"{code}/{rid}"
        if rid not in ctx["ids"] or rid in ended:
            check.problem(f"{where}: '{rid}' isn't a current id in data/planning-requirement.csv")
        if data.get("confidence") not in ("high", "medium", "low"):
            check.problem(f"{where}: confidence must be high, medium or low")
        check.check_rule(data.get("required-if"), where, ctx)
        check.check_items(data.get("must-include"), where, ctx, "must-include")
    check.check_items(corr.get("submission-standards"), f"{code}/_lpa", ctx, "submission-standards")
    for u in corr.get("unmapped") or []:
        if not u.get("local-name") or "source-text" not in u:
            check.problem(f"{code}: every unmapped item needs local-name and source-text")
    if check.problems:
        print(f"{code}: {len(check.problems)} problem(s):")
        for msg in check.problems:
            print("   -", msg)
    else:
        print(f"{code}: valid ({len(files)} requirement files)")


# ---------- main ----------

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lpa", help="comma-separated council codes, e.g. CMD,SHR")
    p.add_argument("--region", help='comma-separated regions, e.g. "London,South East"')
    p.add_argument("--dry-run", action="store_true", help="only print what would change")
    p.add_argument("--validate", action="store_true",
                   help="build in memory and run check.py's rule checks; write nothing")
    a = p.parse_args()

    lpa_rows = {r["code"]: r for r in read_csv(DATA / "lpa.csv")}
    match = {r["code"]: r["workbook-name"] for r in read_csv(SCRIPTS / "lpa_match.csv") if r.get("code")}
    codes = sorted(lpa_rows)
    if a.lpa:
        codes = [c.strip() for c in a.lpa.split(",") if c.strip()]
    if a.region:
        regions = {x.strip() for x in a.region.split(",")}
        codes = [c for c in codes if lpa_rows.get(c, {}).get("region") in regions]
    for c in codes:
        if c not in lpa_rows:
            raise SystemExit(f"{c} isn't in data/lpa.csv")

    req_map, sheet_map = load_maps()
    req_rows = {r["reference"]: r for r in read_csv(DATA / "planning-requirement.csv")}
    wanted = {match[c]: c for c in codes}
    rows = read_workbook(sheet_map, set(wanted))
    all_audits = audits()
    unmapped_all, new_fields = [], []

    for code in codes:
        name = match[code]
        audit = all_audits.get(name)
        corr_path = CORRECTIONS / f"{code}.yaml"
        corr = load_yaml(corr_path) if corr_path.exists() else {}
        dropped = {(d["id"], sh) for d in corr.get("drop") or [] for sh in d.get("sheets") or []}
        by_id, unmapped = collect(rows.get(name, []), req_map, sheet_map, code, dropped)
        files = OrderedDict((rid, workbook_file(code, rid, info)) for rid, info in by_id.items()
                            if rid not in NATIONAL_ONLY_IDS and info["sheets"])
        files = apply_corrections(files, corr, code)
        gone = {d["local-name"] for d in corr.get("drop-unmapped") or []}
        unmapped = [u for u in unmapped if u["local-name"] not in gone]
        unmapped_all += unmapped + [dict(u, **{"local-authority": code}) for u in corr.get("unmapped") or []]
        new_fields += [dict(f, source=code) for f in corr.get("new-fields") or []]
        files = OrderedDict((rid, finish(d, audit, bool(corr), req_rows, by_id.get(rid)))
                            for rid, d in files.items())
        if a.validate:
            validate(code, files, corr)
            continue
        update_lpa(code, audit, corr, a.dry_run)
        changes = write_council(code, files, a.dry_run)
        flag = "" if corr else " (no corrections file yet)"
        print(f"{code}: {len(files)} requirement files, {len(unmapped)} unmapped items{flag}"
              + (f"; {len(changes)} change(s)" if changes else ""))
        if a.dry_run:
            for what, rid in changes:
                print(f"    {what} {rid}")

    if a.dry_run or a.validate:
        print("Nothing was written (" + ("--validate" if a.validate else "dry run") + ").")
        return
    write_unmapped(set(codes), unmapped_all)
    add_new_fields(new_fields)
    rebuild_index()
    report = []
    for code in codes:
        review.recompute_council(code, reset_stale=True, report=report)
    review.sync_lpa_csv()
    for line in report:
        print("  reset:", line)
    print("Done. Now run: python scripts/check.py")


if __name__ == "__main__":
    main()

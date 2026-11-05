"""Check MHCLG's register of planning authorities for changes, and update our copy.

Run:  python scripts/update_register.py           (download, show changes, save)
      python scripts/update_register.py --check   (download and show changes; save nothing.
                                                   Fails if a change affects our councils or
                                                   adds a planning authority. Runs monthly in
                                                   GitHub Actions: .github/workflows/register.yml)

Our copy is data/organisation.csv: one row per English planning authority
(code, name, ONS code, start and end dates). scripts/build_lpas.py uses it to
give each council its code.

Where it downloads from, in order:
  1. planning.data.gov.uk's organisation dataset (the official, current one)
  2. MHCLG's organisation-collection repo on GitHub (the files that dataset is built from)

After it reports a change that affects one of our councils (for example a
council was abolished in a merger, or renamed), run python scripts/build_lpas.py
and look at what it prints.
"""

import argparse
import csv
import io
import sys
import urllib.request

from common import DATA, SCRIPTS, read_csv, write_csv

OUT = DATA / "organisation.csv"
COLUMNS = ["code", "organisation", "name", "ons-code", "start-date", "end-date"]

OFFICIAL = "https://files.planning.data.gov.uk/organisation-collection/dataset/organisation.csv"
GITHUB = "https://raw.githubusercontent.com/digital-land/organisation-collection/main/data/"
GITHUB_FILES = {"local-authority.csv": "local-authority",
                "national-park-authority.csv": "national-park-authority",
                "development-corporation.csv": "development-corporation"}

# MHCLG's codes for national parks and development corporations are Wikidata
# ids (e.g. Q72617988), which aren't readable as folder names, so we use the
# authorities' own short names. The full MHCLG id stays in the 'organisation' column.
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


def fetch(url):
    """Download a CSV file and return its rows as dictionaries."""
    req = urllib.request.Request(url, headers={"User-Agent": "open-validation register check"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))


def row(organisation, name, ons, start, end):
    """One row of our file. The code is the part after ':' (or our short name)."""
    ref = organisation.split(":", 1)[-1]
    return {"code": SHORT_CODES.get(ref, ref), "organisation": organisation, "name": name,
            "ons-code": ons or "", "start-date": start or "", "end-date": end or ""}


def from_official():
    raw = fetch(OFFICIAL)
    needed = {"organisation", "name", "end-date", "local-planning-authority"}
    if not raw or not needed <= set(raw[0]):
        raise ValueError("the file doesn't have the columns we expect: " + ", ".join(sorted(needed)))
    rows = []
    for r in raw:
        org = r.get("organisation", "")
        if not org.startswith(tuple(GITHUB_FILES.values())):
            continue
        # Keep English planning authorities: anything with an LPA code, plus
        # county councils and the GLA (they have no E60 code but are in our list).
        if not (r.get("local-planning-authority") or org.startswith("local-authority:")):
            continue
        rows.append(row(org, r.get("name", ""), r.get("local-planning-authority"),
                        r.get("start-date"), r.get("end-date")))
    return rows


def from_github():
    rows = []
    for file, prefix in GITHUB_FILES.items():
        for r in fetch(GITHUB + file):
            org = r.get("organisation") or f"{prefix}:{r['reference']}"
            if prefix != "local-authority" and not r.get("local-planning-authority"):
                continue  # old development corporations with no planning powers
            rows.append(row(org, r["name"], r.get("local-planning-authority"),
                            r.get("start-date"), r.get("end-date")))
    return rows


def download():
    for label, get in (("planning.data.gov.uk", from_official), ("MHCLG's GitHub", from_github)):
        try:
            rows = get()
            if len(rows) > 300:
                print(f"Downloaded the register from {label} ({len(rows)} authorities).")
                return rows
            print(f"{label} returned too few rows ({len(rows)}); trying the next source.")
        except Exception as e:  # blocked, moved, or a different format
            print(f"Couldn't use {label} ({e}); trying the next source.")
    sys.exit("Couldn't download MHCLG's register from anywhere. Nothing was changed.")


def compare(old, new):
    """Return a list of plain-English changes, marking those that affect our councils."""
    ours = {r["code"] for r in read_csv(SCRIPTS / "lpa_match.csv") if r.get("code")}
    old = {r["code"]: r for r in old}
    new = {r["code"]: r for r in new}
    changes = []

    def say(code, text):
        flag = "  ** affects one of our councils **" if code in ours else ""
        changes.append((code in ours, f"{code}: {text}{flag}"))

    for code in sorted(set(new) - set(old)):
        if new[code]["ons-code"] and not new[code]["end-date"] and code not in ours:
            # A new planning authority (it has an LPA code): we'll need to add it.
            changes.append((True, f"{code}: NEW planning authority in the register: {new[code]['name']} "
                                  f"({new[code]['ons-code']})  ** we don't cover it yet **"))
        else:
            say(code, f"new in the register: {new[code]['name']}")
    for code in sorted(set(old) - set(new)):
        say(code, f"no longer in the register: {old[code]['name']}")
    for code in sorted(set(old) & set(new)):
        a, b = old[code], new[code]
        if a["end-date"] != b["end-date"]:
            say(code, f"end date changed from '{a['end-date']}' to '{b['end-date']}' ({b['name']})")
        if a["name"] != b["name"]:
            say(code, f"renamed from '{a['name']}' to '{b['name']}'")
        if a["ons-code"] != b["ons-code"]:
            say(code, f"ONS code changed from '{a['ons-code']}' to '{b['ons-code']}' ({b['name']})")
    return changes


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true", help="only report changes; fail if there are any")
    a = p.parse_args()

    new = sorted(download(), key=lambda r: r["code"])
    if not OUT.exists():
        write_csv(OUT, new, COLUMNS)
        print(f"No saved copy yet, so saved {len(new)} authorities to data/organisation.csv.")
        return
    changes = compare(read_csv(OUT), new)

    if not changes:
        print("No changes: our copy of the register is up to date.")
        return
    affecting = sum(1 for hit, _ in changes if hit)
    print(f"\n{len(changes)} change(s) in MHCLG's register ({affecting} affect our councils):")
    for _, text in changes:
        print("  -", text)
    if a.check:
        if not affecting:
            print("\nNone of these affect our councils, so the check passes. "
                  "Run python scripts/update_register.py to save them anyway.")
            return
        print("\nNothing saved (--check). To update: python scripts/update_register.py, "
              "then python scripts/build_lpas.py")
        sys.exit(1)
    write_csv(OUT, new, COLUMNS)
    print(f"\nSaved {OUT.relative_to(DATA.parent)}. Now run: python scripts/build_lpas.py")


if __name__ == "__main__":
    main()

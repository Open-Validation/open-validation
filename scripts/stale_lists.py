"""List councils whose validation list is more than 2 years old (or has no date).

Run:  python scripts/stale_lists.py [--report <file>]

The NPPF expects councils to review their local list at least every 2 years.
A GitHub Action runs this monthly (.github/workflows/stale-lists.yml) and keeps
one 'stale-lists' issue up to date, so old lists surface without anyone looking.
"""

import argparse
from datetime import date, timedelta

from common import DATA, read_csv


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--report", help="write the list to this file as Markdown")
    a = p.parse_args()

    cutoff = (date.today() - timedelta(days=730)).isoformat()
    rows = read_csv(DATA / "lpa.csv")
    old = sorted((r for r in rows if r["list-date"] and r["list-date"] < cutoff), key=lambda r: r["list-date"])
    undated = [r for r in rows if not r["list-date"] and r["list-status"] != "national-only"]

    lines = [f"**{len(old)} of {len(rows)} councils** have a validation list more than 2 years old "
             f"(before {cutoff}). The NPPF expects local lists to be reviewed at least every 2 years. "
             f"If a council has published a newer list, update its `_lpa.yaml`.", "",
             "| Council | Code | List date | Status |", "|---|---|---|---|"]
    lines += [f"| {r['name']} | {r['code']} | {r['list-date']} | {r['review-status']} |" for r in old]
    if undated:
        lines += ["", f"**{len(undated)} councils have no list date:** " +
                  ", ".join(f"{r['name']} ({r['code']})" for r in undated)]
    lines += ["", f"_Updated {date.today().isoformat()} by the monthly stale-lists check._"]
    text = "\n".join(lines) + "\n"
    print(text)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()

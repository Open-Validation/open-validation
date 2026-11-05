"""Mark cells as checked, from the command line.

Examples:
  python scripts/set_status.py SHR human-verified --by "Jake White"
      marks every non-empty cell in every SHR file (including _lpa.yaml)
  python scripts/set_status.py SHR human-verified --by "Jake White" --files site-plan,_lpa --cells required-if,source-text
  python scripts/set_status.py SHR council-verified --by "Jake White" --evidence https://github.com/.../issues/12
  python scripts/set_status.py SHR incorrect --by "Jake White" --files site-plan --cells required-if --note "Now needed for all householder applications"
  python scripts/set_status.py --recompute
      changes no marks on purpose: resets any cell edited since it was marked
      back to unverified (and lists them), then recomputes every file, every
      council, coverage and data/lpa.csv

Statuses: incorrect, unverified, human-verified, council-verified, council-updated.
The two council statuses need --evidence; 'incorrect' needs --note (what's wrong). Marking a cell 'unverified' removes its mark.
"""

import argparse
import sys

from common import SPEC, load_yaml, lpa_folders, write_yaml
import review


def recompute_all():
    report = []
    for folder in lpa_folders():
        review.recompute_council(folder.name, reset_stale=True, report=report)
    review.sync_lpa_csv()
    if report:
        print("These cells changed after they were marked, so they are back to unverified:")
        for line in report:
            print("  -", line)
    else:
        print("No marks were out of date.")
    print(f"Recomputed review-status and coverage for {len(lpa_folders())} councils and updated data/lpa.csv.")


def mark(code, status, by, files, cells, evidence, note=""):
    folder = SPEC / code
    if not (folder / "_lpa.yaml").exists():
        sys.exit(f"There is no council folder called {code}.")
    if status in review.NEEDS_EVIDENCE and not evidence:
        sys.exit(f"'{status}' needs --evidence (a link to the issue or PR, or a short note of the email).")
    if status in review.NEEDS_NOTE and not note:
        sys.exit(f"'{status}' needs --note saying what's wrong (or what the council's list actually says).")
    if status not in review.STATUSES:
        sys.exit(f"'{status}' isn't a status. Use one of: {', '.join(review.STATUSES)}")

    paths = sorted(folder.glob("*.yaml"))
    if files:
        wanted = set(files)
        paths = [p for p in paths if p.stem in wanted]
        missing = wanted - {p.stem for p in paths}
        if missing:
            sys.exit(f"No such file(s) in {code}/: {', '.join(sorted(missing))}")

    changed = 0
    for path in paths:
        data = load_yaml(path)
        names = review.cells_for(path.stem)
        targets = [c for c in (cells or names) if c in names]
        done = []
        for cell in targets:
            if review.mark_cell(data, path.stem, cell, status, by, evidence=evidence, note=note):
                done.append(cell)
        if done:
            write_yaml(path, data)
            changed += len(done)
            print(f"{code}/{path.name}: marked {', '.join(done)} as {status}")
    council = review.recompute_council(code, reset_stale=False)
    review.sync_lpa_csv([code])
    print(f"\nMarked {changed} cell(s). {code} is now '{council}' overall (the lowest of all its cells).")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("code", nargs="?", help="council code, e.g. SHR")
    p.add_argument("status", nargs="?", help="the status to give the cells")
    p.add_argument("--by", help="who checked them (your name)")
    p.add_argument("--files", help="comma-separated file names without .yaml (use _lpa for _lpa.yaml)")
    p.add_argument("--cells", help="comma-separated cell names (default: every non-empty cell)")
    p.add_argument("--evidence", default="", help="link or note; needed for the council statuses")
    p.add_argument("--note", default="", help="what's wrong; needed for 'incorrect'")
    p.add_argument("--recompute", action="store_true", help="only recompute statuses (see above)")
    a = p.parse_args()

    if a.recompute:
        recompute_all()
        return
    if not (a.code and a.status and a.by):
        p.error("give a council code, a status and --by (or use --recompute)")
    split = lambda s: [x.strip().removesuffix(".yaml") for x in s.split(",") if x.strip()] if s else None
    mark(a.code, a.status, a.by, split(a.files), split(a.cells), a.evidence, a.note)


if __name__ == "__main__":
    main()

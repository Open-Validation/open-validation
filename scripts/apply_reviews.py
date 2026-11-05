"""Apply cell marks submitted from the explorer's review mode.

Run:  python scripts/apply_reviews.py

Each file in reviews/pending/ is a list of marks like this:

  - lpa: SHR
    file: site-plan          # or _lpa
    cell: required-if
    status: human-verified
    by: Jake White
    date: 2026-11-06
    evidence: ""             # needed for the two council statuses

All marks in all pending files are checked first. If any is wrong, nothing is
changed and you get a clear message. Otherwise they're applied, each file is
moved to reviews/applied/, every status is recomputed and a summary printed.
"""

import shutil
import sys

from common import ROOT, SPEC, load_yaml, write_yaml
import review

PENDING = ROOT / "reviews" / "pending"
APPLIED = ROOT / "reviews" / "applied"


def check_mark(m, where):
    """Return a list of problems with one mark (empty list = fine)."""
    if not isinstance(m, dict):
        return [f"{where}: each mark must be a set of keys (lpa, file, cell, status, by, date)"]
    problems = []
    for key in ("lpa", "file", "cell", "status", "by", "date"):
        if not m.get(key):
            problems.append(f"{where}: missing '{key}'")
    if problems:
        return problems
    path = SPEC / str(m["lpa"]) / f"{m['file']}.yaml"
    if not path.exists():
        problems.append(f"{where}: there is no file {m['lpa']}/{m['file']}.yaml")
    elif m["cell"] not in review.cells_for(m["file"]):
        problems.append(f"{where}: '{m['cell']}' is not a cell of {m['file']}")
    elif review.is_empty(review.cell_value(load_yaml(path), m["cell"])):
        problems.append(f"{where}: {m['lpa']}/{m['file']} '{m['cell']}' is empty, so it can't be marked")
    if m["status"] not in review.STATUSES:
        problems.append(f"{where}: '{m['status']}' is not a status ({', '.join(review.STATUSES)})")
    if m["status"] in review.NEEDS_EVIDENCE and not m.get("evidence"):
        problems.append(f"{where}: '{m['status']}' needs evidence")
    return problems


def main():
    files = sorted(PENDING.glob("*.yaml"))
    if not files:
        print("Nothing to apply: reviews/pending/ has no .yaml files.")
        return

    batches, problems = [], []
    for f in files:
        try:
            marks = load_yaml(f) or []
        except Exception as e:  # a YAML syntax error
            problems.append(f"{f.name}: can't be read as YAML ({e})")
            continue
        if not isinstance(marks, list):
            problems.append(f"{f.name}: should be a list of marks (each starting with '- lpa:')")
            continue
        for i, m in enumerate(marks, 1):
            problems += check_mark(m, f"{f.name} mark {i}")
        batches.append((f, marks))
    if problems:
        print("Nothing was changed, because of these problems:")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    councils, count = set(), 0
    for f, marks in batches:
        for m in marks:
            path = SPEC / m["lpa"] / f"{m['file']}.yaml"
            data = load_yaml(path)
            review.mark_cell(data, m["file"], m["cell"], m["status"], m["by"],
                             when=m["date"], evidence=m.get("evidence") or "")
            write_yaml(path, data)
            councils.add(m["lpa"])
            count += 1
        APPLIED.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), APPLIED / f.name)
        print(f"Applied {len(marks)} mark(s) from {f.name} and moved it to reviews/applied/")

    for code in sorted(councils):
        status = review.recompute_council(code, reset_stale=True)
        print(f"  {code} is now '{status}' overall")
    review.sync_lpa_csv(sorted(councils))
    print(f"Done: {count} cell(s) marked across {len(councils)} council(s).")


if __name__ == "__main__":
    main()

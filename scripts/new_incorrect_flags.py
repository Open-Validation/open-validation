"""List cells newly flagged 'incorrect' since an earlier commit.

Run:  python scripts/new_incorrect_flags.py <earlier-commit> [--report <file>]

Example:  python scripts/new_incorrect_flags.py HEAD~5

GitHub Actions runs this every time something lands on main
(.github/workflows/incorrect-alert.yml). If any cell has been flagged
'incorrect' that wasn't before, it writes the list to the report file, and the
workflow opens an issue that mentions the repo owner, so they get an email.
It doesn't matter how the flag got there: review mode, set_status.py, or a
hand edit.
"""

import argparse
import subprocess
import sys

import yaml

from common import ROOT, SPEC, load_yaml


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def flags(data):
    """{cell: mark} for every cell marked 'incorrect' in a loaded file."""
    marks = (data or {}).get("field-status") or {}
    return {cell: m for cell, m in marks.items() if (m or {}).get("status") == "incorrect"}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("since", help="the earlier commit to compare with")
    p.add_argument("--report", help="write the list to this file if there are new flags")
    a = p.parse_args()

    spec = str(SPEC.relative_to(ROOT))
    changed = git("diff", "--name-only", a.since, "HEAD", "--", spec)
    if changed.returncode != 0:
        # The earlier commit isn't known (for example the first push): check every file.
        print(f"Couldn't compare with {a.since}, so checking every file.")
        paths = [str(p.relative_to(ROOT)) for p in SPEC.rglob("*.yaml")]
    else:
        paths = [x for x in changed.stdout.splitlines() if x.endswith(".yaml")]

    new = []
    for path in paths:
        if not (ROOT / path).exists():
            continue  # file deleted
        now = flags(load_yaml(ROOT / path))
        old_text = git("show", f"{a.since}:{path}")
        before = flags(yaml.safe_load(old_text.stdout)) if old_text.returncode == 0 else {}
        for cell, m in now.items():
            if cell not in before or before[cell].get("hash") != m.get("hash"):
                code, name = path.split("/")[-2], path.split("/")[-1].removesuffix(".yaml")
                new.append(f"- **{code} / {name}**, cell `{cell}`, flagged by {m.get('by')} on "
                           f"{m.get('date')}: {m.get('note', '(no note)')}")

    if not new:
        print("No new 'incorrect' flags.")
        return
    text = f"{len(new)} cell(s) newly flagged as **incorrect**:\n\n" + "\n".join(new) + "\n"
    print(text)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    sys.exit(main())

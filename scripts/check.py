"""Integrity checks for the whole repo. Also runs in GitHub Actions.

Run:  python scripts/check.py

It prints every problem it finds in plain English and exits with an error if
there are any. Then it prints a summary of the data.
"""

import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

from common import DATA, DEFINITIONS, ROOT, SPEC, application_type_ids, read_csv, requirement_ids
import review

# Fields MHCLG already use in their planning-requirement files (FORMAT.md).
MHCLG_FIELDS = {"dwelling-count", "site-area-residential", "site-area-non-residential",
                "floorspace-non-residential", "floorspace", "housing-floorspace", "housing-type"}
OPERATORS = {">=", ">", "<=", "<", "=="}
LEVELS = {"must", "should"}
CONFIDENCE = {"high", "medium", "low"}
ROOT_FILES_OK = {"_lpa.yaml"}

problems = []


def problem(msg):
    problems.append(msg)


def rel(path):
    return str(Path(path).relative_to(ROOT))


# ---------- loading ----------

def load_all():
    """Parse every .yaml under specification/. Report .yml files and '---'."""
    loaded = {}
    for path in sorted(SPEC.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix == ".yml":
            problem(f"{rel(path)}: use the .yaml extension, not .yml")
            continue
        if path.suffix != ".yaml":
            continue
        text = path.read_text(encoding="utf-8")
        if any(line.strip() == "---" for line in text.splitlines()):
            problem(f"{rel(path)}: contains a '---' line. Our files are plain YAML, not Markdown front matter")
        if re.search(r"(^|[\s:\-\[,])[&*]id\d+", text, re.M):
            problem(f"{rel(path)}: contains a YAML anchor (&id001 / *id001). Write each rule out in full")
        try:
            loaded[path] = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            problem(f"{rel(path)}: isn't valid YAML ({str(e).splitlines()[0]})")
    return loaded


def definitions(loaded):
    names = set()
    for path, data in loaded.items():
        if path.parent == DEFINITIONS:
            names.update((data.get("definition") or {}).keys())
    return names


def known_fields():
    """MHCLG's fields plus everything listed in data/new-field.csv."""
    fields = set(MHCLG_FIELDS)
    path = DATA / "new-field.csv"
    if path.exists():
        fields.update(r["field"] for r in read_csv(path))
    return fields


# ---------- rule checks ----------

def check_rule(rule, where, ctx):
    """Walk a required-if rule and check every construct in it."""
    if rule is None or rule == "discretionary":
        return
    if isinstance(rule, list):
        for item in rule:
            check_rule(item, where, ctx)
        return
    if not isinstance(rule, dict):
        problem(f"{where}: don't understand the rule '{rule}'")
        return
    for key, value in rule.items():
        if key in ("all", "any"):
            if not isinstance(value, list):
                problem(f"{where}: '{key}:' must be followed by a list")
            check_rule(value, where, ctx)
        elif key == "condition":
            value = value or {}
            field = value.get("field")
            if field not in ctx["fields"]:
                problem(f"{where}: field '{field}' isn't an MHCLG field or listed in data/new-field.csv")
            op = value.get("operator")
            if op is not None and op not in OPERATORS:
                problem(f"{where}: operator '{op}' isn't allowed (use {', '.join(sorted(OPERATORS))})")
        elif key == "application-type":
            for t in (value or {}).get("in") or []:
                if t not in ctx["types"]:
                    problem(f"{where}: application type '{t}' isn't in data/planning-application-type.csv")
        elif key == "site":
            for s in (value or {}).get("in") or []:
                if s not in ctx["fields"]:
                    problem(f"{where}: site designation '{s}' isn't listed in data/new-field.csv")
        elif key == "ref":
            if value not in ctx["defs"]:
                problem(f"{where}: 'ref: {value}' doesn't exist in specification/planning-requirement/definition/")
        elif key in ("always", "description"):
            pass
        else:
            problem(f"{where}: unknown rule key '{key}'")


def check_items(items, where, ctx, label):
    """must-include and submission-standards items."""
    if items is None:
        return
    if not isinstance(items, list):
        problem(f"{where}: '{label}' must be a list")
        return
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict) or not item.get("item"):
            problem(f"{where}: {label} item {i} has no 'item'")
            continue
        if item.get("level") not in LEVELS:
            problem(f"{where}: {label} item {i} has level '{item.get('level')}' (use must or should)")
        if "required-if" in item:
            check_rule(item["required-if"], f"{where} ({label} item {i})", ctx)


def check_marks(data, where, filename):
    marks = data.get("field-status")
    if marks in (None, {}):
        return
    if not isinstance(marks, dict):
        problem(f"{where}: field-status must be a set of cell: mark entries")
        return
    for cell, mark in marks.items():
        if cell not in review.cells_for(filename):
            problem(f"{where}: field-status has '{cell}', which isn't a cell name ({', '.join(review.cells_for(filename))})")
            continue
        mark = mark or {}
        if mark.get("status") not in review.STATUSES:
            problem(f"{where}: '{cell}' has status '{mark.get('status')}' (use one of {', '.join(review.STATUSES)})")
        if not mark.get("by") or not mark.get("date"):
            problem(f"{where}: the mark on '{cell}' needs both 'by' and 'date'")
        if mark.get("status") in review.NEEDS_EVIDENCE and not mark.get("evidence"):
            problem(f"{where}: '{cell}' is marked {mark.get('status')} but has no 'evidence'")
        if mark.get("status") in review.NEEDS_NOTE and not mark.get("note"):
            problem(f"{where}: '{cell}' is marked incorrect but has no 'note' saying what's wrong")
        if mark.get("status") in review.RECORDS_CHECKED_AGAINST and not (mark.get("checked-against") or {}).get("url"):
            problem(f"{where}: '{cell}' is marked {mark.get('status')} but doesn't say which list it was "
                    f"checked against ('checked-against: url')")
        value = review.cell_value(data, cell)
        if review.is_empty(value) or mark.get("hash") != review.cell_hash(value):
            problem(f"{where}: '{cell}' changed after it was marked (hash doesn't match). "
                    f"Run: python scripts/set_status.py --recompute")
    if filename == "_lpa":
        return  # a council's review-status is the roll-up of its whole folder, checked in main()
    expected = review.file_status(data, filename)
    if data.get("review-status") != expected:
        problem(f"{where}: review-status is '{data.get('review-status')}' but its cells say '{expected}'. "
                f"Run: python scripts/set_status.py --recompute")


def check_requirement(path, data, ctx):
    where = rel(path)
    code = path.parent.name
    if path.stem not in ctx["ids"]:
        problem(f"{where}: '{path.stem}' isn't an id in data/planning-requirement.csv")
    if data.get("reference") != path.stem:
        problem(f"{where}: reference is '{data.get('reference')}' but the file is called {path.name}")
    if data.get("local-authority") != code:
        problem(f"{where}: local-authority is '{data.get('local-authority')}' but the folder is {code}")
    if data.get("confidence") not in CONFIDENCE:
        problem(f"{where}: confidence must be high, medium or low")
    check_rule(data.get("required-if"), where, ctx)
    check_items(data.get("must-include"), where, ctx, "must-include")
    check_marks(data, where, path.stem)
    if data.get("review-status") is None:
        problem(f"{where}: has no review-status. Run: python scripts/set_status.py --recompute")


def check_national(path, data, ctx):
    where = rel(path)
    if path.stem not in ctx["ids"]:
        problem(f"{where}: '{path.stem}' isn't an id in data/planning-requirement.csv")
    if data.get("reference") != path.stem:
        problem(f"{where}: reference doesn't match the filename")
    check_rule(data.get("required-if"), where, ctx)
    check_items(data.get("must-include"), where, ctx, "must-include")


def main():
    loaded = load_all()
    ctx = {"ids": requirement_ids(), "types": application_type_ids(),
           "fields": known_fields(), "defs": definitions(loaded)}
    lpa_rows = {r["code"]: r for r in read_csv(DATA / "lpa.csv")}
    folders = {p.name for p in SPEC.iterdir() if p.is_dir() and p.name != "definition"}

    for path, data in loaded.items():
        if path.parent == DEFINITIONS:
            for name, rule in (data.get("definition") or {}).items():
                check_rule({k: v for k, v in rule.items() if k != "description"}, rel(path), ctx)
        elif path.parent == SPEC:
            check_national(path, data, ctx)
        elif path.name == "_lpa.yaml":
            where = rel(path)
            if data.get("local-authority") != path.parent.name:
                problem(f"{where}: local-authority doesn't match the folder name")
            vstatus = (data.get("validation-list") or {}).get("status")
            if vstatus not in ("current", "outdated", "not-found", "national-only"):
                problem(f"{where}: validation-list.status '{vstatus}' isn't current/outdated/not-found/national-only")
            check_items(data.get("submission-standards"), where, ctx, "submission-standards")
            check_marks(data, where, "_lpa")
        else:
            check_requirement(path, data, ctx)

    # Council roll-ups, coverage and lpa.csv agreement
    for code in sorted(folders):
        lpa_path = SPEC / code / "_lpa.yaml"
        if not lpa_path.exists():
            problem(f"specification/planning-requirement/{code}/ has no _lpa.yaml")
            continue
        if code not in lpa_rows:
            problem(f"{code} has a folder but isn't in data/lpa.csv")
            continue
        lpa = loaded.get(lpa_path, {})
        _, reqs = review.folder_files(code)
        statuses = []
        for p in reqs + [lpa_path]:
            statuses += review.cell_statuses(loaded.get(p, {}), p.stem).values()
        expected = review.lowest(statuses)
        if lpa.get("review-status") != expected:
            problem(f"{code}/_lpa.yaml: review-status is '{lpa.get('review-status')}' but its cells say "
                    f"'{expected}'. Run: python scripts/set_status.py --recompute")
        want = review.lpa_csv_row(code, lpa_rows[code])
        for col in ("review-status", "coverage", "list-status", "list-date", "validation-list-url",
                    "audit-status", "issues-open", "partners"):
            if str(lpa_rows[code].get(col, "")) != str(want[col]):
                problem(f"data/lpa.csv: {code} '{col}' is '{lpa_rows[code].get(col)}' but the folder says "
                        f"'{want[col]}'. Run: python scripts/set_status.py --recompute")
    for code in sorted(set(lpa_rows) - folders):
        problem(f"data/lpa.csv lists {code} but there is no folder specification/planning-requirement/{code}/")

    check_evaluator_copies()
    check_index()

    if problems:
        print(f"check.py found {len(problems)} problem(s):\n")
        for p in problems[:300]:
            print("  -", p)
        if len(problems) > 300:
            print(f"  ... and {len(problems) - 300} more")
        print()
    summary(loaded, lpa_rows)
    sys.exit(1 if problems else 0)


def check_evaluator_copies():
    """The rule evaluator is copied in docs/index.html and docs/evaluate.test.html; they must match."""
    import re
    pages = [ROOT / "docs" / "index.html", ROOT / "docs" / "evaluate.test.html"]
    if not all(p.exists() for p in pages):
        return
    code = []
    for p in pages:
        m = re.search(r"// ===== EVALUATOR START.*?// ===== EVALUATOR END =====", p.read_text(encoding="utf-8"), re.S)
        code.append(m.group(0) if m else None)
    if None in code or code[0] != code[1]:
        problem("docs/index.html and docs/evaluate.test.html have different copies of the rule evaluator "
                "(the code between the EVALUATOR START and END markers must be identical)")


def check_index():
    """data/local-planning-requirement.csv must list exactly the requirement files on disk."""
    path = DATA / "local-planning-requirement.csv"
    if not path.exists():
        return
    listed = {(r["local-authority"], r["planning-requirement"]) for r in read_csv(path)}
    on_disk = {(p.parent.name, p.stem) for p in SPEC.glob("*/*.yaml")
               if p.parent.name != "definition" and p.name != "_lpa.yaml"}
    if listed != on_disk:
        extra, missing = sorted(listed - on_disk)[:5], sorted(on_disk - listed)[:5]
        problem("data/local-planning-requirement.csv is out of date "
                f"(lists missing files: {extra}; files not listed: {missing}). "
                "Run: python scripts/build_from_workbook.py --lpa <CODE> or rebuild the index")


def summary(loaded, lpa_rows):
    reqs = {p: d for p, d in loaded.items()
            if p.parent.parent == SPEC and p.parent.name != "definition" and p.name != "_lpa.yaml"}
    lpas = {p: d for p, d in loaded.items() if p.name == "_lpa.yaml"}
    with_files = {p.parent.name for p in reqs}
    conf = Counter(d.get("confidence") for d in reqs.values())
    file_status = Counter(d.get("review-status") for d in list(reqs.values()) + list(lpas.values()))
    council_status = Counter(r["review-status"] for r in lpa_rows.values())
    coverage = Counter(r["coverage"] for r in lpa_rows.values())
    cells = Counter()
    for p, d in list(reqs.items()) + list(lpas.items()):
        cells.update(review.cell_statuses(d, p.stem).values())
    audit = Counter((d.get("audit") or {}).get("status", "not-audited") for d in lpas.values())
    cutoff = (date.today() - timedelta(days=730)).isoformat()
    old = sorted(r["code"] for r in lpa_rows.values() if r["list-date"] and r["list-date"] < cutoff)

    fmt = lambda c: ", ".join(f"{k}: {v}" for k, v in sorted(c.items(), key=lambda x: str(x[0]))) or "none"
    print("Summary")
    print(f"  LPAs:                         {len(lpa_rows)}")
    print(f"  LPAs with no requirement files: {len(set(lpa_rows) - with_files)}")
    print(f"  Requirement files:            {len(reqs)}")
    print(f"  Files by confidence:          {fmt(conf)}")
    print(f"  Councils by coverage:         {fmt(coverage)}")
    print(f"  Councils by review status:    {fmt(council_status)}")
    print(f"  Files by review status:       {fmt(file_status)}  (includes _lpa.yaml)")
    print(f"  Cells by review status:       {fmt(cells)}")
    print(f"  Audit:                        {fmt(audit)}")
    print(f"  Lists more than 2 years old:  {len(old)} (NPPF expects review at least every 2 years)")
    if old:
        print("    " + " ".join(old))
    print("\nAll checks passed." if not problems else f"\n{len(problems)} problem(s) to fix (listed above).")


if __name__ == "__main__":
    main()

"""The review-status rules from FORMAT.md, in one place.

Other scripts import this module, so the rules are only written once:
  - which "cells" each kind of file has, and how to read each cell's value
  - the hash (fingerprint) of a cell's value
  - how statuses roll up to a file and to a council
  - coverage, and keeping data/lpa.csv in step with the _lpa.yaml files

You don't run this file directly.
"""

import hashlib
import json
from datetime import date

from common import DATA, SPEC, load_yaml, read_csv, write_csv, write_yaml

# The four statuses, from least to most trusted.
STATUSES = ["unverified", "human-verified", "council-verified", "council-updated"]
NEEDS_EVIDENCE = {"council-verified", "council-updated"}

# The cells of a requirement file and of a council's _lpa.yaml (FORMAT.md, "Review status").
REQUIREMENT_CELLS = ["requirement", "application-type", "required-if", "must-include",
                     "policy", "source-text", "source-url"]
LPA_CELLS = ["validation-list-url", "validation-list-date", "validation-list-status",
             "submission-standards", "contact", "joint-list"]


def cells_for(filename):
    """The cell names for a file: _lpa.yaml has its own six."""
    return LPA_CELLS if filename in ("_lpa", "_lpa.yaml") else REQUIREMENT_CELLS


def application_types(rule):
    """Every application-type id used anywhere inside a required-if rule, sorted."""
    found = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "application-type" and isinstance(v, dict):
                    found.update(v.get("in") or [])
                else:
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)

    walk(rule)
    return sorted(found)


def cell_value(data, cell):
    """Read one cell's value out of a loaded file."""
    vl = data.get("validation-list") or {}
    getters = {
        "requirement": lambda: data.get("reference"),
        "application-type": lambda: application_types(data.get("required-if")),
        "required-if": lambda: data.get("required-if"),
        "must-include": lambda: data.get("must-include"),
        "policy": lambda: data.get("policy"),
        "source-text": lambda: data.get("source-text"),
        "source-url": lambda: data.get("source-url"),
        "validation-list-url": lambda: vl.get("url"),
        "validation-list-date": lambda: vl.get("date"),
        "validation-list-status": lambda: vl.get("status"),
        "submission-standards": lambda: data.get("submission-standards"),
        "contact": lambda: data.get("contact"),
        "joint-list": lambda: data.get("joint-list"),
    }
    return getters[cell]()


def is_empty(value):
    """An empty cell (no policy given, no contact...) has no status and doesn't count."""
    return value is None or value == "" or value == [] or value == {}


def cell_hash(value):
    """First 8 characters of the SHA-1 of the value written as JSON.
    (Dates are written as text, so 2022-05-01 and '2022-05-01' hash the same.)"""
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def lowest(statuses):
    """The least trusted status in a list (unverified if the list is empty)."""
    statuses = list(statuses)
    if not statuses:
        return "unverified"
    return min(statuses, key=STATUSES.index)


def cell_statuses(data, filename):
    """{cell: status} for every non-empty cell of a file. A cell with no mark,
    or whose hash no longer matches its value, counts as unverified."""
    marks = data.get("field-status") or {}
    out = {}
    for cell in cells_for(filename):
        value = cell_value(data, cell)
        if is_empty(value):
            continue
        mark = marks.get(cell) or {}
        ok = mark.get("status") in STATUSES and mark.get("hash") == cell_hash(value)
        out[cell] = mark["status"] if ok else "unverified"
    return out


def stale_marks(data, filename):
    """Cells whose mark no longer matches the value (edited after marking),
    or which are marked but now empty."""
    marks = data.get("field-status") or {}
    stale = []
    for cell, mark in marks.items():
        if cell not in cells_for(filename):
            continue
        value = cell_value(data, cell)
        if is_empty(value) or (mark or {}).get("hash") != cell_hash(value):
            stale.append(cell)
    return stale


def file_status(data, filename):
    """Roll-up for one file: the lowest status among its non-empty cells."""
    return lowest(cell_statuses(data, filename).values())


def mark_cell(data, filename, cell, status, by, when=None, evidence=""):
    """Write a mark for one cell into data['field-status'] (in memory).
    Returns False (and changes nothing) if the cell is empty."""
    if cell not in cells_for(filename):
        raise ValueError(f"'{cell}' is not a cell of {filename}. Cells: {', '.join(cells_for(filename))}")
    if status not in STATUSES:
        raise ValueError(f"'{status}' is not a status. Use one of: {', '.join(STATUSES)}")
    if status in NEEDS_EVIDENCE and not evidence:
        raise ValueError(f"'{status}' needs evidence (a link to the issue or PR, or a note of the email)")
    value = cell_value(data, cell)
    if is_empty(value):
        return False
    marks = data.setdefault("field-status", {}) or {}
    data["field-status"] = marks
    if status == "unverified":
        marks.pop(cell, None)  # back to the default: no entry
        return True
    entry = {"status": status, "by": by, "date": str(when or date.today().isoformat())}
    if evidence:
        entry["evidence"] = evidence
    entry["hash"] = cell_hash(value)
    marks[cell] = entry
    return True


def put_status_last(data, status):
    """Set review-status and keep 'review-status' and 'field-status' as the
    last two keys (FORMAT.md key order). For _lpa.yaml the review-status
    sits near the top, so it's left where it is."""
    marks = data.pop("field-status", {}) or {}
    if "local-authority" in data and "validation-list" in data:  # an _lpa.yaml
        data["review-status"] = status
    else:
        data.pop("review-status", None)
        data["review-status"] = status
    data["field-status"] = marks
    return data


def folder_files(code):
    """(_lpa.yaml path, [requirement file paths]) for one council."""
    folder = SPEC / code
    lpa = folder / "_lpa.yaml"
    reqs = sorted(p for p in folder.glob("*.yaml") if p.name != "_lpa.yaml")
    return lpa, reqs


def coverage(lpa_data, requirement_count):
    """covered once we have at least one requirement file, or we know the
    council has no local list (validation-list.status: national-only)."""
    status = (lpa_data.get("validation-list") or {}).get("status")
    return "covered" if requirement_count > 0 or status == "national-only" else "not-covered"


def recompute_council(code, reset_stale=True, report=None):
    """Recompute every file's review-status and the council's roll-up.
    If reset_stale, marks whose hash no longer matches are removed (the cell
    drops back to unverified) and listed in report. Returns the council status."""
    lpa_path, reqs = folder_files(code)
    all_statuses = []
    for path in reqs + [lpa_path]:
        data = load_yaml(path)
        name = path.stem
        if reset_stale:
            for cell in stale_marks(data, name):
                data["field-status"].pop(cell, None)
                if report is not None:
                    report.append(f"{code}/{path.name}: '{cell}' changed after it was marked, so it is back to unverified")
        statuses = cell_statuses(data, name)
        all_statuses += statuses.values()
        if path != lpa_path:
            put_status_last(data, lowest(statuses.values()))
            write_yaml(path, data)
    lpa = load_yaml(lpa_path)
    if reset_stale:
        for cell in stale_marks(lpa, "_lpa"):
            lpa["field-status"].pop(cell, None)
    council = lowest(all_statuses)
    put_status_last(lpa, council)
    write_yaml(lpa_path, lpa)
    return council


LPA_COLUMNS = ["code", "ons-code", "name", "region", "type", "validation-list-url", "list-date",
               "list-status", "coverage", "review-status", "audit-status", "issues-open",
               "joint-list", "partners", "notes", "entry-date"]


def lpa_csv_row(code, base):
    """The data/lpa.csv row for a council, worked out from its folder.
    'base' is the existing row (for ons-code, region, type, notes, entry-date)."""
    lpa_path, reqs = folder_files(code)
    lpa = load_yaml(lpa_path)
    vl = lpa.get("validation-list") or {}
    audit = lpa.get("audit") or {}
    partners = (lpa.get("joint-list") or {}).get("partners") or []
    row = dict(base)
    row.update({
        "code": code,
        "name": lpa.get("name", base.get("name", "")),
        "region": lpa.get("region", base.get("region", "")),
        "type": lpa.get("type", base.get("type", "")),
        "validation-list-url": vl.get("url") or "",
        "list-date": str(vl.get("date") or ""),
        "list-status": vl.get("status") or "",
        "coverage": coverage(lpa, len(reqs)),
        "review-status": lpa.get("review-status", "unverified"),
        "audit-status": audit.get("status", "not-audited"),
        "issues-open": "" if audit.get("issues-open") is None else str(audit.get("issues-open")),
        "joint-list": "yes" if partners else "",
        "partners": ";".join(partners),
    })
    return row


def sync_lpa_csv(codes=None):
    """Rewrite data/lpa.csv rows (all, or just 'codes') from the _lpa.yaml files."""
    path = DATA / "lpa.csv"
    rows = {r["code"]: r for r in read_csv(path)}
    for code in (codes or list(rows)):
        if code in rows:
            rows[code] = lpa_csv_row(code, rows[code])
    write_csv(path, [rows[c] for c in sorted(rows)], LPA_COLUMNS)

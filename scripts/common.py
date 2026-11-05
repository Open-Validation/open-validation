"""Small helpers shared by the scripts in this folder.

Nothing clever here: where the folders are, how to read and write CSV and
YAML the same way every time, and how to pull a URL out of an Excel
=HYPERLINK(...) formula.
"""

import csv
import re
from pathlib import Path

import yaml

# The repo root is the folder above this "scripts" folder.
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPEC = ROOT / "specification" / "planning-requirement"
DEFINITIONS = SPEC / "definition"
INPUTS = ROOT / "inputs"
WORKBOOK = INPUTS / "grokbot_validation_requirements.xlsx"
AUDIT = INPUTS / "audit"
SCRIPTS = ROOT / "scripts"


# ---------- YAML ----------

def load_yaml(path):
    """Read one YAML file. Every file in this repo must load like this."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(data):
    """Turn data into YAML text in the house style (see FORMAT.md)."""
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def write_yaml(path, data):
    """Write data to a .yaml file, but only touch the file if it changed."""
    path = Path(path)
    text = dump_yaml(data)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


# ---------- CSV ----------

def read_csv(path):
    """Read a CSV file into a list of dictionaries (one per row)."""
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, columns):
    """Write a list of dictionaries to a CSV file with the given columns."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})


# ---------- Excel ----------

HYPERLINK = re.compile(r'=HYPERLINK\("([^"]*)"', re.I)


def link_url(cell):
    """Return the URL inside =HYPERLINK("url","text"), or a bare URL, else ''.

    Internal links such as #'Sheet'!A1 are ignored.
    """
    if not cell:
        return ""
    text = str(cell).strip()
    m = HYPERLINK.match(text)
    url = m.group(1) if m else text
    return url if url.startswith("http") else ""


def sheet_rows(ws):
    """Yield each data row of a sheet as a dict, using the row whose first
    cell is 'Council' as the header (it moves between sheets)."""
    header = None
    for row in ws.iter_rows(values_only=True):
        if header is None:
            if row and row[0] == "Council":
                header = [str(h).strip() if h else f"col{i}" for i, h in enumerate(row)]
            continue
        if row and row[0]:
            yield dict(zip(header, row))


# ---------- Reference data ----------

def requirement_ids():
    """All ids in data/planning-requirement.csv."""
    return {r["reference"] for r in read_csv(DATA / "planning-requirement.csv")}


def application_type_ids():
    """All ids in data/planning-application-type.csv."""
    return {r["reference"] for r in read_csv(DATA / "planning-application-type.csv")}


def lpa_folders():
    """Every council folder (anything in SPEC except 'definition')."""
    return sorted(p for p in SPEC.iterdir() if p.is_dir() and p.name != "definition")

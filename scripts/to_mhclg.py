"""Export our .yaml files back to MHCLG's Markdown format.

Run:  python scripts/to_mhclg.py <folder or file> [--out <folder>]

Examples:
  python scripts/to_mhclg.py specification/planning-requirement/SHR
  python scripts/to_mhclg.py specification/planning-requirement/site-plan.yaml --out export

Each file becomes '---' + YAML + '---' (+ the notes as Markdown body).
Our extra keys (source-url, must-include, review-status, ...) are dropped,
because MHCLG's model doesn't have them. _lpa.yaml files are skipped.
The output goes to export/ by default (not committed).
"""

import argparse
from pathlib import Path

from common import ROOT, dump_yaml, load_yaml

# Keys that are ours, not MHCLG's. Everything else is kept as it is.
OUR_KEYS = {
    "source-url", "policy", "source-text", "must-include", "confidence",
    "notes", "review-status", "field-status",
}


def to_markdown(data):
    """Return MHCLG-style Markdown text for one requirement."""
    notes = data.get("notes", "")
    kept = {k: v for k, v in data.items() if k not in OUR_KEYS}
    text = "---\n" + dump_yaml(kept) + "---\n"
    if notes:
        text += "\n" + f'"{notes}"' + "\n"
    return text


def export(path, out_dir):
    path = Path(path)
    files = [path] if path.is_file() else sorted(path.glob("*.yaml"))
    for f in files:
        if f.name == "_lpa.yaml":
            continue
        target = out_dir / f.parent.name / (f.stem + ".md") if path.is_dir() else out_dir / (f.stem + ".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(to_markdown(load_yaml(f)), encoding="utf-8")
        print("wrote", target.relative_to(ROOT) if target.is_relative_to(ROOT) else target)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", help="a folder of .yaml files or one .yaml file")
    p.add_argument("--out", default=str(ROOT / "export"), help="where to write the .md files")
    a = p.parse_args()
    export(a.path, Path(a.out))


if __name__ == "__main__":
    main()

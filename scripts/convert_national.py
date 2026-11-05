"""Convert MHCLG's national requirement files (.md with YAML front matter)
into our plain .yaml files.

Run:  python scripts/convert_national.py

It reads vendor/mhclg-spec/specification/planning-requirement/*.md and
definition/*.md (clone MHCLG's repo into vendor/mhclg-spec first, see README)
and writes specification/planning-requirement/<id>.yaml and definition/<name>.yaml.

The YAML between the two '---' lines becomes the file. Any Markdown text
after the second '---' goes into a 'notes:' key, so nothing is lost.
"""

from pathlib import Path

import yaml

from common import ROOT, SPEC, write_yaml

MHCLG = ROOT / "vendor" / "mhclg-spec" / "specification" / "planning-requirement"


def split_front_matter(text):
    """Split '---\\nyaml\\n---\\nbody' into (yaml data, body text)."""
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise ValueError("no front matter found")
    data = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return data, body


def tidy(data):
    """MHCLG sometimes leave keys blank (synonyms:) or as ''. Keep the key
    but make blanks consistent so the files read cleanly."""
    for key, value in list(data.items()):
        if value is None:
            data[key] = [] if key == "synonyms" else ""
    return data


def convert(md_path, out_path):
    data, body = split_front_matter(md_path.read_text(encoding="utf-8"))
    data = tidy(data)
    if body:
        # Body text is usually a quoted sentence; strip the quotes.
        data["notes"] = body.strip('"').strip()
    changed = write_yaml(out_path, data)
    print(("wrote   " if changed else "same    ") + str(out_path.relative_to(ROOT)))


def main():
    if not MHCLG.exists():
        raise SystemExit(
            "Can't find MHCLG's spec. Clone it first:\n"
            "  git clone https://github.com/digital-land/planning-application-data-specification vendor/mhclg-spec"
        )
    for md in sorted(MHCLG.glob("*.md")):
        convert(md, SPEC / (md.stem + ".yaml"))
    for md in sorted((MHCLG / "definition").glob("*.md")):
        convert(md, SPEC / "definition" / (md.stem + ".yaml"))
    print("Done. (Local examples such as CMD/ are rebuilt by build_from_workbook.py, not copied.)")


if __name__ == "__main__":
    main()

"""Print everything you need to write one council's corrections file.

Run:  python scripts/audit_extract.py CMD [--out <file.md>]
      python scripts/audit_extract.py CMD,SHR,... --out-dir <folder>   (one <CODE>.md each)

It shows, for the council:
  - its workbook rows (requirement, MHCLG id, sheet, trigger excerpt, notes, link)
  - the extra items on its own workbook tab (drawing standards, submission rules...)
  - the audit: current list link and date, summary, and every live issue with its
    final status and any claude_response (withdrawn issues are left out)
Then write scripts/audit_corrections/<CODE>.yaml (see the README in that folder).
"""

import argparse
import json

import openpyxl

from common import AUDIT, SCRIPTS, WORKBOOK, link_url, read_csv, sheet_rows


def tab_items(wb, tab_name):
    """Numbered items under each heading of a council's own tab."""
    if tab_name not in wb.sheetnames:
        return {}
    out, heading = {}, None
    for row in wb[tab_name].iter_rows(values_only=True):
        a, b = row[0], row[1] if len(row) > 1 else None
        if a and not b and isinstance(a, str) and not a.startswith("score"):
            heading = a.split(".")[0][:60]
        elif heading and b and str(a or "").isdigit():
            out.setdefault(heading, []).append(f"{str(b).strip()}  [{link_url(row[2]) if len(row) > 2 else ''}]")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("code", help="a council code, or several separated by commas")
    p.add_argument("--out", help="file to write (one council)")
    p.add_argument("--out-dir", help="folder to write <CODE>.md into (several councils)")
    a = p.parse_args()

    wb = openpyxl.load_workbook(WORKBOOK, read_only=True)
    sheets = [r["sheet"] for r in read_csv(SCRIPTS / "sheet_map.csv")]
    rows_by_council = {}
    for s in sheets:  # read every sheet once
        for r in sheet_rows(wb[s]):
            rows_by_council.setdefault(r["Council"], []).append((s, r))
    audits = {}
    for f in AUDIT.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        audits[d["council"]] = d
    codes = [c.strip() for c in a.code.split(",") if c.strip()]
    for code in codes:
        text = extract(code, wb, rows_by_council, audits)
        out = a.out if len(codes) == 1 and a.out else (f"{a.out_dir}/{code}.md" if a.out_dir else None)
        if out:
            open(out, "w", encoding="utf-8").write(text)
            print(f"Wrote {out}")
        else:
            print(text)


def extract(code, wb, rows_by_council, audits):
    """The Markdown summary for one council."""
    match = {r["code"]: r["workbook-name"] for r in read_csv(SCRIPTS / "lpa_match.csv") if r.get("code")}
    name = match[code]
    req_map = {r["workbook-name"]: r for r in read_csv(SCRIPTS / "requirement_map.csv")}

    lines = [f"# {code}: {name}", "", "## Workbook rows (18 application-type sheets)", ""]
    tab = None
    for s, r in rows_by_council.get(name, []):
        tab = tab or str(r.get("Council tab") or "")
        if r.get("Requirement") in (None, "(none)"):
            continue
        ids = req_map.get(r["Requirement"], {}).get("planning-requirement") or "UNMAPPED"
        lines += [f"- [{s}] **{r['Requirement']}** -> `{ids}`",
                  f"  - excerpt: {str(r.get('Trigger / when required (verbatim excerpt)') or '').strip()}",
                  f"  - notes: {r.get('Notes') or ''} | link: {link_url(r.get('Source document (link)'))}"]
    tab_name = tab.split('","')[-1].rstrip('")') if tab else ""
    lines += ["", f"## Council tab '{tab_name}'", ""]
    for heading, items in tab_items(wb, tab_name).items():
        lines.append(f"### {heading}")
        lines += [f"{i}. {t}" for i, t in enumerate(items, 1)]
        lines.append("")

    audit = audits.get(name)
    lines += ["## Audit", ""]
    if not audit:
        lines.append("No audit file.")
    else:
        for k in ("workbook_url", "workbook_list_date", "link_check", "current_url", "current_date",
                  "is_workbook_link_current", "current_evidence", "contents_checked", "contents_source",
                  "summary", "review_note"):
            if audit.get(k) not in (None, ""):
                lines.append(f"- **{k}**: {audit[k]}")
        lines += ["", "### Issues (live only)"]
        for n, i in enumerate(audit.get("issues", []), 1):
            lines.append(f"{n}. **{i['type']}** ({i.get('severity')}, {i.get('final_status')}): {i['detail']}")
            lines.append(f"   - evidence: {i.get('evidence', '')}")
            for k in ("claude_response", "grok_comment"):
                if i.get(k):
                    lines.append(f"   - {k}: {i[k]}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()

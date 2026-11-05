"""Print everything you need to write one council's corrections file.

Run:  python scripts/audit_extract.py CMD [--out <file.md>]

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
    p.add_argument("code")
    p.add_argument("--out")
    a = p.parse_args()

    match = {r["code"]: r["workbook-name"] for r in read_csv(SCRIPTS / "lpa_match.csv") if r.get("code")}
    name = match[a.code]
    req_map = {r["workbook-name"]: r for r in read_csv(SCRIPTS / "requirement_map.csv")}
    sheets = [r["sheet"] for r in read_csv(SCRIPTS / "sheet_map.csv")]
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True)

    lines = [f"# {a.code}: {name}", "", "## Workbook rows (18 application-type sheets)", ""]
    tab = None
    for s in sheets:
        for r in sheet_rows(wb[s]):
            if r["Council"] != name:
                continue
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

    audit = next((json.loads(f.read_text(encoding="utf-8")) for f in AUDIT.glob("*.json")
                  if json.loads(f.read_text(encoding="utf-8"))["council"] == name), None)
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
    text = "\n".join(lines) + "\n"
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"Wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()

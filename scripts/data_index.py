"""Rebuild data/local-planning-requirement.csv, the flat index of every requirement file.

You don't run this directly: python scripts/set_status.py --recompute does it.
"""

from datetime import date

from common import DATA, SPEC, load_yaml, read_csv, write_csv
import review

TODAY = date.today().isoformat()


def trigger_summary(rule):
    """Plain-English summary of a required-if rule, from its description lines."""
    if rule is None:
        return "see source-text"
    if rule == "discretionary":
        return "officer discretion"
    found = []

    def walk(x):
        if isinstance(x, dict):
            if x.get("always"):
                found.append("always")
            if "description" in x:
                found.append(str(x["description"]).strip())
            elif "ref" in x:
                found.append(str(x["ref"]).replace("-", " "))
            for k, v in x.items():
                if k not in ("description",):
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif x == "discretionary":
            found.append("other cases at officer discretion")
    walk(rule)
    return "; ".join(dict.fromkeys(found)) or "application type only"


def rebuild_index():
    path = DATA / "local-planning-requirement.csv"
    old = {(r["local-authority"], r["planning-requirement"], r["application-type"]): r.get("entry-date")
           for r in read_csv(path)} if path.exists() else {}
    rows = []
    for folder in sorted(p for p in SPEC.iterdir() if p.is_dir() and p.name != "definition"):
        for f in sorted(folder.glob("*.yaml")):
            if f.name == "_lpa.yaml":
                continue
            d = load_yaml(f)
            types = review.application_types(d.get("required-if")) or ["all"]
            for t in types:
                key = (folder.name, d["reference"], t)
                rows.append({"local-authority": folder.name, "planning-requirement": d["reference"],
                             "application-type": t, "trigger-summary": trigger_summary(d.get("required-if")),
                             "policy": d.get("policy", ""), "source-url": d.get("source-url", ""),
                             "confidence": d.get("confidence", ""), "review-status": d.get("review-status", ""),
                             "entry-date": old.get(key) or TODAY})
    write_csv(path, rows, ["local-authority", "planning-requirement", "application-type", "trigger-summary",
                           "policy", "source-url", "confidence", "review-status", "entry-date"])
    print(f"Rebuilt data/local-planning-requirement.csv ({len(rows)} rows)")

# Audit corrections

One file per council, `<CODE>.yaml`. It records what the council's audit
(`inputs/audit/<slug>.json`) says is wrong with Grokbot's workbook, in a form
`scripts/build_from_workbook.py` can apply. The audit is prose, so a person (or
Claude) reads it and writes this file. To see everything for one council:

    python scripts/audit_extract.py CMD

Then write `scripts/audit_corrections/CMD.yaml`, run
`python scripts/build_from_workbook.py --lpa CMD` and `python scripts/check.py`.

## Rules

- **Only use what the workbook or the audit says.** Never invent requirements,
  thresholds, `must-include` items or submission standards.
- **`source-text` is the council's own wording, verbatim**: a workbook excerpt,
  or words the audit quotes from the council's list (usually in `evidence`, in
  quotes). If you only have the audit's paraphrase, leave `source-text` out and
  put the paraphrase in `notes`, starting "From the audit: ...".
- Triggers (`required-if`) follow FORMAT.md. Use `ref: major-development` for
  "major applications", `site: {in: [...]}` for designations, `condition:` for
  thresholds, `discretionary` for "where appropriate / where relevant / with
  transport impacts". Fields must be MHCLG's or in `data/new-field.csv`; if you
  really need a new one, list it under `new-fields` (below).
- An issue whose `final_status` is `Open`: leave the rows as they are and add a
  `low-confidence` entry saying so.
- Where you can't tell which rows an issue affects, add a `low-confidence` entry
  with the issue in the note, rather than guessing.
- If the workbook text is a garbled run-on but the audit gives the right trigger,
  `replace` the requirement. If neither gives a usable trigger, keep the workbook
  text and add a `low-confidence` entry.

## Format (every key is optional except `local-authority`)

```yaml
local-authority: CMD

# The council's current list, if the audit found a newer/correct one.
# (build_from_workbook.py already uses the audit's current_url and current_date;
# only add this to correct or refine them.)
validation-list:
  url: https://...
  date: 2025-03          # as precise as the source allows: 2025, 2025-03 or 2025-03-14
  date-basis: "audit: LARs 2025 title page"

# Council-wide rules for every document (FORMAT.md). Only clear rules.
submission-standards:
  - item: Drawings to an identified metric scale, with a scale bar; plans with a north arrow
    level: must

# Workbook rows to throw away (not_a_requirement, duplicate, wrong placement).
drop:
  - id: photos                       # an MHCLG id the workbook row was mapped to
    sheets: [Advertisement consent]  # optional; leave out to drop the requirement entirely
    reason: "not_a_requirement: process text"

# Workbook items with no MHCLG id that should NOT go to unmapped-requirement.csv.
drop-unmapped:
  - local-name: Character / Conservation area appraisal reference
    reason: "not_a_requirement: cross-reference inside the heritage statement entry"

# Whole requirements, from the audit.
#   action: replace  - throw away the workbook's rows for this id and use this instead
#   action: add      - a missing requirement (missing_requirement); same as replace
#   action: update   - keep the workbook's file, but override the keys given here
requirements:
  - id: schedule-of-works
    action: replace
    required-if:
      application-type:
        in: [lbc]
    source-text: "Schedule of works - Listed building consent applications"
    source-url: https://...
    policy: "Local Plan D2"
    must-include:
      - item: ...
        level: must
    confidence: medium               # medium for audit-backed items; low if unsure
    notes: "Audit (wrong_trigger): the workbook quoted tree-survey text."

# Local items with no MHCLG id (they go to data/unmapped-requirement.csv).
unmapped:
  - local-name: Basement Impact Assessment
    source-text: "Basement Impact Assessment - developments including new or enlarged basements"
    source-url: https://...
    suggested-id: basement-impact-assessment

# Issues you couldn't resolve: these files get confidence: low and the note.
low-confidence:
  - id: noise-assessment             # or "*" for every file of this council
    note: "Audit (Open): ..."

# New fields used above that aren't in data/new-field.csv yet (kebab-case).
new-fields:
  - field: protected-view
    kind: designation                # designation | boolean | number
    label: In a protected view
    description: Site is in a protected view corridor.
```

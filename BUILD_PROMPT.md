# One prompt: build the open-validation repo, from empty to live

This single prompt replaces the old prompts 1, 2 and 3. It builds the data, the checks and the
explorer tool with the UK map. The submission pack (`4-submission-pack.md`) and form wizard
(`5-form-wizard.md`) are optional add-ons you can run afterwards.

**Before you paste it:**
1. Create an empty repo on GitHub called `open-validation` (public; no README, licence or
   .gitignore).
2. Open Claude Code on that repo.
3. Upload `open-validation-inputs.zip` from the project folder into the repo root. It holds
   Grokbot's workbook and the 328 audit files.
4. Paste everything below the line. Claude Code stops four times to show you something: the
   council-code matches, Shropshire and Camden, one region, and screenshots of the tool.

---

You are building a public data repo of **local planning validation requirements for every English
local planning authority (LPA)**, one folder per LPA, each holding one YAML file per
requirement. It must mirror the "planning requirements" part of MHCLG's planning application
data specification so the data could be contributed back to them. It ends with a browser tool,
published on GitHub Pages, with a colour-coded map of the UK and tables in which every cell
shows how far it has been verified, and a review mode for marking cells as verified.

The person you're working with is a Python novice. Keep scripts short, heavily commented and
runnable with `python scripts/<name>.py`. Python may use only the standard library plus
`pyyaml` and `openpyxl` (list them in `requirements.txt`). The web page uses plain HTML, CSS and
JavaScript with no build step; the only libraries allowed are js-yaml and d3, each from a
pinned CDN URL. At each checkpoint, explain what you did in plain English.

## 0. How to work

This is a long job in five stages (A to E). Before anything else:

- Save this whole prompt as `BUILD_PROMPT.md` in the repo root, and keep `BUILD_PROGRESS.md`
  with a ticked list of the stages and what's left. Update it at the end of every stage, so a
  new Claude Code session can pick up from it if this one runs out of room.
- Work on one branch, `build`. Commit in small logical steps. After stage A, open a **draft**
  pull request and keep pushing to it. Never push to `main`.
- Unzip `open-validation-inputs.zip` into `inputs/` (you should get
  `inputs/grokbot_validation_requirements.xlsx` and `inputs/audit/*.json`, 328 files), then
  delete the zip. Never edit anything in `inputs/`.
- If a download is blocked, stop and tell me the exact link to download by hand and where to
  put the file.
- At each **Checkpoint**, stop and wait for my OK.

---

## Stage A: skeleton, reference data, council folders and checks

### A1. Read MHCLG's model first

Clone https://github.com/digital-land/planning-application-data-specification into
`vendor/mhclg-spec/` (add `vendor/` to `.gitignore`). Read, in this order:

- `documentation/planning-requirements.md` (the model and its open questions)
- `specification/planning-requirement/*.md` (national requirement definitions)
- `specification/planning-requirement/definition/major-development.md` (reusable definition)
- `specification/planning-requirement/CMD/affordable-housing-statement.md` (Camden: the only local example)
- `data/planning-requirement.csv`, `data/national-planning-requirement.csv`, `data/planning-application-type.csv`

Record the commit hash you read in `README.md`.

**One deliberate difference:** MHCLG wrap YAML in Markdown front matter (`---` lines plus a
Markdown body). We use **plain `.yaml` files, no `---`, no Markdown**, so every file loads with
`yaml.safe_load(open(path))`. Always use the `.yaml` extension (never `.yml`). Keys are
identical to MHCLG's, so converting back is just wrapping in `---`. Any Markdown body text
goes into a `notes:` key.

### A2. Target layout (mirrors MHCLG's paths)

```
open-validation/
  README.md
  FORMAT.md                             # the rulebook (section A4)
  LICENSE                               # ask me: suggest CC BY 4.0 for data, MIT for code
  BUILD_PROMPT.md, BUILD_PROGRESS.md    # this prompt and your progress notes
  requirements.txt
  index.html                            # redirects to docs/
  data/
    planning-requirement.csv            # copied from MHCLG, unchanged
    planning-application-type.csv       # copied from MHCLG, unchanged
    national-planning-requirement.csv   # copied from MHCLG, unchanged
    lpa.csv                             # one row per LPA (A3)
    local-planning-requirement.csv      # flat index: LPA x requirement x application type
    unmapped-requirement.csv            # local items with no MHCLG id
    new-field.csv                       # fields and values we introduced (field, description, example)
  specification/
    planning-requirement/
      <requirement-id>.yaml             # national definitions, converted from MHCLG's .md
      definition/
        major-development.yaml
      <LPA-CODE>/                       # one folder per LPA, e.g. CMD/, SHR/
        _lpa.yaml                       # council metadata, list, audit and review status
        <requirement-id>.yaml           # one file per local requirement
  scripts/
    convert_national.py                 # MHCLG .md -> our .yaml (national + definition)
    to_mhclg.py                         # export any folder back to MHCLG's .md format
    build_from_workbook.py              # workbook + audit -> requirement files (stage B)
    review.py                           # shared rules: cell list, hash, roll-up (A6)
    set_status.py                       # mark cells as verified from the command line (A6)
    apply_reviews.py                    # apply marks submitted from the explorer (A6)
    build_map.py                        # boundary files -> docs/map/uk-lpa.geojson (stage C)
    check.py                            # integrity checks (A7)
    lpa_match.csv                       # workbook council -> LPA code
    requirement_map.csv                 # workbook requirement name -> MHCLG id (hand-editable)
    sheet_map.csv                       # workbook sheet -> application-type ids (hand-editable)
  inputs/                               # workbook + audit JSON (committed, never edited)
  reviews/
    pending/                            # cell marks waiting to be applied (one .yaml per submission)
    applied/                            # marks already applied, kept as a record
  docs/
    index.html                          # the explorer tool (stage D)
    evaluate.test.html
    STYLE.md
    map/uk-lpa.geojson
  .github/
    workflows/check.yml                 # runs check.py on every push and PR
    workflows/pages.yml                 # publishes to GitHub Pages
    workflows/apply-reviews.yml         # applies submitted cell marks on a pull request
    ISSUE_TEMPLATE/                     # forms for confirmations and corrections (stage D)
```

### A3. LPA codes, `lpa.csv` and `_lpa.yaml`

- Codes come from MHCLG's organisation dataset:
  `https://files.planning.data.gov.uk/organisation-collection/dataset/organisation.csv`
  (if moved, find the current organisation dataset on planning.data.gov.uk). The code is the
  part after `local-authority:`, e.g. `CMD`. National parks and development corporations have
  their own prefixes; use the code the same way. Also keep each council's ONS code (the
  `local-planning-authority` column, `E60...`; check the column name) for the map in stage C.
- Match each council in the workbook sheet `Councils reference` to a code by name (handle
  "Borough Council"/"BC", "&"/"and", "City of" etc.). Write matches to `scripts/lpa_match.csv`
  with a `match-method` column. **Print anything you can't match confidently and stop to ask.**
- **England only (328 councils).** MHCLG's spec covers England. Skip every council whose
  `Nation` in `Councils reference` isn't England (Scotland 34, Wales 25, Northern Ireland 11),
  and ignore any audit files for them. List the skipped councils in `README.md` as out of scope
  for now. (They still appear on the map, in grey as "Not covered yet".)
- **Every council gets a folder and an `_lpa.yaml`**, even if it has no requirement files yet.
- `lpa.csv` columns: `code, ons-code, name, region, type, validation-list-url, list-date,
  list-status, coverage, review-status, audit-status, issues-open, joint-list, partners,
  notes, entry-date`.

The workbook's header row is the one whose first cell is `Council` (find it, don't hard-code
it), and links are `=HYPERLINK("url","text")` formulas: extract the URL with a regex.
In stage A, fill `_lpa.yaml` and `lpa.csv` from the workbook only (`Councils reference` and
`Mergers & shared services`), with `audit.status: not-audited` and `review-status:
ai-collated` for everyone. Stage B applies the audit.

`_lpa.yaml`:
```yaml
local-authority: SHR
name: Shropshire Council
region: West Midlands
type: Unitary
review-status: ai-collated  # worked out from every cell in the folder (see FORMAT.md)
validation-list:
  url: https://...          # the CURRENT list per the audit, else the workbook's
  date: 2022-05-01
  date-basis: document text # copy the workbook's "Date basis"
  status: current           # current | outdated | not-found | national-only
submission-standards: []    # council-wide rules for every document (see FORMAT.md)
contact:                    # optional; blank until someone finds them on the council site
  planning-email: planning@...
  planning-phone: "0345 ..."
  fee-payment-url: https://...
joint-list:                 # only if the council shares a list
  partners: [TFW]
audit:
  status: audited           # audited | not-audited
  checked: 2026-11-05
  contents-checked: true
  workbook-link-current: false
  issues-open: 12
  notes: >
    One-paragraph summary from the audit.
field-status: {}            # one status per cell, written by scripts (see FORMAT.md)
```

### A4. `FORMAT.md` (the rulebook)

Copy the quoted block below, word for word (without the leading `>` marks), into `FORMAT.md`
at the repo root. You follow it in stage B, the tool follows it in stage D, and contributors
will too.

> #### Three different things in a validation list
>
> Councils' lists mix three things. Keep them apart:
> 1. **When a document is needed** goes in `required-if` in the requirement file (MHCLG's model).
> 2. **What a document must contain or show** goes in `must-include` in the requirement file.
>    This is our addition: MHCLG has no field for it, only a free-text `description`. Example:
>    a block plan must show visibility splays where a new access is proposed.
> 3. **Council-wide submission rules** that apply to every document, such as PDF only, maximum
>    file size, metric scale, A3/A4, file naming or no hand-drawn plans. These go in
>    `submission-standards` in the council's `_lpa.yaml`. They are not requirements, so don't
>    create requirement files for them, but don't throw them away either.
>
> #### Requirement file
>
> `specification/planning-requirement/<CODE>/<requirement-id>.yaml`. The filename must be an
> id from `data/planning-requirement.csv`. MHCLG's keys first, ours after:
>
> ```yaml
> reference: site-plan                      # MHCLG
> local-authority: SHR                      # MHCLG
> required-if:                              # MHCLG
>   application-type:
>     in: [hh, full, outline, reserved-matters]
> source-url: https://...                   # ours: where the council says it
> policy: "SAMDev MD2"                      # ours: local policy, if given
> source-text: >                            # ours: the council's wording, verbatim
>   ...
> must-include:                             # ours: what the document must contain or show
>   - item: Scale (typically 1:500) and north point
>     level: must                           # must | should ("should"/"advised"/"preferably" = should)
>   - item: Visibility splays and access layout
>     level: must
>     required-if:                          # optional; same rule syntax as below
>       condition:
>         field: new-vehicle-access
>         value: true
>         description: The proposal creates or alters a vehicle access.
>     source-text: "show the access layout and visibility splay"
> confidence: high                          # ours: high | medium | low
> notes: ""                                 # ours, optional: anything else
> review-status: ai-collated                # ours, worked out by scripts: see "Review status"
> field-status: {}                          # ours, written by scripts: one status per cell
> ```
>
> Write YAML with `yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)` so the
> key order matches the example. Quote operators (`">="`). Leave out optional keys that are empty.
>
> #### `must-include` rules
>
> - Only list what the council actually says the document must contain or show. Don't copy
>   general guidance about why a document is useful.
> - Local items add to any national `must-include`; they don't replace them. Don't repeat a
>   national item unless the council changes it, e.g. a different scale.
> - One item per distinct thing to check, written so a validation officer could tick it off.
> - Give an item its own `required-if` only if it applies just sometimes.
> - Never invent items. If the council's text doesn't list contents, leave `must-include` out.
>
> #### `submission-standards` (in `_lpa.yaml`)
>
> ```yaml
> submission-standards:
>   - item: All documents in PDF format
>     level: must
>   - item: Maximum file size 10 MB per file
>     level: must
>   - item: Drawings at an identified metric scale with a scale bar; not hand-drawn
>     level: must
> ```
>
> #### `required-if` rules: MHCLG's own constructs
>
> - `all:` (every item true), `any:` (at least one), nested freely.
> - `condition:` with `field`, optional `operator` (`>=`, `>`, `<=`, `<`, `==`; omit for
>   equals), `value`, and plain-English `description`.
> - `application-type: { in: [...] }` only when the requirement isn't for every type. Ids must
>   come from `data/planning-application-type.csv` (child types like `pa-storey` are allowed).
> - Major development: `- ref: major-development` (exactly as MHCLG's design-and-access-statement
>   does). Don't repeat the four thresholds.
> - Designations: `site: { in: [conservation-area, world-heritage-site], description: ... }`
>   (MHCLG's form). Value ids should follow planning.data.gov.uk dataset names
>   (`conservation-area`, `listed-building`, `flood-risk-zone`, `tree-preservation-zone`,
>   `site-of-special-scientific-interest`, `area-of-outstanding-natural-beauty`...). List any
>   you use in `data/new-field.csv`.
> - `always: true` when the council requires it for every application of the listed types.
> - Reuse MHCLG field names (`dwelling-count`, `site-area-residential`,
>   `site-area-non-residential`, `floorspace-non-residential`, `floorspace`,
>   `housing-floorspace`, `housing-type`). Any new field is kebab-case and goes in `new-field.csv`.
> - Vague triggers ("where appropriate", "officer discretion"): `required-if: discretionary`.
>   **Never invent thresholds.**
>
> #### Review status (cell by cell)
>
> Every piece of data we collected is a **cell**, and every cell has one of four statuses, from
> least to most trusted. The explorer shows each cell tinted in its status colour.
>
> | value | colour | meaning |
> |---|---|---|
> | `ai-collated` | red | Built by AI from Grokbot's workbook, Claude's audit or the ingest skill. Nobody has checked it against the council's list yet. Every cell starts here. |
> | `human-verified` | orange | A person compared the cell with the council's current list and it matches. |
> | `council-verified` | dark green | Someone at the council confirmed the cell is correct. |
> | `council-updated` | light green | The council has changed the cell itself (for example through a pull request or the "I work for this council" form), so the council now maintains it. |
>
> **The cells.** A requirement file has seven: `requirement` (that the council asks for this
> document at all), `application-type` (the types inside `required-if`), `required-if`,
> `must-include`, `policy`, `source-text` and `source-url`. A council's `_lpa.yaml` has six:
> `validation-list-url`, `validation-list-date`, `validation-list-status`,
> `submission-standards`, `contact` and `joint-list`. These are the columns of the explorer's
> tables. Columns that are worked out (status, issues open) or copied from MHCLG's register
> (name, region, type) are not cells and have no status.
>
> Statuses live in `field-status` at the end of each file:
>
> ```yaml
> review-status: human-verified       # worked out: the lowest of the cells
> field-status:
>   required-if:
>     status: human-verified
>     by: Jake White
>     date: 2026-11-06
>     hash: 3f2a9c1e                  # fingerprint of the cell's value when it was marked
>   source-text:
>     status: council-verified
>     by: Jake White
>     date: 2026-11-06
>     evidence: https://github.com/<owner>/open-validation/issues/12
>     hash: 9b04d7aa
> ```
>
> - A cell with no entry is `ai-collated`. An empty cell (for example no policy given) has no
>   status and doesn't count.
> - `council-verified` and `council-updated` need `evidence`: a link to the issue or PR, or a
>   short note of the email.
> - `hash` is the first 8 characters of the SHA-1 of the cell's value written as JSON
>   (`json.dumps(value, sort_keys=True, ensure_ascii=False)`). If the value changes after it
>   was marked, the hash stops matching and the cell drops back to `ai-collated`, so a mark can
>   never outlive an edit.
> - **Roll-up:** a file's `review-status` is the lowest status among its non-empty cells. A
>   council's `review-status` (in `_lpa.yaml`, in `lpa.csv` and on the map) is the lowest
>   among all non-empty cells in its folder, so one unchecked cell keeps the whole council at
>   that level.
> - **Coverage:** a council is `not-covered` (grey on the map, whatever its status) until we
>   have its requirements: that is, until its folder has at least one requirement file, or its
>   `validation-list.status` is `national-only` (we know it has no local list). Otherwise it
>   is `covered`. Councils outside England are always shown as not covered. Coverage is
>   worked out by scripts and stored in `lpa.csv`.
> - Only scripts write `review-status`, `field-status` and hashes. People mark cells with
>   `scripts/set_status.py` or the explorer's review mode; `check.py` fails if anything is out
>   of date.

### A5. National definitions

`scripts/convert_national.py`: convert MHCLG's national `.md` files and `definition/` into
`.yaml` (front matter becomes the file, any body text becomes `notes:`).
Also write `scripts/to_mhclg.py` (any folder back to MHCLG's `.md` format, dropping our extra
keys) and check it round-trips one national file.

### A6. Marking cells: `review.py`, `set_status.py`, `apply_reviews.py`

Put the rules from FORMAT.md's "Review status" in one small module, `scripts/review.py`: the
cell names, how to read each cell's value from a file, the hash, and the roll-up. The other
scripts and `check.py` import it, so the rules live in one place.

`python scripts/set_status.py SHR human-verified --by "Jake White" [--files site-plan,_lpa] [--cells required-if,source-text] [--evidence <url>]`

- Marks the named cells (every non-empty cell if `--cells` is left out) in the named files
  (every file in the folder, including `_lpa.yaml`, if `--files` is left out), with `by`,
  today's date and the hash.
- Refuses `council-verified` or `council-updated` without `--evidence`.
- Then recomputes the files' and the council's `review-status` and updates `lpa.csv`.
- `python scripts/set_status.py --recompute` changes no marks on purpose: it resets any cell
  whose hash no longer matches to `ai-collated` (listing them), then recomputes every file,
  council, coverage and `lpa.csv`.
- Prints what it changed in plain English.

`python scripts/apply_reviews.py` applies every file in `reviews/pending/`. Each one is a list
of marks written by the explorer's review mode (D5):

```yaml
- lpa: SHR
  file: site-plan          # or _lpa
  cell: required-if
  status: human-verified
  by: Jake White
  date: 2026-11-06
  evidence: ""             # required for the two council statuses
```

It checks every mark (real file, real cell, allowed status, evidence where needed), applies
them through `review.py`, moves the file to `reviews/applied/`, runs the recompute and prints
a summary. A bad mark stops it with a clear message and changes nothing.

`.github/workflows/apply-reviews.yml`: on a pull request from a branch in this repo that
touches `reviews/pending/`, run `apply_reviews.py` and `check.py`, then commit the result back
to the pull request branch, so the diff I review shows exactly which cells changed. For pull
requests from forks, only run the checks and say in the log that a maintainer must apply them.

### A7. `scripts/check.py` (also in CI)

Fail with a clear, plain-English message if:
- any `.yaml` doesn't parse, or any file uses `.yml` or contains `---`
- a filename (other than `_lpa.yaml`) isn't an id in `data/planning-requirement.csv`
- `reference` doesn't match the filename, or `local-authority` doesn't match the folder
- an `application-type` value isn't in `data/planning-application-type.csv`
- a `condition.field` or `site` value isn't an MHCLG field or listed in `data/new-field.csv`
  (including inside `must-include` items)
- `operator` isn't allowed, or a `ref:` doesn't exist in `definition/`
- a `field-status` key isn't a cell name, a status isn't one of the four values, a mark has
  no `by` or `date`, or a cell marked `council-verified` or `council-updated` has no
  `evidence`
- a cell's `hash` doesn't match its value (say which file and cell changed after it was
  marked, and to run `set_status.py --recompute`)
- a file's or council's `review-status` isn't the roll-up of its cells, a council's
  `coverage` is wrong, or `_lpa.yaml` and `lpa.csv` disagree
- a `must-include` or `submission-standards` item has no `item` or a `level` other than
  `must`/`should`
- a folder has no `_lpa.yaml`, or its code isn't in `data/lpa.csv` (and vice versa)

Then print a summary: LPAs, LPAs with no requirement files, requirement files, counts by
confidence, councils covered and not covered, counts of councils, files and cells by review
status, audited vs not-audited, and LPAs whose list is more than 2 years old (NPPF expects
local lists to be reviewed at least every 2 years).

Add `.github/workflows/check.yml` to run it on every push and pull request.

### A8. README

`README.md` for a non-programmer: what this is, the folder layout, how it maps to MHCLG's spec
(link + commit hash), the `.yaml`-not-Markdown difference, the four review statuses and their
colours, how cells are marked (command line or the explorer's review mode), how to add or
correct a council, and the caveat that everything is `ai-collated` until someone checks it
against the council's list.

**Checkpoint 1:** show me `scripts/lpa_match.csv` (anything unmatched or doubtful first), the
number of council folders (expect 328), one example `_lpa.yaml`, and the `check.py` summary.
Then open the draft pull request.

---

## Stage B: fill in every council's requirements

### B1. Reading the workbook (quirks)

- Sheets have title rows: the header row is the one whose first cell is `Council` (row 5 in
  the per-type sheets, row 4 in `Councils reference`). Find it, don't hard-code it.
- Link cells are formulas like `=HYPERLINK("https://...","text")`. Extract the URL with a
  regex. Ignore internal links (`#'Sheet'!A1`).
- Per-application-type sheets: `Householder` … `S106 modification`. Their columns are
  `Council, Region / Nation, Council type, Requirement, Trigger / when required (verbatim
  excerpt), Notes, List date, Outdated list?, Source document (link), Council tab`.
- Sheets after `S106 modification` are one tab per council. Inspect a few: if they hold more
  detail than the type sheets, use them for `source-text`; otherwise ignore them.
- `Mergers & shared services` tells you joint lists and reorganisations: use it for
  `joint-list` and `notes`.

Start `scripts/sheet_map.csv` like this, check every id against
`planning-application-type.csv`, and ask me about any you're unsure of:

| sheet | application-type ids |
|---|---|
| Householder | hh |
| Full planning | full |
| Outline | outline |
| Reserved matters | reserved-matters |
| Listed building consent | lbc |
| Advertisement consent | advertising |
| Lawful development cert | ldc |
| Change of use - prior approval | prior-approval; change-of-use |
| Demolition in cons area | demolition-con-area |
| Variation of condition s73 | s73 |
| Discharge of conditions | approval-condition |
| Non-material amendment | non-material-amendment |
| Works to trees | consent-under-tpo; notice-trees-in-con-area |
| Permission in principle | pip |
| Minerals & waste (county) | mineral-app; waste-dev |
| County own devt (Reg 3) | reg-3 |
| Hazardous substances | haz-substance-consent |
| S106 modification | mod-discharge-s106 |

### B2. The audit files

`inputs/audit/<slug>.json` holds Claude's audit of every English council's entry, checked
against the council's live site on 4-5 November 2026 and then reviewed by a second AI (Grok).
Fields:

- `council`, `workbook_url`, `workbook_list_date`, `link_check`, `current_url`,
  `current_date` (free text, e.g. "Last updated June 2020"), `current_evidence`,
  `is_workbook_link_current`, `contents_checked`, `contents_source` (sometimes), `summary`,
  `review_note` (sometimes: a correction made after the review).
- `issues[]`: the **live** issues only. Each has `type` (`outdated_link, wrong_document,
  wrong_date, missing_requirement, not_a_requirement, wrong_trigger, wrong_app_type,
  duplicate, other`), `severity`, free-text `detail` and `evidence`, plus `final_status`
  (`Confirmed`, `Amended`, `Kept`, `Stands` or `Open`), and sometimes `claude_response` and
  `grok_comment`. Where `claude_response` exists, it is the last word: it can narrow or
  correct the `detail` (for example a corrected date). Treat `Open` as unresolved: leave the
  affected rows as they are, set `confidence: low` and say so in `notes`.
- `withdrawn_issues[]`: issues that were withdrawn after the review. **Ignore them.**

### B3. `scripts/build_from_workbook.py`: the audit decides, the workbook gets corrected

1. Map each workbook `Requirement` name to an MHCLG id using names and `synonyms` from
   `planning-requirement.csv`. Save the mapping in `scripts/requirement_map.csv`
   (`workbook-name, planning-requirement, confidence`) so I can fix it by hand. Ignore rows
   for requirements with an `end-date` in the past; map them to their replacement if `notes`
   names one (e.g. acoustic-report -> noise-assessment). Unmatched names go to
   `unmapped-requirement.csv` (`local-authority, local-name, source-text, source-url,
   suggested-id`). **Never create new ids.**
2. Skip items that merely repeat national requirements (application form, location plan,
   fee, ownership certificate) unless the council adds a local trigger.
3. **Merge across sheets:** one council + one requirement = one file. Collect the application
   types from every sheet it appears in into one `application-type: in:` list. If the
   triggers differ by type, use `any:` with one `all:` block per type group.
4. **Apply the audit.** Issue `detail` is prose, so read it to work out which rows it
   affects; where that's unclear, leave the row as is, set `confidence: low` and record the
   issue in the file's `notes`.
   - drop `not_a_requirement` and `duplicate` rows
   - fix `wrong_app_type` and `wrong_trigger` from the audit's details
   - add `missing_requirement` items as new files (`confidence: medium`)
   - use the audit's `current_url` and date in `_lpa.yaml` for `outdated_link` /
     `wrong_document` / `wrong_date`. Extract a date from `current_date` where you can and
     keep the original wording in `validation-list.date-basis`.
   - put the audit `summary` (plus `review_note` if present) into `_lpa.yaml` `audit.notes`,
     and `len(issues)` into `audit.issues-open` and `lpa.csv` `issues-open`
   - `contents_checked: false` (70 councils whose sites blocked the audit): still build
     their requirement files from the workbook, but cap every file at `confidence: low`, set
     `audit.contents-checked: false` in `_lpa.yaml`, and list these councils in the
     checkpoint summary. Only write `_lpa.yaml` alone if the workbook has no rows for them.
5. **Councils with no audit file** (shouldn't happen, but keep the fallback): build from the
   workbook alone, set `audit.status: not-audited`, cap `confidence` at `low`, and add a note
   in `_lpa.yaml`. Re-running the script later, once an audit file exists, must upgrade them.
6. Workbook notes saying `INFERRED ... placed under Full planning` mean the type is a guess.
   The audit often says these lists are general and apply across application types: in
   that case leave `application-type` out (in MHCLG's model that means "all types"). If the
   audit doesn't say, also leave it out. Either way set `confidence: low`.
7. Garbled trigger excerpts: keep them in `source-text`, write no `required-if` beyond
   application type, `confidence: low`. Re-reading the council's own PDF is a later step,
   done one council at a time with the `lpa-requirements-ingest` skill.
8. `must-include` and `submission-standards`: fill them only where the workbook text or the
   audit clearly says what a document must show, or gives a council-wide rule (file format,
   size, scale, naming). Otherwise leave them out. Never invent them.
9. Councils on a joint list: each gets its own folder and files (copies), with `joint-list`
   naming the partners, so every folder stands alone.
10. Every file this script writes starts with `field-status: {}` (all cells `ai-collated`).
11. Write files, then rebuild `local-planning-requirement.csv` (`local-authority,
    planning-requirement, application-type, trigger-summary, policy, source-url,
    confidence, review-status, entry-date`) and run `set_status.py --recompute`.
12. Safe to re-run: **never change a cell that is marked above `ai-collated`** (you may still
    fill empty cells and update unmarked ones); take `--lpa SHR,CMD` to limit the run and
    `--dry-run` to only print what would change.

Skip any council not in `data/lpa.csv`. Run `python scripts/check.py` after every batch and fix
anything it reports before moving on.

**Checkpoint 2:** run for Shropshire (`SHR`) and Camden (`CMD`) only. Show me the files and a
table: council item, MHCLG id, application types, trigger, `must-include` count, confidence.
Wait for my OK.

**Checkpoint 3:** run for one region, show the summary from `check.py`, wait for my OK. Then
run everything, committing one region at a time.

---

## Stage C: map data

The explorer's home view is a map of the UK with every council coloured by its review status.

1. **Boundaries.** Preferred source: the ONS Open Geography Portal's latest "Local Planning
   Authorities ... Boundaries UK BUC" file (ultra-generalised, the whole UK in one file,
   national parks included as their own LPAs). Download it as GeoJSON into
   `inputs/boundaries/` and note the dataset name, date and URL in `README.md`. If the raw file
   is over 20 MB, add it to `.gitignore` instead of committing it. Fallback if that dataset
   can't be found: England from planning.data.gov.uk's `local-planning-authority` dataset
   (GeoJSON download) plus ONS "Local Authority Districts ... UK BUC" for the councils of
   Scotland, Wales and Northern Ireland. Either way, every council in the UK is drawn as its
   own area.
2. **`scripts/build_map.py`** (standard library only) writes `docs/map/uk-lpa.geojson`:
   - properties only `code` (our LPA code via `ons-code` in `lpa.csv`; blank outside
     England), `name` and `nation`
   - coordinates rounded to 4 decimal places and simplified with a short Douglas-Peucker
     function, so the file is under 2 MB
   - prints English councils in `lpa.csv` with no shape, and English shapes with no code
3. **Overlapping councils.** The 21 county councils (minerals and waste) and any development
   corporations overlap district councils, so don't draw them as areas. The tool lists them
   under the map with their status instead. Councils with no shape for any other reason join
   that list too.

Licence note: these boundaries are Open Government Licence. The page must show "Contains OS
data © Crown copyright and database right <year>" with the source.

---

## Stage D: the explorer tool (`docs/index.html`)

A single HTML page, published with GitHub Pages, that lets anyone see verification progress
on a UK map, browse the data by council and application type in tables where every cell shows
its review status, describe their site with toggle pills to see exactly what they need to
submit, and (for maintainers) mark cells as verified. Plain HTML, CSS and vanilla JavaScript
in one file. Must work on a phone.

**The page reads the YAML files themselves, live.** There is no copied or generated data
file (the map's GeoJSON is the only exception, because boundaries aren't requirement data):
the repo's YAML and CSV files are the only copy of the data, and the page fetches them when it
needs them, so a merged change shows up without rebuilding anything.

### D1. Loading the data

- GitHub Pages publishes the **whole repo** (not just `docs/`), so every file is available
  at the same address as the page, e.g. `./specification/planning-requirement/SHR/site-plan.yaml`.
  The page is `docs/index.html`; the root `index.html` redirects to it.
- Parse YAML in the browser with js-yaml, loaded from
  `https://cdn.jsdelivr.net/npm/js-yaml@4.1.0/dist/js-yaml.min.js`. Use d3 from
  `https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js` for the map projection and zoom only.
  Parse CSV with a ten-line function (no library).
- **On page load** fetch only: `data/lpa.csv` (council search and map colours),
  `docs/map/uk-lpa.geojson`, `data/planning-application-type.csv` (type dropdown),
  `data/planning-requirement.csv`, `data/national-planning-requirement.csv`,
  `data/new-field.csv` (pill labels) and `specification/planning-requirement/definition/*.yaml`.
- **When a council is chosen** fetch that council's `_lpa.yaml` and its requirement files.
  To know which files exist, use the GitHub API once per session
  (`GET https://api.github.com/repos/<owner>/<repo>/git/trees/main?recursive=1`, which lists
  every path in one call) and cache the result in `sessionStorage`. If that call fails (it is
  rate-limited to 60 an hour per visitor), fall back to trying each id from
  `planning-requirement.csv` and keeping the ones that exist. Fetch a council's files in
  parallel and cache them in memory, so switching back is instant.
- Show a small loading state while a council loads, and a clear message if the files can't
  be reached.
- For local testing, `python -m http.server` from the repo root must work (the page uses
  relative paths, so it needs no GitHub URL except the file-list call; read owner/repo from a
  single constant at the top of the script).

### D2. The map (home view)

Five tabs in the main panel: **Map**, **Councils**, **Results**, **Table**, **Browse files**.
Map is the default when no council is chosen; choosing a council switches to Results.

- Draw `uk-lpa.geojson` as SVG with a d3 projection fitted to the panel. Colour each council
  from `lpa.csv`:
  - **grey, "Not covered yet"**: any council whose `coverage` is `not-covered` (we don't have
    its requirements yet), and every council in Scotland, Wales and Northern Ireland (MHCLG's
    data standard is England-only). The tooltip says which of the two it is.
  - otherwise by `review-status`: `ai-collated` red, `human-verified` orange,
    `council-verified` dark green, `council-updated` light green.
- **Legend** with "Not covered yet" and the four statuses, a count of councils for each (the
  grey count split into "England" and "rest of the UK"), and a short line on what each means.
  Clicking a legend entry highlights those councils and dims the rest.
- Hover (or tap on a phone) shows a tooltip: council name, status, list date, and number of
  requirement files if known. Clicking a council selects it, exactly like the search box.
- Choosing a council from the search box zooms to it and outlines it on the map.
- Zoom and pan (scroll, pinch, drag), plus +, − and Reset buttons. London boroughs must be
  easy to pick when zoomed in.
- Under the map: the county councils and other councils without a shape, each as a small
  chip coloured the same way as the map (grey if not covered) that selects the council.
- A "List view" link opens the Councils tab (D5), which shows the same information as a
  table, for screen readers and anyone who prefers it.
- Colour must not be the only signal: the tooltip, legend and table always name the status in
  words, and a "Patterns" toggle in the legend adds a different texture per status (none,
  dots, diagonal lines, cross-hatch; grey stays plain) for colour-blind users.
- The OS/ONS attribution line sits under the map.

### D3. Picking and describing the site

**Pick (top bar):**
- **Council**: a search box with type-ahead over council names and codes (matches "Shrop",
  "SHR", "Shropshire Council"). Optional; with no council chosen, show national
  requirements only.
- **Application type**: a dropdown grouped by parent (e.g. Prior approval > pa-storey).
  Choosing a parent includes its children; choosing a child includes its parent's rules.

**Describe the site (toggle pills, under the top bar):**
- Yes/no pills for every `site` designation and yes/no field (In a conservation area, Listed
  building, Flood zone 2/3, TPO, AONB/National Landscape, SSSI nearby, Major development, New
  vehicle access...). Each pill cycles **unknown -> yes -> no**, shown clearly
  (outline / filled / struck through).
- Small number inputs for numeric fields (new homes, floorspace m², site area ha), shown
  as pills that expand when tapped.
- Work out the pills from the rules in the files actually loaded (including `required-if`
  inside `must-include` items), using `new-field.csv` for labels; any field without a label
  shows its kebab-case name tidied up. Only show pills for fields used by the current
  selection, most-used first, with "More" for the rest.
- A "Clear site" button.

### D4. Results

Each requirement evaluated against the site:
- **Required**: the rule is true.
- **Check**: the rule depends on a pill still set to unknown, is `discretionary`, or has
  no `required-if` (show which pill would settle it, as a tappable link to that pill).
- **Not required**: the rule is false. Collapsed by default.

Each result is a card: requirement name, plain-English trigger built from the rule's
`description` lines, **"What it must show"** (the `must-include` items that apply to this
site, `must` items as a checklist and `should` items marked "advised"; items whose own rule is
unknown are marked "Check"), the council's `source-text` (collapsible), policy, a link to the
council's list (`source-url`), a link to the YAML file on GitHub, and badges for `confidence`
and `review-status` (the status badge uses the map colour and always says the status in
words). Local rules show a "Local" badge; national ones "National".

**Council panel** (above the results when a council is chosen): review status with its
colour, list date and status (warn if older than 2 years), audit status and issues open,
joint-list partners, the council's **submission standards** as a short list, and a link to
the council's own validation list.

**Browse files tab:** the folder tree `specification/planning-requirement/<CODE>/...`
filtered by the same council and application type. Tapping a file shows its YAML,
syntax-highlighted with a few lines of CSS.

### D5. Tables and cell marking (how statuses move up)

**Two tables.** Both are drawn as a grid of thin white lines (D8), with a sticky header row and
first column, sortable columns, and their own sideways scroll on a phone (the page itself never
scrolls sideways).
- **Councils tab:** one row per council: council, region, type, status (worked out), validation
  list link, list date, list status, submission standards, contact, joint list, issues open.
  The first five come from `lpa.csv`; the rest come from each council's `_lpa.yaml`, fetched in
  batches of about 20 the first time the tab opens (with a progress bar) and cached for the
  session. Clicking a council's name selects it.
- **Table tab** (for the chosen council): one row per requirement file: requirement,
  application types, when required (the plain-English trigger), must show, policy, the
  council's wording (first line, expands on click) and source link.

**Every cell is tinted by its status**, in the same four colours as the map but washed out so
the text stays easy to read (D8). Worked-out and register columns, and empty cells, stay
untinted. The first column shows each row's rolled-up status as a small badge with the status
written in it. Above each table: a count of cells in each status, and a filter ("Show: all /
only red cells / ..."). The cell's status is also in its tooltip and in a visually hidden label
for screen readers.

**Review mode** (a switch in the header, for maintainers):
- On first use, ask for the reviewer's name and a GitHub fine-grained personal access token
  that can only reach this repo, with Contents and Pull requests set to read and write. Explain
  on screen how to make one, with a link to GitHub's token page. Keep the token in
  `sessionStorage` only (gone when the tab closes), send it only to `api.github.com`, and never
  log it or put it in a URL.
- In review mode, tapping any cell opens a small menu: the four statuses (colour and name), an
  evidence box (required for the two council statuses), and shortcuts "Mark the whole row" and
  "Mark every cell for this council". Changed cells show their new tint with a dashed outline,
  and a bar at the bottom says, for example, "12 cells marked: Submit / Discard". Pending marks
  are also kept in `localStorage` (never the token), so a refresh doesn't lose them.
- **Submit** creates a branch `review/<github-user>-<timestamp>`, adds one file
  `reviews/pending/<timestamp>-<github-user>.yaml` with the marks (format in A6) and opens a
  pull request titled, for example, "Cell marks: SHR (12 cells)". The page never edits the
  requirement YAML itself: `apply-reviews.yml` applies the marks on the pull request, and they
  show on the map and tables once I merge it.
- Without a token (any visitor), Submit opens a pre-filled GitHub issue with the same YAML
  (label `cell-marks`), which a maintainer saves into `reviews/pending/` and applies.

**Quick confirmations for everyone:**
- On every result card, "Checked against the council's site?" with two buttons: *Matches* and
  *Doesn't match*. Each opens a pre-filled GitHub issue (title, council code, requirement id,
  file path, site settings, and a box for what the council's site actually says), labelled
  `confirmed` or `correction`. No backend and no accounts of our own. Show on each card how
  many `confirmed` issues it has (one GitHub search API call per council, cached; skip
  quietly if rate-limited).
- In the council panel, an **"I work for this council"** link opens an issue form (label
  `council`) where a council officer can confirm the council's data is correct or send
  corrections.
- Add `.github/ISSUE_TEMPLATE/` forms for `confirmed`, `correction`, `council` and
  `cell-marks`. In `README.md`, explain how a maintainer turns them into statuses: a checked
  `confirmed` issue -> `human-verified`; a council confirmation -> `council-verified` with the
  issue as evidence; a council's corrections merged as a PR -> `council-updated`.

### D6. Other features

- Free-text filter over requirement names and synonyms ("tree" finds arboricultural report).
- Save all choices in the URL hash (`#lpa=SHR&type=hh&conservation-area=yes&dwelling-count=2`,
  plus `tab=map`) so a link reproduces the view. The back button works.
- "Copy checklist" copies the Required list, with each item's "must show" points and the
  council's submission standards, as plain text. Before it copies, ask the user to tick "I've
  checked this list against the council's own validation list", which links to that list.
- A footer disclaimer: draft data, always check the council's own list before submitting.
- Dark theme only (D8). Keyboard and screen-reader friendly: pills are
  `<button aria-pressed>`, table cells and the map's councils are focusable with a visible
  outline, and the review menu works from the keyboard.

### D7. Rule evaluator (in the page's JavaScript)

Write a small function `evaluate(rule, site, appType, definitions)` that returns `true`,
`false` or `"unknown"`, using three-valued logic:
- `all`: false if any item is false, else unknown if any is unknown, else true.
- `any`: true if any item is true, else unknown if any is unknown, else false.
- `condition`: compare `site[field]` with `value` using `operator` (equals if none);
  unknown if the site value is unset.
- `site: {in: [...]}`: true if any listed designation pill is yes; false if all are no;
  else unknown.
- `application-type: {in: [...]}`: true/false from the chosen type (including
  parent/child); unknown if no type is chosen.
- `ref: <name>`: evaluate `definitions[name]`. `major-development` can also be set
  directly by its pill.
- `always: true` -> true; `discretionary` or missing rule -> unknown.
- Anything unrecognised -> unknown, and log it to the console.

The same function decides which `must-include` items apply. Put a copy of the evaluator in
`docs/evaluate.test.html` with about 15 test cases (open in a browser, shows pass/fail),
covering each construct, a `must-include` item with its own rule, and the Camden affordable
housing example.

### D8. Visual style (write it down in `docs/STYLE.md`)

**Look:** a dark blueprint. Deep blueprint-navy background with a faint white squared-paper
grid, white linework, flat shapes, no gradients or shadows. Think "architect's drawing on
blueprint paper". Dark is the only theme. It must look independent: no GOV.UK crown, font,
black header or anything that could be mistaken for a council or government service.

**Colour (CSS variables on `:root`):**
- `--bg #0B1F3A` (page), `--surface #112B4E` (cards, panels, table cells),
  `--grid rgba(255,255,255,0.06)` (faint 24px page grid), `--line rgba(255,255,255,0.6)`
  (table grid lines), `--text #F2F6FB`, `--text-muted #A8BEDB`, `--accent #7FB2F0` (links,
  buttons, Required).
- **Tables:** every cell has a 1px `--line` border on all four sides, giving a thin white grid
  like a drawing schedule. Header row in semi-bold `--text` on `--bg`. No zebra stripes (the
  status tints do that job).
- Result status must not rely on colour alone: **Required** = solid `--accent` card edge and a
  filled tick icon; **Check** = amber `#F2B705` dashed edge and a "?" icon; **Not required** =
  muted outline and `--text-muted` text.
- **Review-status colours**, tuned for the dark background. Keep these four hues; check each
  is at least 3:1 against `--bg` and that dark and light green are easy to tell apart:
  `--status-ai #EF5350` (red), `--status-human #FB8C00` (orange), `--status-council #43A047`
  (dark green), `--status-updated #AED581` (light green), `--status-out #3A4A60` (grey, "Not
  covered yet": councils we have no requirements for, and everywhere outside England). Grey
  must be easy to tell apart from the dark-green and navy, so give it a thin `--line` border.
  - Map fills and status badges use the full colours.
  - **Table cells use washed-out tints of the same colours** so the text stays readable: the
    status colour at about 20% opacity over `--surface`, plus a 3px solid stripe of the full
    colour down the cell's left edge (so dark green still shows against navy). Text in tinted
    cells stays `--text`. Check every tint passes WCAG AA (4.5:1) with `--text`; if one fails,
    lower its opacity rather than changing the hue.
  - Orange sits close to the amber "Check" colour, so keep them apart: status colours appear
    only as map fills, cell tints and small solid badges with the status written in them, and
    "Check" is always a dashed card edge with a "?".
- Check every text/background pair meets WCAG AA contrast.

**Type:** Inter or IBM Plex Sans from Google Fonts (weights 400 and 600); IBM Plex Mono for
file names, YAML and table cells that hold codes. Large, plain headings.

**Shapes:** rounded pills (999px radius) for site toggles: white 1px outline when unknown,
filled `--accent` with `--bg` text when yes, struck-through `--text-muted` when no. Cards with
12px radius and a 1px `--line` border. Generous spacing.

**Illustrations:** a few small inline SVGs drawn as thin white line drawings, like linework on
a blueprint (e.g. a pin-up board with a site plan, a document stack, a phone for "pay the
council"). Use them only for the empty state, the loading state and the submission pack's
final screen. Draw them yourself as simple shapes; no stock images.

### D9. Publishing

`.github/workflows/pages.yml`: on push to `main`, run `scripts/check.py`, then deploy the
whole repo to GitHub Pages as it is (no build step). Tell me the one setting I need to switch
on (Settings > Pages > Source: GitHub Actions). Add a link to the tool at the top of
`README.md`.

**Checkpoint 4:** first mark a few of Shropshire's cells in each of the four statuses with
`set_status.py` on a throwaway branch (don't commit them to `build`). Then take screenshots at
phone and desktop width of: the map home view with the legend; the map zoomed into London; the
Councils tab; Shropshire's Table tab showing all four cell tints; review mode with a few
pending marks; Shropshire + Householder + conservation area on; Camden + Full + 12 new homes.
Show me before polishing further.

---

## Stage E: finish

- Run `check.py` one last time and paste its summary into `BUILD_PROGRESS.md`.
- Mark the pull request ready for review. Don't merge it yourself.
- End with a short plain-English summary: what you built, what's left (for example, councils
  still at `confidence: low`, councils with no shape on the map, unmapped requirements), and
  anything I must decide.

# FORMAT.md: the rulebook

How the data in this repo is written. Scripts, the explorer tool and contributors all follow it.

#### Three different things in a validation list

Councils' lists mix three things. Keep them apart:
1. **When a document is needed** goes in `required-if` in the requirement file (MHCLG's model).
2. **What a document must contain or show** goes in `must-include` in the requirement file.
   This is our addition: MHCLG has no field for it, only a free-text `description`. Example:
   a block plan must show visibility splays where a new access is proposed.
3. **Council-wide submission rules** that apply to every document, such as PDF only, maximum
   file size, metric scale, A3/A4, file naming or no hand-drawn plans. These go in
   `submission-standards` in the council's `_lpa.yaml`. They are not requirements, so don't
   create requirement files for them, but don't throw them away either.

#### Requirement file

`specification/planning-requirement/<CODE>/<requirement-id>.yaml`. The filename must be an
id from `data/planning-requirement.csv`. MHCLG's keys first, ours after:

```yaml
reference: site-plan                      # MHCLG
local-authority: SHR                      # MHCLG
required-if:                              # MHCLG
  application-type:
    in: [hh, full, outline, reserved-matters]
source-url: https://...                   # ours: where the council says it
policy: "SAMDev MD2"                      # ours: local policy, if given
source-text: >                            # ours: the council's wording, verbatim
  ...
must-include:                             # ours: what the document must contain or show
  - item: Scale (typically 1:500) and north point
    level: must                           # must | should ("should"/"advised"/"preferably" = should)
  - item: Visibility splays and access layout
    level: must
    required-if:                          # optional; same rule syntax as below
      condition:
        field: new-vehicle-access
        value: true
        description: The proposal creates or alters a vehicle access.
    source-text: "show the access layout and visibility splay"
confidence: high                          # ours: high | medium | low
notes: ""                                 # ours, optional: anything else
review-status: unverified                 # ours, worked out by scripts: see "Review status"
field-status: {}                          # ours, written by scripts: one status per cell
```

Write YAML with `yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)` so the
key order matches the example. Quote operators (`">="`). Leave out optional keys that are empty.

#### `must-include` rules

- Only list what the council actually says the document must contain or show. Don't copy
  general guidance about why a document is useful.
- Local items add to any national `must-include`; they don't replace them. Don't repeat a
  national item unless the council changes it, e.g. a different scale.
- One item per distinct thing to check, written so a validation officer could tick it off.
- Give an item its own `required-if` only if it applies just sometimes.
- Never invent items. If the council's text doesn't list contents, leave `must-include` out.

#### `submission-standards` (in `_lpa.yaml`)

```yaml
submission-standards:
  - item: All documents in PDF format
    level: must
  - item: Maximum file size 10 MB per file
    level: must
  - item: Drawings at an identified metric scale with a scale bar; not hand-drawn
    level: must
```

#### `required-if` rules: MHCLG's own constructs

- `all:` (every item true), `any:` (at least one), nested freely.
- `condition:` with `field`, optional `operator` (`>=`, `>`, `<=`, `<`, `==`; omit for
  equals), `value`, and plain-English `description`.
- `application-type: { in: [...] }` only when the requirement isn't for every type. Ids must
  come from `data/planning-application-type.csv` (child types like `pa-storey` are allowed).
- Major development: `- ref: major-development` (exactly as MHCLG's design-and-access-statement
  does). Don't repeat the four thresholds.
- Designations: `site: { in: [conservation-area, world-heritage-site], description: ... }`
  (MHCLG's form). Value ids should follow planning.data.gov.uk dataset names
  (`conservation-area`, `listed-building`, `flood-risk-zone`, `tree-preservation-zone`,
  `site-of-special-scientific-interest`, `area-of-outstanding-natural-beauty`...). List any
  you use in `data/new-field.csv`.
- `always: true` when the council requires it for every application of the listed types.
- Reuse MHCLG field names (`dwelling-count`, `site-area-residential`,
  `site-area-non-residential`, `floorspace-non-residential`, `floorspace`,
  `housing-floorspace`, `housing-type`). Any new field is kebab-case and goes in `new-field.csv`.
- Vague triggers ("where appropriate", "officer discretion"): `required-if: discretionary`.
  **Never invent thresholds.**

#### Review status (cell by cell)

Every piece of data we collected is a **cell**, and every cell has one of five statuses, from
least to most trusted. The explorer shows each cell tinted in its status colour.

| value | colour | meaning |
|---|---|---|
| `incorrect` | purple | Someone checked the cell against the council's list and found it wrong. A `note` says what's wrong. It is the lowest status, so the council shows purple on the map until it's fixed. |
| `unverified` | red | Nobody has checked it against the council's list yet. Most cells were collected by AI (from Grokbot's workbook, Claude's audit or the ingest skill). Every cell starts here. |
| `human-verified` | orange | A person compared the cell with the council's current list and it matches. |
| `council-verified` | dark green | Someone at the council confirmed the cell is correct. |
| `council-updated` | light green | The council has changed the cell itself (for example through a pull request or the "I work for this council" form), so the council now maintains it. |

**The cells.** A requirement file has seven: `requirement` (that the council asks for this
document at all), `application-type` (the types inside `required-if`), `required-if`,
`must-include`, `policy`, `source-text` and `source-url`. A council's `_lpa.yaml` has six:
`validation-list-url`, `validation-list-date`, `validation-list-status`,
`submission-standards`, `contact` and `joint-list`. These are the columns of the explorer's
tables. Columns that are worked out (status, issues open) or copied from MHCLG's register
(name, region, type) are not cells and have no status.

Statuses live in `field-status` at the end of each file:

```yaml
review-status: human-verified       # worked out: the lowest of the cells
field-status:
  required-if:
    status: human-verified
    by: Jake White
    date: 2026-11-06
    hash: 3f2a9c1e                  # fingerprint of the cell's value when it was marked
  source-text:
    status: council-verified
    by: Jake White
    date: 2026-11-06
    evidence: https://github.com/<owner>/open-validation/issues/12
    hash: 9b04d7aa
  policy:
    status: incorrect
    by: Jake White
    date: 2026-11-06
    note: The council's 2026 list cites policy DP4, not MD2
    hash: 51c0e8b2
```

- A cell with no entry is `unverified`. An empty cell (for example no policy given) has no
  status and doesn't count.
- `council-verified` and `council-updated` need `evidence`: a link to the issue or PR, or a
  short note of the email.
- `incorrect` needs a `note`: what's wrong, or what the council's list actually says. When
  someone fixes the value, the hash stops matching and the flag clears itself, so the cell goes
  back to `unverified` (fixed, but not yet checked). Every new `incorrect` flag that lands on
  `main` opens a GitHub issue that emails the maintainer.
- `hash` is the first 8 characters of the SHA-1 of the cell's value written as JSON
  (`json.dumps(value, sort_keys=True, ensure_ascii=False)`). If the value changes after it
  was marked, the hash stops matching and the cell drops back to `unverified`, so a mark can
  never outlive an edit.
- **Roll-up:** a file's `review-status` is the lowest status among its non-empty cells. A
  council's `review-status` (in `_lpa.yaml`, in `lpa.csv` and on the map) is the lowest
  among all non-empty cells in its folder, so one unchecked cell keeps the whole council at
  that level, and one `incorrect` cell shows the council as incorrect.
- **Coverage:** a council is `not-covered` (grey on the map, whatever its status) until we
  have its requirements: that is, until its folder has at least one requirement file, or its
  `validation-list.status` is `national-only` (we know it has no local list). Otherwise it
  is `covered`. Councils outside England are always shown as not covered. Coverage is
  worked out by scripts and stored in `lpa.csv`.
- Only scripts write `review-status`, `field-status` and hashes. People mark cells with
  `scripts/set_status.py` or the explorer's review mode; `check.py` fails if anything is out
  of date.

# open-validation

> **[Disclaimer](DISCLAIMER.md).** Draft open data from an independent, volunteer project, not a
> council or government service. It is collected by AI, then checked by volunteers, then (ideally)
> confirmed by councils; most of it has not been checked yet. It is provided "as is", without
> warranty, and as far as the law allows the maintainers, contributors and volunteer checkers are
> not liable for any loss, cost or delay from relying on it. **Always check the council's own
> validation list before you submit an application: it takes precedence over this data.**

**[Open the explorer tool](https://open-validation.github.io/open-validation/docs/)**: a UK map
of verification progress, every council's requirements in tables, and a checklist for your site.

Local planning **validation requirements for every English local planning authority (LPA)**, as
open data. A validation list says which documents a council needs before it will accept
("validate") a planning application. Every council publishes its own, in its own format. This repo
puts all 328 English councils' lists into one consistent format that computers can read.


## How it relates to MHCLG's data specification

The format mirrors the "planning requirements" part of MHCLG's
[planning application data specification](https://github.com/digital-land/planning-application-data-specification),
read at commit [`a3519413aa2a550471ae08af986e80b861c7c2d5`](https://github.com/digital-land/planning-application-data-specification/tree/a3519413aa2a550471ae08af986e80b861c7c2d5),
so the data can be contributed back to MHCLG.

- Same folder layout: national requirements in `specification/planning-requirement/`, each council's
  local rules in a folder named with its MHCLG code (e.g. `CMD/` for Camden, `SHR/` for Shropshire).
- Same keys (`reference`, `local-authority`, `required-if` with `all`, `any`, `condition`,
  `application-type`, `site`, `ref: major-development`, `always`).
- **One deliberate difference:** MHCLG write YAML inside Markdown front matter (between `---` lines).
  We use **plain `.yaml` files**, no `---` and no Markdown, so every file loads with
  `yaml.safe_load(open(path))`. Converting back is just wrapping in `---`:
  `python scripts/to_mhclg.py specification/planning-requirement/SHR`. Any Markdown body text is kept
  in a `notes:` key.
- Our additions (MHCLG have no field for them): `must-include` (what a document must show),
  `source-url`, `source-text`, `policy`, `confidence`, `review-status`, `field-status`, and
  `submission-standards` in each council's `_lpa.yaml`. They're all listed in `data/new-field.csv`.

The rules for writing the files are in **[FORMAT.md](FORMAT.md)**.

## Folder layout

| Path | What's in it |
|---|---|
| `specification/planning-requirement/<id>.yaml` | National requirement definitions, converted from MHCLG |
| `specification/planning-requirement/definition/` | Reusable definitions (e.g. `major-development`) |
| `specification/planning-requirement/<CODE>/_lpa.yaml` | One council: its list, audit and review status |
| `specification/planning-requirement/<CODE>/<id>.yaml` | One local requirement for that council |
| `data/lpa.csv` | One row per council (code, ONS code, list, coverage, review status...) |
| `data/local-planning-requirement.csv` | Flat index: council × requirement × application type |
| `data/unmapped-requirement.csv` | Local items with no MHCLG id yet |
| `data/new-field.csv` | Fields and values we introduced |
| `data/other-planning-authority.csv` | Development corporations: separate planning authorities inside or next to councils, and which councils they border (built by `build_map.py`; the explorer shows them as notes) |
| `data/organisation.csv` | Our copy of MHCLG's register of planning authorities (codes, names, ONS codes) |
| `data/planning-requirement.csv` etc. | Copied unchanged from MHCLG |
| `scripts/` | Short Python scripts (see below) |
| `inputs/` | Grokbot's workbook, Claude's audit files, boundary files. Never edited. |
| `reviews/pending/`, `reviews/applied/` | Cell marks waiting to be applied, and those already applied |
| `docs/` | The explorer tool (`docs/index.html`) and the map |

**Development corporations** decide planning applications in their own areas instead of the
council around them. Old Oak and Park Royal (`OPDC`, west London) has its own validation list, so it
has its own folder. (Grokbot's workbook labelled it "Greater London Authority"; the GLA itself doesn't
validate applications.) The others (Ebbsfleet, London Legacy, Oxford Street, Hartlepool and
Middlesbrough) aren't covered yet; the explorer notes them on the map and on the neighbouring councils.

Councils use MHCLG's three-letter codes. For national parks MHCLG's code is a Wikidata id
(e.g. Peak District is `Q72617988`), so we use the parks' own short names instead: `BROADS`, `DNPA`,
`ENPA`, `LDNPA`, `NFNPA`, `NYMNPA`, `NNPA`, `PDNPA`, `SDNPA`, `YDNPA`. The Wikidata id is kept in
`scripts/lpa_match.csv` (column `organisation`) so the data can be matched back to MHCLG's register.

## The five review statuses

Every piece of data is a **cell** (for example the trigger of one requirement, or a council's list
link), and every cell has one of five statuses. The explorer tints each cell in its colour.

| Status | Colour | Meaning |
|---|---|---|
| `incorrect` | purple | Someone checked it and found it wrong. A note says what's wrong. |
| `unverified` | red | Nobody has checked it against the council's list yet. Every cell starts here. |
| `human-verified` | orange | A person compared it with the council's current list and it matches. |
| `council-verified` | dark green | Someone at the council confirmed it is correct. |
| `council-updated` | light green | The council changed it itself, so the council now maintains it. |

A council is shown in the lowest status of any of its cells, and grey ("Not covered yet") until we
have its requirements. A mark remembers a fingerprint of the value it was given to; if the value is
edited later, the cell drops back to `unverified`. Fixing an `incorrect` cell clears its flag the
same way. Whenever a new `incorrect` flag lands on `main`, a GitHub Action opens an issue that
emails the repo owner.

### How cells are marked

- **Command line:** `python scripts/set_status.py SHR human-verified --by "Your Name"` (add
  `--files site-plan,_lpa` and `--cells required-if,source-text` to narrow it; the two council
  statuses also need `--evidence <link>`, and `incorrect` needs `--note "what's wrong"`).
- **Explorer review mode:** switch on "Review", tap cells, choose a status and press Submit. That
  opens a pull request adding a file to `reviews/pending/`; a GitHub Action applies the marks to the
  pull request so you can see exactly which cells change, and they go live when it's merged.
  Without a GitHub token, Submit opens an issue instead; save its YAML into `reviews/pending/` and
  run `python scripts/apply_reviews.py`.

### Publishing the explorer (GitHub Pages)

Use a computer's web browser (the GitHub phone app has no repository settings): open
https://github.com/Open-Validation/open-validation/settings/pages and, under **Build and deployment**,
set the **Source** drop-down to **GitHub Actions**. The `pages` workflow then publishes the site each time
`main` changes. If you prefer **Deploy from a branch**, choose `main` and `/ (root)`; the empty
`.nojekyll` file stops GitHub skipping files whose names start with `_` (such as `_lpa.yaml`).

### Merge rules for review mode

Marks submitted from the explorer arrive as a pull request. The `apply-reviews` workflow applies
them, then turns on auto-merge only if the person has write access, the batch is 50 cells or
fewer for one council, and it has no council statuses. Everything else waits for a maintainer.
One-off settings: **Settings → General → Allow auto-merge**, protect `main` so the `check`
workflow must pass, and add a repository secret **`REVIEW_BOT_TOKEN`** (a fine-grained token for
this repo with Contents: read and write) so the workflow's own commit re-runs the checks.

### Turning issues into statuses (for maintainers)

The explorer's buttons open GitHub issues from the forms in `.github/ISSUE_TEMPLATE/`:

- A **`confirmed`** issue ("Matches the council's site"): check it, then mark the cells
  `human-verified`.
- A **`correction`** issue: fix the file, then mark the corrected cells `human-verified`.
- A **`council`** issue where an officer confirms the data: mark the cells `council-verified` with
  the issue link as `--evidence`.
- A council's own corrections, merged as a pull request: mark those cells `council-updated` with the
  pull request link as evidence.
- **Right of reply:** once every cell for a council is `human-verified`, run
  `python scripts/right_of_reply.py` to draft an email to its planning team, send it, then record it
  with `--mark-sent CODE`. The council has 28 days to confirm (→ `council-verified`) or correct it.
- A **`cell-marks`** issue: save its YAML as `reviews/pending/<date>-<name>.yaml` and run
  `python scripts/apply_reviews.py`.

## How to fix or add data (the everyday routine)

**The council files are the data.** Each requirement is one small file in
`specification/planning-requirement/<CODE>/` (codes are in `data/lpa.csv`). There is no other copy:
to change something, you change that file. Nothing regenerates or overwrites it.

1. **Spot it.** In the explorer, if something is wrong, switch on Review, tap the cell, choose
   **Incorrect** and say what the council's list actually says. (You get an email; the cell turns purple.)
2. **Fix it.** Edit the council's file (on GitHub: open the file, pencil icon, commit to a new branch,
   open a pull request), following [FORMAT.md](FORMAT.md). Or ask Claude to do it. When the value
   changes, any "incorrect" flag on it clears itself.
3. **Check it.** The `check` workflow runs on the pull request. Locally:
   `python scripts/set_status.py --recompute` then `python scripts/check.py`.
4. **Verify it.** Once it matches the council's list, mark it **Human verified** in review mode.

A new requirement is a new file named after an id in `data/planning-requirement.csv`; if no id fits,
add a row to `data/unmapped-requirement.csv` instead.

**How the data was first built (history):** Grokbot's workbook (`inputs/`) was turned into council files
by `scripts/build_from_workbook.py`, applying each council's audit through
`scripts/audit_corrections/<CODE>.yaml`. That was a one-off: the script is now retired and refuses to
run unless given `--rebuild-from-workbook`, because regenerating would undo hand edits.

## Scripts

Install once: `pip install -r requirements.txt`. Then, from the repo root:

| Script | What it does |
|---|---|
| `python scripts/check.py` | Checks everything and prints a summary (also runs on every push) |
| `python scripts/set_status.py ...` | Marks cells; `--recompute` refreshes every status and the index `data/local-planning-requirement.csv` (run it after editing a file) |
| `python scripts/apply_reviews.py` | Applies marks waiting in `reviews/pending/` |
| `python scripts/right_of_reply.py` | Drafts emails to councils whose data is fully checked, so they can confirm or correct it; `--mark-sent CODE` records it |
| `python scripts/stale_lists.py` | Lists councils whose list is over 2 years old (a monthly Action keeps a `stale-lists` issue up to date) |
| `python scripts/new_incorrect_flags.py <commit>` | Lists cells newly flagged `incorrect` since a commit (used for the email alert) |
| `python scripts/update_register.py` | Checks MHCLG's register of planning authorities for new, abolished or renamed councils and updates `data/organisation.csv` (runs monthly; opens an issue if anything changed) |
| `python scripts/build_lpas.py` | Matches councils to MHCLG codes and creates new council folders (e.g. after the register adds one) |
| `python scripts/build_from_workbook.py` | *Retired.* Built the council files once from the workbook + audit |
| `python scripts/build_map.py` | Builds `docs/map/uk-lpa.geojson` from the boundary files |
| `python scripts/convert_national.py` | MHCLG's national `.md` files → our `.yaml` |
| `python scripts/to_mhclg.py <folder>` | Our `.yaml` → MHCLG's `.md` format |

To read MHCLG's spec locally: `git clone https://github.com/digital-land/planning-application-data-specification vendor/mhclg-spec`
(`vendor/` isn't committed).

## Sources

- **Grokbot's workbook** (`inputs/grokbot_validation_requirements.xlsx`, 4 Nov 2026): verbatim excerpts
  auto-extracted from council validation lists.
- **Claude's audit** (`inputs/audit/*.json`, 328 files): each English council's entry checked against
  its live website on 4-5 November 2026, then reviewed by a second AI (Grok).
- **Boundaries for the map**: ONS Open Geography Portal, *Local Planning Authorities (January 2026)
  Boundaries UK BUC (V2)* (ultra-generalised, clipped to the coastline; national parks are their own
  areas), saved as `inputs/boundaries/LPA_JAN_2026_UK_BUC_V2.gpkg`. Catalogue page:
  https://www.data.gov.uk/dataset/3f445e45-d0b8-4f34-a3aa-8d04f3e69307/local-planning-authorities-january-2026-boundaries-uk-buc.
  `python scripts/build_map.py` converts it to `docs/map/uk-lpa.geojson` (simplified, under 1 MB).
  Contains OS data © Crown copyright and database right 2026; Open Government Licence v3.0.
- **Council codes**: MHCLG's organisation register, saved in `data/organisation.csv` by
  `scripts/update_register.py` (from planning.data.gov.uk, or MHCLG's
  [organisation-collection](https://github.com/digital-land/organisation-collection) repo if that's
  unreachable). A GitHub Action checks it on the 3rd of each month. If anything changed (a
  merger, a rename, a new body, a new code) or the check couldn't run, it opens an issue labelled
  `register-change` that mentions the repo owner, so you get an email.

## Out of scope for now

MHCLG's specification covers England only, so councils in the rest of the UK are skipped. They
still appear on the map, in grey, as "Not covered yet".

- **Northern Ireland (11):** Antrim and Newtownabbey Borough Council, Ards and North Down Borough Council, Armagh City, Banbridge and Craigavon Borough Council, Belfast City Council, Causeway Coast and Glens Borough Council, Derry City and Strabane District Council, Fermanagh and Omagh District Council, Lisburn and Castlereagh City Council, Mid Ulster District Council, Mid and East Antrim Borough Council, Newry, Mourne and Down District Council
- **Scotland (34):** Aberdeen City Council, Aberdeenshire Council, Angus Council, Argyll and Bute Council, Cairngorms National Park Authority, City of Edinburgh Council, Clackmannanshire Council, Dumfries and Galloway Council, Dundee City Council, East Ayrshire Council, East Dunbartonshire Council, East Lothian Council, East Renfrewshire Council, Falkirk Council, Fife Council, Glasgow City Council, Highland Council, Inverclyde Council, Loch Lomond and The Trossachs National Park Authority, Midlothian Council, Moray Council, Na h-Eileanan Siar (Comhairle nan Eilean Siar) Council, North Ayrshire Council, North Lanarkshire Council, Orkney Islands Council, Perth and Kinross Council, Renfrewshire Council, Scottish Borders Council, Shetland Islands Council, South Ayrshire Council, South Lanarkshire Council, Stirling Council, West Dunbartonshire Council, West Lothian Council
- **Wales (25):** Blaenau Gwent Council, Brecon Beacons (Bannau Brycheiniog) National Park Authority, Bridgend Council, Caerphilly Council, Cardiff Council, Carmarthenshire Council, Ceredigion Council, Conwy Council, Denbighshire Council, Eryri (Snowdonia) National Park Authority, Flintshire Council, Gwynedd Council, Isle of Anglesey Council, Merthyr Tydfil Council, Monmouthshire Council, Neath Port Talbot Council, Newport Council, Pembrokeshire Coast National Park Authority, Pembrokeshire Council, Powys Council, Rhondda Cynon Taf Council, Swansea Council, Torfaen Council, Vale of Glamorgan Council, Wrexham Council

## Licence

Code: MIT ([LICENSE](LICENSE)). Data: CC BY 4.0 ([LICENSE-DATA.md](LICENSE-DATA.md)).

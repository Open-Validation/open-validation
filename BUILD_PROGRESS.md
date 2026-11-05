# Build progress

The full instructions are in `BUILD_PROMPT.md`. This file says where the build has got to, so a
new Claude Code session can pick up from here.

Working branch: `ccr-f743743a-pji9c0` (the session's designated branch, used instead of `build`).

## Stages

- [x] **A. Skeleton, reference data, council folders and checks**
  - MHCLG spec read at commit `a3519413aa2a550471ae08af986e80b861c7c2d5` (clone into `vendor/mhclg-spec`)
  - Council codes from MHCLG's organisation register, saved in `data/organisation.csv` by
    `scripts/update_register.py` (tries planning.data.gov.uk, falls back to MHCLG's GitHub;
    planning.data.gov.uk is blocked from the build machine). Monthly check: `.github/workflows/register.yml` fails on ANY change and opens a `register-change` issue mentioning @Open-Validation (email alert)
  - 328 English councils matched (`scripts/lpa_match.csv`: 326 exact, 2 by normalised name)
  - 328 folders with `_lpa.yaml`, `data/lpa.csv`, `FORMAT.md`, `review.py`, `set_status.py`,
    `apply_reviews.py`, `check.py`, workflows, README
  - [x] Checkpoint 1 approved: branch OK; national parks use short codes (BROADS, DNPA, ... YDNPA)
    instead of MHCLG's Wikidata ids (ids kept in lpa_match.csv `organisation`)
  - [x] Licence: MIT code + CC BY 4.0 data (confirmed); build_lpas.py kept as a separate script
- [ ] **B. Fill in every council's requirements** (`build_from_workbook.py`)
  - [ ] Checkpoint 2: SHR and CMD
  - [ ] Checkpoint 3: one region, then all regions (one commit per region)
- [ ] **C. Map data** (`build_map.py`, `docs/map/uk-lpa.geojson`)
- [ ] **D. Explorer tool** (`docs/index.html`, `evaluate.test.html`, `STYLE.md`, issue forms)
  - [ ] Checkpoint 4: screenshots
- [ ] **E. Finish** (final check summary here, PR ready for review)

## Decisions that change BUILD_PROMPT.md

`BUILD_PROMPT.md` is kept exactly as it was given. Where a later decision changes it, follow this list:

- The baseline review status is **`unverified`**, not `ai-collated` (same meaning and colour, red).
  It is used everywhere: FORMAT.md, scripts, data, and the explorer (CSS variable `--status-unverified`).
- National parks use short codes (BROADS, DNPA, ENPA, LDNPA, NFNPA, NYMNPA, NNPA, PDNPA, SDNPA, YDNPA).
- The council register lives in `data/organisation.csv` (refreshed by `scripts/update_register.py`), not `inputs/`.
- Working branch is `ccr-f743743a-pji9c0`, not `build`.

## Notes for whoever picks this up

- Inputs are in `inputs/`; never edit them.
- After any data change: `python scripts/set_status.py --recompute && python scripts/check.py`.

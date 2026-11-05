# Build progress

The full instructions are in `BUILD_PROMPT.md`. This file says where the build has got to, so a
new Claude Code session can pick up from here.

Working branch: `ccr-f743743a-pji9c0` (the session's designated branch, used instead of `build`).

## Stages

- [x] **A. Skeleton, reference data, council folders and checks**
  - MHCLG spec read at commit `a3519413aa2a550471ae08af986e80b861c7c2d5` (clone into `vendor/mhclg-spec`)
  - Council codes from MHCLG's organisation register (GitHub copy in `inputs/organisation/`,
    because files.planning.data.gov.uk is blocked from the build machine)
  - 328 English councils matched (`scripts/lpa_match.csv`: 326 exact, 2 by normalised name)
  - 328 folders with `_lpa.yaml`, `data/lpa.csv`, `FORMAT.md`, `review.py`, `set_status.py`,
    `apply_reviews.py`, `check.py`, workflows, README
  - [ ] Checkpoint 1 approved (licence: MIT code + CC BY 4.0 data proposed)
- [ ] **B. Fill in every council's requirements** (`build_from_workbook.py`)
  - [ ] Checkpoint 2: SHR and CMD
  - [ ] Checkpoint 3: one region, then all regions (one commit per region)
- [ ] **C. Map data** (`build_map.py`, `docs/map/uk-lpa.geojson`)
- [ ] **D. Explorer tool** (`docs/index.html`, `evaluate.test.html`, `STYLE.md`, issue forms)
  - [ ] Checkpoint 4: screenshots
- [ ] **E. Finish** (final check summary here, PR ready for review)

## Notes for whoever picks this up

- Inputs are in `inputs/`; never edit them.
- After any data change: `python scripts/set_status.py --recompute && python scripts/check.py`.

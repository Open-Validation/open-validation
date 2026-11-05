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
  - How it works: workbook rows -> requirement files; each council's audit (prose) is turned into
    `scripts/audit_corrections/<CODE>.yaml` (format: that folder's README), which the build applies.
    `python scripts/audit_extract.py <CODE>` prints everything needed to write one;
    `build_from_workbook.py --lpa <CODE> --validate` checks it without writing anything.
  - [x] Camden written by hand (the worked example)
  - [x] London (34) and South East (72) corrections written (12 parallel helpers, brief in the
    session scratchpad), synonym fields merged, built: 106 councils, 2669 files, check passes
  - [ ] Checkpoint 2: Camden + London + South East (shown to the user; waiting for OK)
  - [ ] Remaining regions: East Midlands, East of England, North East, North West,
    South West, West Midlands, Yorkshire and the Humber (222 councils), same method
  - Open questions for the user: GLA row is really OPDC (rename folder?); helpers added the
    national major-development branch to some local design-and-access-statement rules;
    requirements with no trigger show as "Check" in the explorer
- [ ] **C. Map data** (blocked: ONS boundary download needs the user; see README)
   (`build_map.py`, `docs/map/uk-lpa.geojson`)
- [ ] **D. Explorer tool** (`docs/index.html`; done so far: `evaluate.test.html` 26/26, `STYLE.md`, issue forms)
  - [ ] Checkpoint 4: screenshots
- [ ] **E. Finish** (final check summary here, PR ready for review)

## Decisions that change BUILD_PROMPT.md

`BUILD_PROMPT.md` is kept exactly as it was given. Where a later decision changes it, follow this list:

- The baseline review status is **`unverified`**, not `ai-collated` (same meaning and colour, red).
  It is used everywhere: FORMAT.md, scripts, data, and the explorer (CSS variable `--status-unverified`).
- National parks use short codes (BROADS, DNPA, ENPA, LDNPA, NFNPA, NYMNPA, NNPA, PDNPA, SDNPA, YDNPA).
- The council register lives in `data/organisation.csv` (refreshed by `scripts/update_register.py`), not `inputs/`.
- Working branch is `ccr-f743743a-pji9c0`, not `build`.
- A fifth status, **`incorrect`** (purple `#B388FF`, CSS `--status-incorrect`), sits below `unverified`.
  It needs a `note`. Fixing the value clears it (hash). It has its own texture in Patterns mode
  (horizontal lines) and a ✕ in table cells. Every new `incorrect` flag landing on `main` opens an
  `incorrect-flag` issue mentioning @Open-Validation (`incorrect-alert.yml` + `new_incorrect_flags.py`).
- Any change at all in MHCLG's register opens a `register-change` issue mentioning @Open-Validation (monthly).
- **Merge rules for review mode (build in stage D, apply-reviews.yml):**

  | Who | What | Merge |
  |---|---|---|
  | Contributor (write access) | Marks up to human-verified, down to unverified, or incorrect | auto if ≤ 50 cells and one council |
  | Contributor | Bigger batches | manual |
  | Registered council officer (public GitHub email on that council's own domain) | council-verified, own council only | auto |
  | Registered council officer | Data corrections (→ council-updated) | manual at first |
  | Anyone else | Anything | manual |

  Council officers register once via the tool; the register needs a per-council email domain list.
  Default until told otherwise: the maintainer approves each officer registration. Officers without
  GitHub use the "I work for this council" form (maintainer confirms by emailing the council address).
  Repo settings needed: Allow auto-merge; protect `main` requiring the `check` workflow.
- Lessons adopted from similar projects: (1) human-verified/incorrect marks record `checked-against`
  (list url + date, auto-filled); (2) `right_of_reply.py` drafts council emails and records
  `right-of-reply` in `_lpa.yaml`; (4) **stage D: Subresource Integrity hashes on the js-yaml and d3
  script tags, plus a Content-Security-Policy meta tag** (scripts only from self + cdn.jsdelivr.net,
  connect only to self + api.github.com); (5) monthly `stale-lists` issue (`stale_lists.py`).
  Deferred: no-account feedback form.
- Stage B scope changed by the user: build **Camden, all of London and the South East** (not SHR+CMD).
- Review mode signs in with a pasted fine-grained token (no backend). A "Sign in with GitHub" button
  (Cloudflare Worker) can be added later.

## Notes for whoever picks this up

- Inputs are in `inputs/`; never edit them.
- After any data change: `python scripts/set_status.py --recompute && python scripts/check.py`.

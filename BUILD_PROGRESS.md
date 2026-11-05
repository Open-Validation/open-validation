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
- [x] **B. Fill in every council's requirements** (`build_from_workbook.py`)
  - How it works: workbook rows -> requirement files; each council's audit (prose) is turned into
    `scripts/audit_corrections/<CODE>.yaml` (format: that folder's README), which the build applies.
    `python scripts/audit_extract.py <CODE>` prints everything needed to write one;
    `build_from_workbook.py --lpa <CODE> --validate` checks it without writing anything.
  - Camden written by hand (the worked example); the other 327 by parallel helpers (32 batches)
    following briefs in the session scratchpad; synonym fields merged after round 1.
  - Built one region per commit. Result: 328 councils, 7971 requirement files (4273 medium,
    3698 low), 316 covered, 12 not covered, 4694 unmapped local items; check.py passes.
  - Checkpoint 2 approved (user asked to do all remaining regions with 20 helpers).
  - Decided: the workbook's GLA row is OPDC; renamed to an `OPDC` folder (manual match in lpa_match.csv);
    development corporations are shown as notes on the map and neighbouring councils
    (`data/other-planning-authority.csv`).
  - Open questions for the user (defaults kept): some local
    design-and-access-statement rules repeat the national major-development branch;
    Central Lincolnshire: one audit says 2026 lists adopted 24 Aug 2026, two say 2024 still in force.
- [x] **C. Map data**: ONS LPA January 2026 BUC (V2) GeoPackage in `inputs/boundaries/`;
  `build_map.py` (+ `bng.py` for British National Grid) -> `docs/map/uk-lpa.geojson` (0.94 MB, 382 areas).
  8 councils matched by name because their ONS codes changed after new development corporations
  (update the register when planning.data.gov.uk is reachable). No shape: the 21 county councils.
- [x] **D. Explorer tool** (`docs/index.html`): map, councils, results, table, browse files, review
  mode, feedback issues, copy checklist, URL hash state, SRI + CSP; `evaluate.test.html` 26/26.
  After checkpoint 4 (user feedback): compact council panel; several application types
  (+ Add another type); site details in a Filter pop-up (most important questions first) with
  answer chips and inline Yes/No questions on Check cards; an "Applies to" column and tags worked
  out from each rule; notes for development corporations. Phone width checked.
  - Not built yet: council officer registration (officers use the "I work for this council" form).
- [x] **E. Finish**: final `check.py` below; pull request marked ready for review (not merged).

## Final check (`python scripts/check.py`)

```
Summary
  LPAs:                         328
  LPAs with no requirement files: 16
  Requirement files:            7971
  Files by confidence:          low: 3698, medium: 4273
  Councils by coverage:         covered: 316, not-covered: 12
  Councils by review status:    unverified: 328
  Files by review status:       unverified: 8299  (includes _lpa.yaml)
  Cells by review status:       unverified: 32959
  Audit:                        audited: 328
  Lists more than 2 years old:  136 (NPPF expects review at least every 2 years)
    ADU AMB ARU BAB BAI BBD BEN BEX BIR BOT BRA BRC BRM BRT BRX BUC CAN CBF CHE CHI CHL COL CON DBY DOV DUD EAS EDE EHA EPS ESK EXE FEN GAT GLS GOS GRA GRY HAA HAL HAV HER HIG HIL HIN HMF HNS HOR HRT HRW HRY HUN ISL KEC KHL KIR KTT LAC LAN LEE LEW LIF LIN LND LUT MAL MAN MAS MDB MSU NDE NEA NEC NET NEW NFK NGM NKE NLN NNPA NOW NSM NTY NUN NWA NWL NYMNPA NYUA OXO PEN POR PRE RCC RCH RDG REI ROC ROH RUG RUN SAL SAW SDNPA SGC SHE SHF SHO SHR SKP SND SOL SOS SOX SRY SST STF STS TAW TES THA THE TOB TOR UTT VAL WAE WAT WEW WGN WIN WLI WOC WOI WRT WSK WYR

All checks passed.
```

## What's left

- **Everything is `unverified`**: 32,959 cells wait for a person to check them against the
  council's list (explorer review mode or `set_status.py`).
- **Low confidence**: 3,698 of 7,971 requirement files. The audit couldn't read 70 councils' lists;
  64 councils have only low-confidence files.
- **Not covered (12)**: BAN, BNE, BRC, CAT, CHS, HAM, ISL, MOL, NLN, WAR, WLV, WSK (no local list
  found, or the audit couldn't read it and the workbook had nothing).
- **Unmapped**: 4,694 local items with no MHCLG id (`data/unmapped-requirement.csv`); the commonest are
  drainage strategy (268), structural survey (227), ventilation/extraction (175), landscape and visual
  impact (162), parking plan (158), heads of terms (146), health impact assessment (130). Candidates
  to propose to MHCLG.
- **No shape on the map**: the 21 county councils (shown as chips under the map). Six development
  corporations are drawn with notes; only OPDC is covered.
- **136 lists are more than 2 years old** (monthly `stale-lists` issue).
- **Register out of date**: 8 councils matched to the January 2026 boundaries by name because their
  ONS codes changed; run `update_register.py` where planning.data.gov.uk is reachable.
- **Repo settings to switch on** after merging: Settings > Pages > Source: GitHub Actions;
  Settings > General > Allow auto-merge; protect `main` (require `check`); repository secret
  `REVIEW_BOT_TOKEN`.
- **Open questions**: Central Lincolnshire (2026 lists adopted 24 Aug 2026, or 2024 still in force?);
  some local design-and-access-statement rules repeat the national major-development branch.

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

# The Receipts

Show the money behind politics — who funds every member of Congress, and what
that money buys. Audit-first: every number traces back to an FEC filing, and
the method for every column is written down in `methodology.md`.

## What you get by cloning

The finished dataset is already here: `congress-money-tracker.csv` /
`.json` — 664 people (the 119th Congress plus the incoming 120th), career
money, rankings, and 2026-cycle clean/dirty flags. You don't need to build
anything to explore it. The static site (`docs/index.html`) is generated from that dataset — see
"Static site" below — and is live at https://craigsochocki.github.io/the-receipts/ (GitHub Pages, publishing source `docs/` on `master`, enabled by Craig Nov 12, 2026).

## Quick start

```sh
git clone https://github.com/craigSochocki/the-receipts.git
cd the-receipts
python3 --version   # 3.10+, tested on 3.12
pip install -r requirements.txt  # installs the repo as a package, plus pyyaml, pandas, duckdb
```

Or run `./init.sh` — it does the venv, the bulk download, the rebuild, and the site in one go.

## Rebuild from scratch

One command rebuilds the committed dataset end to end:

```sh
python3 src/rebuild.py
```

It runs the full pipeline in order — `build_roster` → `apply_fec_lookup`
→ `build_store` → `accepted_money` → `pull_udp` → `pull_self_funding` →
`pull_other_committees` → `pull_all_ie` → `compute_opposition` →
`merge_dataset` → `compute_ranking` → `compute_2026` → `verify_dataset` —
and backs the current dataset up to
`data/snapshots/congress-money-tracker-pre-rebuild-<timestamp>.csv/.json` first.
It fails fast with a clear message if the FEC bulk data isn't staged,
or if the staged data is not the snapshot the baseline was recorded
from. Verified Nov 22, 2026: a fresh stage of `fec-bulk-2026-11-22` rebuilds
the committed dataset **byte-identically** on Python 3.11, 3.12 and
3.13, and every audit in `verify_dataset.py` passes.

### Pinned snapshots and the baseline

The FEC updates its bulk files **in place** — same URL, new contents —
so "rebuild from FEC bulk" means different inputs on different days.
The committed dataset is therefore tied to one **pinned snapshot**:

- A snapshot is an immutable GitHub Release (`fec-bulk-<date>`) made by
  the "FEC snapshot" workflow: the raw files exactly as the FEC served
  them, `SHA256SUMS`, and `PROVENANCE.tsv` (URL + Last-Modified).
- `./fetch_snapshot.sh` stages the snapshot named in
  `data/source/baseline.json` (`_snapshot`), verifying every checksum
  (about 315 MB down, ~1.7 GB on disk).
- `data/source/baseline.json` holds every data-dependent figure the
  pipeline checks itself against — roster totals, clean/tier counts,
  named spot cases, and what the public page says (`site.*`). No such
  figure is typed into a script any more (`src/common/baseline.py`).

**Accepting new FEC data** is a reviewed change, never an automatic one:

```sh
# 1. run the "FEC snapshot" workflow (Actions tab) -> new fec-bulk-<date> Release
./fetch_snapshot.sh fec-bulk-<date>
# 2. set data_as_of in config.yaml to that date, then
python3 src/rebuild.py --rebaseline   # records every figure, rebuilds + verifies the site
git diff data/source/baseline.json    # 3. the review: every figure that moved, old -> new
```

`./download_bulk.sh` still fetches the **live** FEC files (it skips
`oppexp`, which no script reads) — that is what the snapshot workflow
runs — but a live download is unpinned, and `src/rebuild.py` refuses to
check it against the baseline. See `research/bulk-inventory.md` for the
exact `curl` commands. The
full staged set including `oppexp` is 838 MB of zips, ~5.9 GB on disk
with the extracted files. Layout the scripts expect:
- `weball/weballYY.txt` (1980–2026), `cm/<cycle>/cm.txt`,
  `pas2/<cycle>/itpas2.txt`
- `ie/<cycle>/independent_expenditure_<cycle>.csv` (2022, 2024, 2026 only)

What each step does (each script documents its own rules in its header):
- `build_roster.py` — the 665-row roster from the vendored
  `data/source/legislators-*.yaml` files.
- `apply_fec_lookup.py` — enriches the roster with the committed
  `fec_lookup_results.json` (113 found, 7 found-manual, 1 not found) and
  the recorded manual notes in `data/source/manual_roster_notes.json`; writes
  `data/intermediate/roster_intermediate.json` and `data/intermediate/roster.json`.
- `store/build_store.py` — the silver store (DuckDB): every FEC candidate,
  committee and filing, with exclusions labeled rather than dropped.
- `store/accepted_money.py` — the roster's career money, read from the
  store with the recorded weball double-count removed
  (`data/source/dedup-applied.json`: $451,776,015.34, 32 persons, 90 groups,
  plus the Curtis 2024 extension to weball cols 6–9); also writes
  `data/intermediate/dedup-notes.json`.
- `pull_udp.py` — UDP independent-expenditure support; also writes the
  per-cycle breakdown `data/intermediate/money_udp_per_cycle.json`.
- `pull_self_funding.py` — self-funding + topline from weball
  (candidate contributions/loans, loan repayments, debts owed by,
  total receipts/disbursements, transfers, cash on hand);
  writes `data/intermediate/self_funding_per_cycle.json` / `data/intermediate/self_funding.csv`.
- `pull_other_committees.py` — other-committee contributions from
  pas2 + cm (party, leadership, labor, trade, membership, cooperative,
  unclassified + earmark breakouts); writes
  `data/intermediate/other_committees_per_cycle.json` / `data/intermediate/other_committees.csv`
  / `data/intermediate/other_committees_diagnostics.json`.
- `pull_all_ie.py` — ALL independent expenditures 2022–2026 (every
  registered committee, not just UDP), plus top 5 committees per person;
  writes `data/intermediate/all_ie_per_cycle.json` / `data/intermediate/all_ie.csv` /
  `data/intermediate/all_ie_top_committees.json`.
- `compute_opposition.py` — UDP opposition credit (exactly-one-backed
  rule); runs before the merge so its sanity check reads the current
  dataset.
- `merge_dataset.py` — roster + money + opposition → base dataset
  (collapses the duplicate Kristen McDonald Rivet rows).
- `compute_ranking.py` — total accepted + twelve rank columns.
- `compute_2026.py` — the 2026 columns, clean/dirty flags, and
  `data/intermediate/primary-targets.md` (House Democrats by dirty_2026).
- `verify_dataset.py` — the standing audits; exit non-zero on any
  mismatch. It checks the dataset against its own definitions — it
  cannot catch a missing money dimension (see its header).

Options: `python3 src/rebuild.py --with-fec-lookup` runs the live
OpenFEC lookup instead of the committed results (needs `FEC_API_KEY`;
default is the committed file, so no API key is needed to rebuild).
`--skip-verify` skips the final audit run.

## Freshness — new money since bulk coverage

The bulk rebuild is the canonical dataset; it only moves when the bulk
files move. Between bulk pulls, `src/ingest/pull_freshness.py` reports late money
(Form 6 48-Hour Notices, F24 24/48-hour independent expenditures, and the
candidate-totals refresh) into `data/intermediate/freshness_snapshot.json` — labeled by
source and date, **never merged into the dataset totals**. See
`methodology.md` §16 for the routes, the cadence (daily in the final 20
days before an election, weekly in-cycle, event-driven after deadlines),
and the verification run (Constantino's $1M Oct-29 loan; UDP vs El-Sayed
F24 $20,903,437.57).

```sh
# Limited spot check (DEMO_KEY-friendly, ~9 calls):
python3 src/ingest/pull_freshness.py --person anthonyconstantinonyhouse \
    --f24-committee C00799031 --f24-candidate abdulelsayedmisenate
```

A full refresh is ~2,200–2,350 keyed API calls (recounted Nov 12, 2026; see
`methodology.md` §16 and the driver's docstring) when run ungated
(`--no-gate`); by default `--all` is gated (`src/ingest/pull_gate.py` — one
global `/filings/` check per family first, legs only for people with new
filings), so a quiet week costs a handful of calls. DEMO_KEY (~30/hr) is spot-checks
only and the driver refuses `--all` on it. A bare `--all` also runs
committee-only F24 sweeps for the six config-listed spender committees
(`config.yaml`, `freshness.f24_committee_sweep`), so the scheduled run
covers the F24 leg. Production needs a registered
api.data.gov key (1,000 req/hr) via the `FEC_API_KEY` environment variable
(`config.yaml` `fec_api`, default `DEMO_KEY`). A registered key is set as
the `FEC_API_KEY` repository secret (added by Craig Nov 12, 2026; the
first scheduled run will confirm it by logging whether freshness ran or
skipped).

## Static site

`docs/index.html` is the tracker page as a static site, for GitHub Pages.
It is **generated, never hand-edited**: `src/site/build_site.py` reads
`congress-money-tracker.json` and emits the page with the dataset embedded
in a compact positional encoding (1.6 MB for 664 rows — column list +
array-of-arrays). Every view on the page (search, filters, sorting,
leaderboards, clean view, party breakdown, primary targets, CSV download)
is computed from that embedded data at runtime, so the page cannot drift
from the dataset. A data refresh regenerates the site with one command:

```sh
python3 src/site/build_site.py     # regenerate docs/index.html
python3 src/site/verify_site.py    # verify it against the dataset
```

`verify_site.py` decodes the embedded payload and checks it field-by-field
against the JSON (0 mismatches), recomputes the headline figures (664 rows;
clean True 98 / False 562 / None 4 (Luria unverified + 3 unopposed); incoming House
clean 70, Senate 14; top-10 total accepted; 192 primary targets; 53
career-clean House), syntax-checks the page JavaScript with `node --check`, serves `docs/` locally and checks it
returns 200, runs the Node runtime smoke test (`src/site/smoke_test.js` —
renders the table and every tab against a DOM stub, opens a drill-down,
exercises the CSV path), and checks the generator is deterministic apart
from the generation timestamp. Any failure exits non-zero.

To preview locally: `python3 -m http.server --directory docs 8000`, then
open http://localhost:8000. The site is live on GitHub Pages (publishing
source `docs/` on `master`). The page carries a visible "Data as of" stamp
— coverage end dates from `config.yaml` plus the build time — checked by
`verify_site.py`.

## Automation (GitHub Actions)

Two workflows in `.github/workflows/`:

- **`ci.yml` — CI on push and pull request to `master`.** Checks out the
  repo, sets up Python 3.12, installs `requirements.txt`, stages the
  **pinned** snapshot (`./fetch_snapshot.sh`), runs
  `python3 src/rebuild.py`, then **fails unless the rebuild reproduces
  the committed dataset byte-identically** (`git diff --exit-code` on
  `congress-money-tracker.csv` / `.json`), builds the site, **fails if
  the committed `docs/index.html` is not the rebuilt page** (timestamp
  aside), and runs `python3 src/site/verify_site.py`. No deploy step —
  GitHub Pages serves `docs/` on `master` automatically.
  `permissions: contents: read`. It needs no secrets, so it is safe to
  run on pull requests, including PRs from forks.
- **`fec-snapshot.yml` — manual.** Downloads the live FEC bulk files once
  and publishes them as an immutable `fec-bulk-<date>` Release (raw
  files + `SHA256SUMS` + `PROVENANCE.tsv`). It does not touch the dataset.
- **`scheduled-refresh.yml` — PAUSED (manual dispatch only).** It never
  completed: it rebuilt from a live download, and any new filing moved
  the totals the pipeline checks itself against, so both scheduled runs
  (Nov 15 and Nov 22, 2026) failed and committed nothing. Its planned
  replacement automates the reviewed path above — snapshot, rebaseline,
  open a pull request — and never pushes to `master` directly. The
  rest of this section describes the paused workflow as written.

**Failure behavior.** A failed rebuild or verify commits nothing and
pushes nothing: the commit step is gated on the earlier steps succeeding
(`if: success()`), so a bad run leaves the committed dataset and site
untouched. In CI the same failure fails the run.

**Commit gate (scheduled refresh only).** The dataset counts on any diff.
The site counts only on a content change: the generation timestamp line
("Generated YYYY-MM-DD HH:MM UTC") is ignored via `git diff -I`, using
the same pattern `verify_site.py` strips in its determinism check — so a
timestamp-only rebuild commits nothing and a no-change run is a no-op.

**Pinned, not cached.** CI downloads the pinned snapshot Release on every run and verifies every sha256 — the inputs are identified by content, so there is nothing to go stale. The paused scheduled refresh re-downloads the live files with `./download_bulk.sh`.

**FEC API key (`FEC_API_KEY` secret) — optional.** The freshness step
(`python3 src/ingest/pull_freshness.py --all`, ~45–60+ minutes for ~2,200–2,350
keyed API calls at an effective 1.0 s/call) runs **only** when the
`FEC_API_KEY` repository secret is set. When it runs, the snapshot
(`data/intermediate/freshness_snapshot.json`) is uploaded as a workflow
artifact (90-day retention) — it is never merged into dataset totals and
never committed. When the secret is absent, the step logs `SKIP: freshness
refresh not run — FEC_API_KEY secret is not set.` and the run continues
without it. The key is set: Craig registered at api.data.gov and added it
as the `FEC_API_KEY` repository secret Nov 12, 2026 (repo Settings →
Secrets and variables → Actions; rotate it there if it ever leaks or
expires). The first scheduled run will confirm it by logging whether
freshness ran or skipped. Everything else — CI, the scheduled rebuild, the
commit-back — works without it. The scheduled run covers the F24 leg via
the six committee sweeps (`config.yaml`, `freshness.f24_committee_sweep`);
the first live confirmation is the Sunday Nov 15, 2026 run.

**Rate limit — the freshness step can fail on 429, and that no longer blocks the
deploy.** A standard registered api.data.gov key allows 1,000 requests/hour, but a
full `--all` freshness run makes ~2,200–2,350 calls in ~45–60 minutes, so it hits
HTTP 429 (`OVER_RATE_LIMIT`) roughly 25 minutes in. The fetch helpers retry a 429 —
honoring `Retry-After` when present, otherwise exponential backoff up to a cap —
and fail loudly naming the limit and the raise path if the wait exceeds budget. A
raise to 120 calls/min (7,200/hour) has been requested from apiinfo@fec.gov and is
pending, not granted. In the scheduled workflow the freshness step is non-blocking
(`continue-on-error`): if it fails, the dataset/site rebuild and commit-back still
proceed, and that run's freshness snapshot is simply absent or partial. See
`methodology.md` §16 for the full account.

**Where to watch runs:** the repo's Actions tab —
https://github.com/craigSochocki/the-receipts/actions.

## Configuration

`config.yaml` at the repo root is the single source of truth for committee
IDs, cycles, paths, thresholds, and API settings. Change values there, never
in the scripts. Scripts resolve all paths relative to the repo, so a checkout
works from any directory on any machine.

## Layout

- `congress-money-tracker.csv` / `.json` — the dataset
- `methodology.md` — definitions, sources, and every known limitation
- `architecture.md` — design, data model, North Star, and the gaps
- `STATUS.md` — where the build stands right now
- `src/` — pipeline code, staged: `common/` (config loader), `ingest/`
  (pulls from FEC bulk + API), `transform/` (roster, dedup, merge,
  ranking, 2026 columns), `validate/` (standing audits), `rebuild.py`
  (the one command that runs it all)
- `data/source/` — committed true inputs: legislators yaml, dedup record,
  manual roster notes, FEC lookup results
- `data/intermediate/` — regenerable staging files, **not committed**
  (gitignored; `src/rebuild.py` recreates them all)
- `data/snapshots/` — dated dataset states (pre-rank, pre-opposition, …)
- `data/evidence/` — one-off API dumps from spot checks
- `research/` — pull logs, verification notes, source research
- `data/raw/` — staged FEC bulk data, **not committed** (gitignored, ~6 GB,
  re-downloadable from fec.gov — see `research/bulk-inventory.md`)
- `docs/` — the generated static site (`index.html`, from
  `src/site/build_site.py`; never hand-edited)
- `src/site/` — site generator (`build_site.py`), verifier
  (`verify_site.py`), runtime smoke test (`smoke_test.js`)

## Ground rules

- One change per commit, each scoped to a single bit of functionality.
- FEC filings are the source of truth; OpenSecrets is the cross-check.
- Never blend AIPAC PAC direct money with UDP independent expenditures into
  one number — they are separate columns by design.

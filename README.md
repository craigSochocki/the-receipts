# The Receipts

Show the money behind politics — who funds every member of Congress, and what
that money buys. Audit-first: every number traces back to an FEC filing, and
the method for every column is written down in `methodology.md`.

## What you get by cloning

The finished dataset is already here: `congress-money-tracker.csv` /
`.json` — 664 people (the 119th Congress plus the incoming 120th), career
money, rankings, and 2026-cycle clean/dirty flags. You don't need to build
anything to explore it. The static site (`docs/index.html`, served by
GitHub Pages once Craig enables it) is generated from that dataset — see
"Static site" below.

## Quick start

```sh
git clone https://github.com/craigSochocki/the-receipts.git
cd the-receipts
python3 --version   # 3.10+, tested on 3.12
pip install pyyaml  # the only dependency
```

## Rebuild from scratch

One command rebuilds the committed dataset end to end:

```sh
python3 src/rebuild.py
```

It runs the full pipeline in order — `build_roster` → `apply_fec_lookup`
→ `pull_money` → `pull_udp` → `apply_dedup` → `pull_self_funding` →
`pull_other_committees` → `pull_all_ie` → `compute_opposition` →
`merge_dataset` → `compute_ranking` → `compute_2026` → `verify_dataset` —
and backs the current dataset up to
`data/snapshots/congress-money-tracker-pre-rebuild-<timestamp>.csv/.json` first.
It fails fast with a clear message if the FEC bulk data isn't staged.
Verified Nov 12, 2026: a fresh clone with staged bulk data rebuilds the
committed dataset **byte-identically** (both files, same md5s), and
`verify_dataset.py` passes all 93 standing audits.

Prerequisite: the FEC bulk files staged under `data/raw/` — the scripts
read them, they don't download them. Run `./download_bulk.sh` (about
315 MB down, ~2 GB on disk — it skips `oppexp`, which no script reads),
or see `research/bulk-inventory.md` for the exact `curl` commands. The
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
- `pull_money.py` — career money from weball + pas2 + cm.
- `pull_udp.py` — UDP independent-expenditure support; also writes the
  per-cycle breakdown `data/intermediate/money_udp_per_cycle.json`.
- `apply_dedup.py` — applies the recorded weball double-count dedup
  (`data/source/dedup-applied.json`: $451,776,015.34, 32 persons, 90 groups,
  plus the Curtis 2024 extension to weball cols 6–9);
  writes `data/intermediate/dedup-notes.json`.
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

A full refresh is ~1,300+ API calls; DEMO_KEY (~30/hr) is spot-checks
only and the driver refuses `--all` on it. Production needs a registered
api.data.gov key (1,000 req/hr) via the `FEC_API_KEY` environment variable
(`config.yaml` `fec_api`, default `DEMO_KEY`). No registered key exists in
the repo yet.

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
clean True 84 / None 1; incoming House clean 67, Senate 10; top-10 total
accepted; 192 primary targets; 53 career-clean House), syntax-checks the
page JavaScript with `node --check`, serves `docs/` locally and checks it
returns 200, runs the Node runtime smoke test (`src/site/smoke_test.js` —
renders the table and every tab against a DOM stub, opens a drill-down,
exercises the CSV path), and checks the generator is deterministic apart
from the generation timestamp. Any failure exits non-zero.

To preview locally: `python3 -m http.server --directory docs 8000`, then
open http://localhost:8000. GitHub Pages is the publishing source
(`docs/`); enabling Pages in repo Settings → Pages is Craig's step — the
site is not public until he does that.

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

# The Receipts

Show the money behind politics — who funds every member of Congress, and what
that money buys. Audit-first: every number traces back to an FEC filing, and
the method for every column is written down in `methodology.md`.

## What you get by cloning

The finished dataset is already here: `congress-money-tracker.csv` /
`.json` — 664 people (the 119th Congress plus the incoming 120th), career
money, rankings, and 2026-cycle clean/dirty flags. You don't need to build
anything to explore it. The tracker web page itself is not built from this
repo yet — that's a known gap, see `architecture.md`.

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
python3 work/rebuild.py
```

It runs the full pipeline in order — `build_roster` → `apply_fec_lookup`
→ `pull_money` → `pull_udp` → `apply_dedup` → `compute_opposition` →
`merge_dataset` → `compute_ranking` → `compute_2026` → `verify_dataset` —
and backs the current dataset up to
`work/congress-money-tracker-pre-rebuild-<timestamp>.csv/.json` first.
It fails fast with a clear message if the FEC bulk data isn't staged.
Verified Nov 12, 2026: a fresh clone with staged bulk data rebuilds the
committed dataset **byte-identically** (both files, same md5s), and
`verify_dataset.py` passes all 37 standing audits.

Prerequisite: the FEC bulk files staged under `work/bulk/` — the scripts
read them, they don't download them. See `work/bulk-inventory.md` for the
exact `curl` commands. About 838 MB of zips, ~5.9 GB on disk with the
extracted files. Layout the scripts expect:
- `weball/weballYY.txt` (1980–2026), `cm/<cycle>/cm.txt`,
  `pas2/<cycle>/itpas2.txt`
- `ie/<cycle>/independent_expenditure_<cycle>.csv` (2022, 2024, 2026 only)

What each step does (each script documents its own rules in its header):
- `build_roster.py` — the 665-row roster from the vendored
  `work/legislators-*.yaml` files.
- `apply_fec_lookup.py` — enriches the roster with the committed
  `fec_lookup_results.json` (113 found, 7 found-manual, 1 not found) and
  the recorded manual notes in `work/manual_roster_notes.json`; writes
  `work/roster_intermediate.json` and `work/roster.json`.
- `pull_money.py` — career money from weball + pas2 + cm.
- `pull_udp.py` — UDP independent-expenditure support; also writes the
  per-cycle breakdown `work/money_udp_per_cycle.json`.
- `apply_dedup.py` — applies the recorded weball double-count dedup
  (`work/dedup-applied.json`: $451,776,015.34, 32 persons, 90 groups);
  writes `work/dedup-notes.json`.
- `compute_opposition.py` — UDP opposition credit (exactly-one-backed
  rule); runs before the merge so its sanity check reads the current
  dataset.
- `merge_dataset.py` — roster + money + opposition → base dataset
  (collapses the duplicate Kristen McDonald Rivet rows).
- `compute_ranking.py` — total accepted + seven rank columns.
- `compute_2026.py` — the 2026 columns, clean/dirty flags, and
  `work/primary-targets.md` (House Democrats by dirty_2026).
- `verify_dataset.py` — the standing audits; exit non-zero on any
  mismatch. It checks the dataset against its own definitions — it
  cannot catch a missing money dimension (see its header).

Options: `python3 work/rebuild.py --with-fec-lookup` runs the live
OpenFEC lookup instead of the committed results (needs `FEC_API_KEY`;
default is the committed file, so no API key is needed to rebuild).
`--skip-verify` skips the final audit run.

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
- `work/` — scripts, pull logs, verification notes, and intermediate files
- `work/bulk/` — staged FEC bulk data, **not committed** (gitignored, ~6 GB,
  re-downloadable from fec.gov — see `work/bulk-inventory.md`)

## Ground rules

- One change per commit, each scoped to a single bit of functionality.
- FEC filings are the source of truth; OpenSecrets is the cross-check.
- Never blend AIPAC PAC direct money with UDP independent expenditures into
  one number — they are separate columns by design.

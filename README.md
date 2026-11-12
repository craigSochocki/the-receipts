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

Run in this order. Step 1 works offline from a clean clone (verified). Steps
3–4 need the FEC bulk files staged first — the scripts read them, they don't
download them.

1. **Roster** — `python3 work/build_roster.py`
   Builds the 664-person roster from the vendored `work/legislators-*.yaml`
   files. Writes `work/roster_intermediate.json`.
2. **Download the FEC bulk data** — see `work/bulk-inventory.md` for the exact
   `curl` commands. About 838 MB of zips, ~5.9 GB on disk with the extracted
   files. Layout the scripts expect under `work/bulk/`:
   - `weball/weballYY.txt` (1980–2026), `cm/<cycle>/cm.txt`,
     `pas2/<cycle>/itpas2.txt`
   - `ie/<cycle>/independent_expenditure_<cycle>.csv` (2022, 2024, 2026 only)
3. **Career money** — `python3 work/pull_money.py`
   Reads the bulk files, writes `work/money_pas2_weball.csv` and
   `work/money_per_cycle.json`.
4. **Opposition credit** — `python3 work/compute_opposition.py`
   Credits UDP spending against a candidate's opponents to the backed
   candidate. Writes `work/opposition-computed.json`.

Optional enrichment: `python3 work/fec_lookup.py` verifies committee IDs and
enriches the roster via the FEC API. It reads `FEC_API_KEY` from the
environment and falls back to the public `DEMO_KEY`.

**Known gap — final assembly is not scripted yet.** The merge, the weball
double-count dedup, the ranking columns, and the 2026-cycle columns have no
saved script (see `architecture.md` §1a). The committed dataset is the output
of those steps; a bare re-run of the pull reproduces pre-dedup totals. That
codification is the next cleanup task.

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

#!/usr/bin/env python3
"""Rebuild the tracker dataset end to end from the staged sources.

Usage:
    python3 src/rebuild.py [--with-fec-lookup] [--skip-verify]

Pipeline (in order; each step runs as a module, `python3 -m <module>`):
    src.transform.build_roster       roster from legislators-current.yaml +
                                     historical_lookup.json + 120th_roster.json
    src.transform.fec_lookup         live OpenFEC lookup (ONLY with
                                     --with-fec-lookup; default off — the
                                     committed fec_lookup_results.json is
                                     used instead, so a rebuild needs no
                                     API key)
    src.transform.apply_fec_lookup   enrich the roster with the lookup
                                     results + the recorded manual notes;
                                     writes roster.json
    src.ingest.pull_money            weball + pas2 money per cycle
    src.ingest.pull_udp              UDP independent-expenditure support
    src.transform.apply_dedup        apply the recorded weball double-count
                                     dedup
    src.ingest.pull_self_funding     self-funding + topline from weball
                                     (Curtis-corrected for cols 6-9)
    src.ingest.pull_other_committees other-committee contributions (pas2 + cm)
    src.ingest.pull_all_ie           all independent expenditures 2022-2026
                                     (+ top committees per person)
    src.transform.compute_opposition UDP opposition credit (runs BEFORE the
                                     merge so its sanity check reads the
                                     current dataset)
    src.transform.merge_dataset      roster + money + opposition -> base dataset
    src.transform.compute_ranking    total_accepted + twelve rank columns
    src.transform.compute_2026       2026 columns, clean flags, primary-target list
    src.validate.verify_dataset      standing audits (unless --skip-verify)

The freshness layer (src/ingest/pull_freshness.py) is NOT part of this
pipeline: it runs on a different cadence (daily in the final 20 days
before an election, weekly in-cycle, event-driven after deadlines)
and writes data/intermediate/freshness_snapshot.json — new money found
since bulk coverage (Oct 14), labeled by source and date, NEVER merged
into the dataset totals. See methodology.md §16.

Prerequisites: the staged FEC bulk data in data/raw/ (see README.md).
The script fails fast with a clear message when bulk is not staged.
The current dataset is backed up first to
data/snapshots/congress-money-tracker-pre-rebuild-YYYYMMDD-HHMMSS.csv/.json
and left in place until the merge overwrites it (so the opposition sanity
check still reads the current dataset).

A live fec_lookup run overwrites fec_lookup_results.json wholesale and
loses the seven recorded `found-manual` entries, so --with-fec-lookup
snapshots them first and restores them afterwards.
"""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
SNAPSHOTS = ROOT / CFG['paths']['snapshots']
INTERMEDIATE = ROOT / CFG['paths']['intermediate']

# Pipeline steps in order (module names; run with `python3 -m <module>`).
STEPS = [
    'src.transform.build_roster',
    'src.transform.apply_fec_lookup',
    'src.ingest.pull_money',
    'src.ingest.pull_udp',
    'src.transform.apply_dedup',
    'src.ingest.pull_self_funding',
    'src.ingest.pull_other_committees',
    'src.ingest.pull_all_ie',
    'src.transform.compute_opposition',
    'src.transform.merge_dataset',
    'src.transform.compute_ranking',
    'src.transform.compute_2026',
    'src.validate.verify_dataset',
]
LOOKUP_STEP = 'src.transform.fec_lookup'

# Bulk files the pulls read; all must exist or the rebuild fails fast.
# The 2026 files plus the earliest-cycle files are checked as sentinels
# for the whole staged bulk set (the pulls read every cycle 1980-2026).
REQUIRED_BULK = [
    'data/raw/weball/weball26.txt',
    'data/raw/weball/weball80.txt',
    'data/raw/pas2/2026/itpas2.txt',
    'data/raw/pas2/1980/itpas2.txt',
    'data/raw/cm/2026/cm.txt',
    'data/raw/cm/1980/cm.txt',
    'data/raw/ie/2026/independent_expenditure_2026.csv',
    'data/raw/ie/2024/independent_expenditure_2024.csv',
    'data/raw/ie/2022/independent_expenditure_2022.csv',
]
# Roster sources build_roster.py reads.
REQUIRED_ROSTER_SOURCES = [
    'data/source/legislators-current.yaml',
    'data/source/historical_lookup.json',
    'data/source/120th_roster.json',
]


def run(module, *args):
    cmd = [sys.executable, '-m', module, *args]
    print(f'\n=== {module} ===', flush=True)
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f'{module} failed (exit {proc.returncode}); rebuild aborted')


def ensure_dirs():
    """Create the output directories a fresh clone lacks: intermediates
    are gitignored, so the directory itself is not in the repo."""
    for d in (INTERMEDIATE, SNAPSHOTS):
        d.mkdir(parents=True, exist_ok=True)


def check_staged():
    missing = [p for p in REQUIRED_BULK + REQUIRED_ROSTER_SOURCES
               if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(
            'bulk data not staged — cannot rebuild.\n'
            'Missing:\n' + '\n'.join(f'  {p}' for p in missing) +
            '\nStage the FEC bulk files under data/raw/ first '
            '(see README.md "Getting the bulk data").')


def backup_dataset():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    for key in ('dataset_csv', 'dataset_json'):
        src = ROOT / CFG['paths'][key]
        if not src.exists():
            print(f'no existing {src.name} to back up (first build)')
            continue
        dst = SNAPSHOTS / f'congress-money-tracker-pre-rebuild-{stamp}{src.suffix}'
        shutil.copy2(src, dst)
        print(f'backed up {src.name} -> {dst.name}')


def restore_manual_lookup_entries(snapshot_path):
    """Re-apply the recorded found-manual entries after a live lookup run."""
    before = json.load(open(snapshot_path))
    manual = {k: v for k, v in before.items()
              if isinstance(v, dict) and v.get('fec_source') == 'found-manual'}
    if not manual:
        return
    path = ROOT / CFG['paths']['fec_lookup_results']
    after = json.load(open(path))
    for k, v in manual.items():
        after[k] = v
    with open(path, 'w') as f:
        json.dump(after, f, indent=1)
    print(f'restored {len(manual)} found-manual lookup entries: {sorted(manual)}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--with-fec-lookup', action='store_true',
                    help='run the live OpenFEC lookup (needs an API key; '
                         'default: use the committed fec_lookup_results.json)')
    ap.add_argument('--skip-verify', action='store_true',
                    help='skip the final verify_dataset.py run')
    args = ap.parse_args()

    check_staged()
    ensure_dirs()
    backup_dataset()

    run(STEPS[0])
    if args.with_fec_lookup:
        lookup_path = ROOT / CFG['paths']['fec_lookup_results']
        snapshot = INTERMEDIATE / '.fec_lookup_snapshot.json'
        shutil.copy2(lookup_path, snapshot)
        try:
            run(LOOKUP_STEP)
            restore_manual_lookup_entries(snapshot)
        finally:
            snapshot.unlink(missing_ok=True)
    for step in STEPS[1:9]:
        run(step)
    opp = json.load(open(ROOT / CFG['paths']['opposition_computed']))
    if opp.get('support_mismatches'):
        raise SystemExit(f"opposition support mismatches (vs current dataset): "
                         f"{opp['support_mismatches']}; rebuild aborted")
    for step in STEPS[9:]:
        if step == 'src.validate.verify_dataset' and args.skip_verify:
            continue
        run(step)
    print('\nrebuild complete.')


if __name__ == '__main__':
    main()

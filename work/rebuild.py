#!/usr/bin/env python3
"""Rebuild the tracker dataset end to end from the staged sources.

Usage:
    python3 work/rebuild.py [--with-fec-lookup] [--skip-verify]

Pipeline (in order):
    build_roster.py        roster from legislators-current.yaml +
                           historical_lookup.json + 120th_roster.json
    fec_lookup.py          live OpenFEC lookup (ONLY with --with-fec-lookup;
                           default off — the committed fec_lookup_results.json
                           is used instead, so a rebuild needs no API key)
    apply_fec_lookup.py    enrich the roster with the lookup results +
                           the recorded manual notes; writes roster.json
    pull_money.py          weball + pas2 money per cycle
    pull_udp.py            UDP independent-expenditure support
    apply_dedup.py         apply the recorded weball double-count dedup
    compute_opposition.py  UDP opposition credit (runs BEFORE the merge so
                           its sanity check reads the current dataset)
    merge_dataset.py       roster + money + opposition -> base dataset
    compute_ranking.py     total_accepted + seven rank columns
    compute_2026.py        2026 columns, clean flags, primary-target list
    verify_dataset.py      standing audits (unless --skip-verify)

Prerequisites: the staged FEC bulk data in work/bulk/ (see README.md).
The script fails fast with a clear message when bulk is not staged.
The current dataset is backed up first to
work/congress-money-tracker-pre-rebuild-YYYYMMDD-HHMMSS.csv/.json and
left in place until the merge overwrites it (so the opposition sanity
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

from config import load_config

CFG = load_config()
ROOT = CFG['_root']
WORK = ROOT / CFG['paths']['work']

# Bulk files the pulls read; all must exist or the rebuild fails fast.
# The 2026 files plus the earliest-cycle files are checked as sentinels
# for the whole staged bulk set (the pulls read every cycle 1980-2026).
REQUIRED_BULK = [
    'work/bulk/weball/weball26.txt',
    'work/bulk/weball/weball80.txt',
    'work/bulk/pas2/2026/itpas2.txt',
    'work/bulk/pas2/1980/itpas2.txt',
    'work/bulk/cm/2026/cm.txt',
    'work/bulk/cm/1980/cm.txt',
    'work/bulk/ie/2026/independent_expenditure_2026.csv',
    'work/bulk/ie/2024/independent_expenditure_2024.csv',
    'work/bulk/ie/2022/independent_expenditure_2022.csv',
]
# Roster sources build_roster.py reads.
REQUIRED_ROSTER_SOURCES = [
    'work/legislators-current.yaml',
    'work/historical_lookup.json',
    'work/120th_roster.json',
]


def run(script, *args):
    cmd = [sys.executable, str(WORK / script), *args]
    print(f'\n=== {script} ===', flush=True)
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f'{script} failed (exit {proc.returncode}); rebuild aborted')


def check_staged():
    missing = [p for p in REQUIRED_BULK + REQUIRED_ROSTER_SOURCES
               if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(
            'bulk data not staged — cannot rebuild.\n'
            'Missing:\n' + '\n'.join(f'  {p}' for p in missing) +
            '\nStage the FEC bulk files under work/bulk/ first '
            '(see README.md "Getting the bulk data").')


def backup_dataset():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    for key in ('dataset_csv', 'dataset_json'):
        src = ROOT / CFG['paths'][key]
        if not src.exists():
            print(f'no existing {src.name} to back up (first build)')
            continue
        dst = WORK / f'congress-money-tracker-pre-rebuild-{stamp}{src.suffix}'
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
    backup_dataset()

    run('build_roster.py')
    if args.with_fec_lookup:
        lookup_path = ROOT / CFG['paths']['fec_lookup_results']
        snapshot = WORK / '.fec_lookup_snapshot.json'
        shutil.copy2(lookup_path, snapshot)
        try:
            run('fec_lookup.py')
            restore_manual_lookup_entries(snapshot)
        finally:
            snapshot.unlink(missing_ok=True)
    run('apply_fec_lookup.py')
    run('pull_money.py')
    run('pull_udp.py')
    run('apply_dedup.py')
    run('compute_opposition.py')
    opp = json.load(open(ROOT / CFG['paths']['opposition_computed']))
    if opp.get('support_mismatches'):
        raise SystemExit(f"opposition support mismatches (vs current dataset): "
                         f"{opp['support_mismatches']}; rebuild aborted")
    run('merge_dataset.py')
    run('compute_ranking.py')
    run('compute_2026.py')
    if not args.skip_verify:
        run('verify_dataset.py')
    print('\nrebuild complete.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Rebuild the tracker dataset end to end from the staged sources.

Usage:
    python3 receipts/rebuild.py [--with-fec-lookup] [--skip-verify] [--rebaseline]

Pipeline (in order; each step runs as a module, `python3 -m <module>`):
    receipts.transform.build_roster       roster from legislators-current.yaml +
                                     historical_lookup.json + 120th_roster.json
    receipts.transform.fec_lookup         live OpenFEC lookup (ONLY with
                                     --with-fec-lookup; default off — the
                                     committed fec_lookup_results.json is
                                     used instead, so a rebuild needs no
                                     API key)
    receipts.transform.apply_fec_lookup   enrich the roster with the lookup
                                     results + the recorded manual notes;
                                     writes roster.json
    receipts.store.build_store            silver store: every FEC candidate,
                                     committee and filing, in DuckDB
    receipts.store.accepted_money         the roster's counted money, read from
                                     the store (double counts removed)
    receipts.store.udp                    UDP independent-expenditure support, from the store
    receipts.store.self_funding           self-funding + topline, from the store
                                     (Curtis-corrected for cols 6-9)
    receipts.store.other_committees       other-committee contributions, from the store
    receipts.store.all_ie                 all independent expenditures 2022-2026, from the store
                                     (+ top committees per person)
    receipts.store.opposition             UDP opposition credit (runs BEFORE the
                                     merge so its sanity check reads the
                                     current dataset)
    receipts.transform.build_dataset      one pass, written once: merge (roster + money +
                                     opposition), ranking (total_accepted + twelve
                                     rank columns), 2026 (columns, clean flags,
                                     primary-target list)
    receipts.validate.verify_dataset      standing audits (unless --skip-verify)

The freshness layer (receipts/ingest/pull_freshness.py) is NOT part of this
pipeline: it runs on a different cadence (daily in the final 20 days
before an election, weekly in-cycle, event-driven after deadlines)
and writes data/intermediate/freshness_snapshot.json — new money found
since bulk coverage (Oct 14), labeled by source and date, NEVER merged
into the dataset totals. See methodology.md §16.

Each step checks its figures against data/source/baseline.json, which is
tied to one pinned FEC snapshot (./fetch_snapshot.sh). `--rebaseline`
accepts a new snapshot: it records the observed figures, and the diff of
baseline.json is the review.

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
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from receipts.common.config import load_config
from receipts.common import baseline

CFG = load_config()
ROOT = CFG['_root']
SNAPSHOTS = ROOT / CFG['paths']['snapshots']
INTERMEDIATE = ROOT / CFG['paths']['intermediate']

# Pipeline steps in order (module names; run with `python3 -m <module>`).
STEPS = [
    'receipts.transform.build_roster',
    'receipts.transform.apply_fec_lookup',
    'receipts.store.build_store',
    'receipts.store.accepted_money',
    'receipts.store.udp',
    'receipts.store.self_funding',
    'receipts.store.other_committees',
    'receipts.store.all_ie',
    'receipts.store.opposition',
    'receipts.transform.build_dataset',
    'receipts.validate.verify_dataset',
]
LOOKUP_STEP = 'receipts.transform.fec_lookup'

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


def staged_snapshot():
    marker = ROOT / CFG['paths']['raw'] / 'SNAPSHOT'
    return marker.read_text().strip() if marker.exists() else None


def staged_candidates_snapshot():
    marker = ROOT / CFG['paths']['raw'] / 'cn' / 'SNAPSHOT'
    return marker.read_text().strip() if marker.exists() else None


def check_data_as_of(tag):
    snapshot_date = tag.removeprefix('fec-bulk-')
    if str(CFG['data_as_of']) != snapshot_date:
        raise SystemExit(
            f'config.yaml data_as_of is {CFG["data_as_of"]} but the staged snapshot is '
            f'{tag}; set data_as_of: "{snapshot_date}" in the same change'
        )


def check_snapshot(rebaseline):
    staged, pinned = staged_snapshot(), baseline.snapshot()
    if rebaseline and (staged is None or staged_candidates_snapshot() is None):
        raise SystemExit(
            'cannot rebaseline from an unpinned download; '
            'stage both snapshots with ./fetch_snapshot.sh <tag>'
        )
    if not rebaseline and staged != pinned:
        raise SystemExit(
            f'staged bulk data is {staged or "an unpinned live download"}, but the baseline '
            f'was recorded from {pinned}; run ./fetch_snapshot.sh, or accept the new data '
            f'with --rebaseline and review the baseline diff'
        )
    if rebaseline:
        print(f'REBASELINE: recording figures from {staged} (baseline was {pinned})')
    check_data_as_of(staged)


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
    missing = [p for p in REQUIRED_BULK + REQUIRED_ROSTER_SOURCES if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(
            'bulk data not staged — cannot rebuild.\n'
            'Missing:\n'
            + '\n'.join(f'  {p}' for p in missing)
            + '\nStage the FEC bulk files under data/raw/ first '
            '(see README.md "Getting the bulk data").'
        )


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
    manual = {
        k: v
        for k, v in before.items()
        if isinstance(v, dict) and v.get('fec_source') == 'found-manual'
    }
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
    ap.add_argument(
        '--with-fec-lookup',
        action='store_true',
        help='run the live OpenFEC lookup (needs an API key; '
        'default: use the committed fec_lookup_results.json)',
    )
    ap.add_argument(
        '--skip-verify', action='store_true', help='skip the final verify_dataset.py run'
    )
    ap.add_argument(
        '--rebaseline',
        action='store_true',
        help='accept the staged snapshot as the new baseline: record '
        'every observed figure into data/source/baseline.json '
        '(review the diff before committing)',
    )
    args = ap.parse_args()
    if args.rebaseline and args.skip_verify:
        raise SystemExit('--rebaseline needs the verify step (it records the audit figures)')

    check_staged()
    ensure_dirs()
    check_snapshot(args.rebaseline)
    if args.rebaseline:
        os.environ['RECEIPTS_REBASELINE'] = '1'
        baseline.start_rebaseline_run()
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
        raise SystemExit(
            f'opposition support mismatches (vs current dataset): '
            f'{opp["support_mismatches"]}; rebuild aborted'
        )
    for step in STEPS[9:]:
        if step == 'receipts.validate.verify_dataset' and args.skip_verify:
            continue
        run(step)
    if args.rebaseline:
        # The baseline also pins what the page says, so the site is rebuilt and verified too.
        run('receipts.site.build_site')
        run('receipts.site.verify_site')
        baseline.start_rebaseline_run()
        baseline.set_snapshots(staged_snapshot(), staged_candidates_snapshot())
        print(
            f'\nbaseline recorded from {staged_snapshot()} and '
            f'{staged_candidates_snapshot()} — review '
            f'`git diff {CFG["paths"]["baseline"]}` before committing.'
        )
    print('\nrebuild complete.')


if __name__ == '__main__':
    main()

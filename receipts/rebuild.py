#!/usr/bin/env python3
"""Rebuild the dataset end to end from the pinned FEC snapshot; the steps are STEPS."""

import argparse
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from receipts.common import baseline
from receipts.common.files import read_json
from receipts.common.log import log
from receipts.common.log import run as run_script
from receipts.common.settings import settings
from receipts.site import build_site, verify_site
from receipts.store import (
    accepted_money,
    all_ie,
    build_store,
    models,
    opposition,
    other_committees,
    self_funding,
    udp,
)
from receipts.transform import apply_fec_lookup, build_dataset, build_roster, fec_lookup
from receipts.validate import run_history, verify_dataset


@dataclass(frozen=True)
class Step:
    name: str
    run: Callable[[], object]


STEPS = [
    Step('receipts.transform.build_roster', build_roster.main),
    Step('receipts.transform.apply_fec_lookup', apply_fec_lookup.main),
    Step('receipts.store.build_store', build_store.main),
    Step('receipts.validate.run_history', run_history.main),
    Step('receipts.store.models silver', lambda: models.build('silver')),
    Step('receipts.store.accepted_money', accepted_money.main),
    Step('receipts.store.udp', udp.main),
    Step('receipts.store.self_funding', self_funding.main),
    Step('receipts.store.other_committees', other_committees.main),
    Step('receipts.store.all_ie', all_ie.main),
    Step('receipts.store.opposition', opposition.main),
    Step('receipts.store.models marts', lambda: models.build('marts')),
    Step('receipts.transform.build_dataset', build_dataset.main),
    Step('receipts.validate.verify_dataset', lambda: verify_dataset.main([])),
]
LOOKUP_STEP = Step('receipts.transform.fec_lookup', fec_lookup.main)
SITE_STEPS = [
    Step('receipts.site.build_site', build_site.main),
    Step('receipts.site.verify_site', lambda: verify_site.main([])),
]


def required_bulk():
    """The current and earliest cycles' files, as sentinels for the whole staged bulk set."""
    cycles = settings().cycles
    ends = (cycles.current, cycles.career_start)
    return [
        *(f'data/raw/weball/weball{year % 100:02d}.txt' for year in ends),
        *(f'data/raw/pas2/{year}/itpas2.txt' for year in ends),
        *(f'data/raw/cm/{year}/cm.txt' for year in ends),
        *(f'data/raw/ie/{year}/independent_expenditure_{year}.csv' for year in cycles.ie),
    ]


# Roster sources build_roster.py reads.
REQUIRED_ROSTER_SOURCES = [
    'data/source/legislators-current.yaml',
    'data/source/historical_lookup.json',
    'data/source/120th_roster.json',
]


def staged_snapshot():
    marker = settings().paths.raw / 'SNAPSHOT'
    return marker.read_text().strip() if marker.exists() else None


def staged_candidates_snapshot():
    marker = settings().paths.raw / 'cn' / 'SNAPSHOT'
    return marker.read_text().strip() if marker.exists() else None


def check_data_as_of(tag):
    snapshot_date = tag.removeprefix('fec-bulk-')
    if settings().data_as_of != snapshot_date:
        raise SystemExit(
            f'config.yaml data_as_of is {settings().data_as_of} but the staged snapshot is '
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
        log.info(f'REBASELINE: recording figures from {staged} (baseline was {pinned})')
    check_data_as_of(staged)


def run(step):
    """Run one step; a step that exits with an error aborts the rebuild."""
    log.info(f'\n=== {step.name} ===')
    try:
        step.run()
    except SystemExit as e:
        if e.code not in (None, 0):
            log.info(e.code if isinstance(e.code, str) else '')
            raise SystemExit(f'{step.name} failed; rebuild aborted') from e


def ensure_dirs():
    """Create the gitignored output folders a fresh clone lacks."""
    for d in (settings().paths.intermediate, settings().paths.snapshots):
        d.mkdir(parents=True, exist_ok=True)


def check_staged():
    missing = [
        p for p in required_bulk() + REQUIRED_ROSTER_SOURCES if not (settings().root / p).exists()
    ]
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
    paths = settings().paths
    for src in (paths.dataset_csv, paths.dataset_json):
        if not src.exists():
            log.info(f'no existing {src.name} to back up (first build)')
            continue
        dst = settings().paths.snapshots / f'congress-money-tracker-pre-rebuild-{stamp}{src.suffix}'
        shutil.copy2(src, dst)
        log.info(f'backed up {src.name} -> {dst.name}')


def restore_manual_lookup_entries(snapshot_path):
    """Re-apply the recorded found-manual entries after a live lookup run."""
    before = read_json(snapshot_path)
    manual = {
        k: v
        for k, v in before.items()
        if isinstance(v, dict) and v.get('fec_source') == 'found-manual'
    }
    if not manual:
        return
    path = settings().paths.fec_lookup_results
    after = read_json(path)
    for k, v in manual.items():
        after[k] = v
    with open(path, 'w') as f:
        json.dump(after, f, indent=1)
    log.info(f'restored {len(manual)} found-manual lookup entries: {sorted(manual)}')


ROSTER_STEP, VERIFY_STEP = STEPS[0], STEPS[-1]


def run_live_lookup():
    lookup_path = settings().paths.fec_lookup_results
    snapshot = settings().paths.intermediate / '.fec_lookup_snapshot.json'
    shutil.copy2(lookup_path, snapshot)
    try:
        run(LOOKUP_STEP)
        restore_manual_lookup_entries(snapshot)
    finally:
        snapshot.unlink(missing_ok=True)


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

    for step in STEPS:
        if step == VERIFY_STEP and args.skip_verify:
            continue
        run(step)
        if step == ROSTER_STEP and args.with_fec_lookup:
            run_live_lookup()
    if args.rebaseline:
        # The baseline also pins what the page says, so the site is rebuilt and verified too.
        for step in SITE_STEPS:
            run(step)
        baseline.start_rebaseline_run()
        baseline.set_snapshots(staged_snapshot(), staged_candidates_snapshot())
        log.info(
            f'\nbaseline recorded from {staged_snapshot()} and '
            f'{staged_candidates_snapshot()} — review '
            f'`git diff {settings().relative(settings().paths.baseline)}` before committing.'
        )
    log.info('\nrebuild complete.')


if __name__ == '__main__':
    run_script(main)

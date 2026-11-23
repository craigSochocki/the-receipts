"""Check what this run read from the FEC against the last recorded run, and record data changes.

data/source/run_history.csv holds, for each recorded snapshot, the rows read from every
FEC bulk file and when the FEC last changed it. Every run fails if:
- a file lost more than run_checks.max_row_drop of its rows since the latest recorded
  snapshot (one not newer than this one), or is missing;
- the newest current-cycle file was more than run_checks.max_file_age_days old on the
  snapshot date (the FEC stopped publishing, or the snapshot froze stale files).
A rebaseline (rebuild.py --rebaseline) also records this snapshot's rows, so they land
with the refresh pull request, which opens only when figures move.
"""

import csv
from datetime import date

from receipts.common import baseline
from receipts.common.config import load_config
from receipts.common.settings import CURRENT_CYCLE, PATHS
from receipts.store.read import connect

FIELDS = ['snapshot', 'file', 'cycle', 'rows_read', 'last_modified']
LIMITS = load_config()['run_checks']


def observed(snapshot):
    with connect() as db:
        rows = db.execute(
            'SELECT file, cycle, rows_read, strftime(last_modified, ?) FROM files_read '
            'LEFT JOIN source_files USING (file, cycle) ORDER BY file, cycle',
            ['%Y-%m-%dT%H:%M:%SZ'],
        ).fetchall()
    return [dict(zip(FIELDS, (snapshot, *row), strict=True)) for row in rows]


def recorded():
    if not PATHS.run_history.exists():
        return []
    with open(PATHS.run_history) as f:
        return [
            {**r, 'cycle': int(r['cycle']), 'rows_read': int(r['rows_read'])}
            for r in csv.DictReader(f)
        ]


def row_drops(previous, current):
    rows_now = {(r['file'], r['cycle']): r['rows_read'] for r in current}
    floor = 1 - LIMITS['max_row_drop']
    return [
        f'{r["file"]} {r["cycle"]}: {rows_now.get((r["file"], r["cycle"]), 0):,} rows, '
        f'was {r["rows_read"]:,} in {r["snapshot"]}'
        for r in previous
        if rows_now.get((r['file'], r['cycle']), 0) < r['rows_read'] * floor
    ]


def file_age_days(current, snapshot):
    newest = max(
        r['last_modified'] for r in current if r['cycle'] == CURRENT_CYCLE and r['last_modified']
    )
    return (
        date.fromisoformat(snapshot.removeprefix('fec-bulk-')) - date.fromisoformat(newest[:10])
    ).days


def main():
    snapshot = (PATHS.bulk / 'SNAPSHOT').read_text().strip()
    current = observed(snapshot)
    history = recorded()
    earlier = [s for s in {r['snapshot'] for r in history} if s <= snapshot]
    previous = [r for r in history if earlier and r['snapshot'] == max(earlier)]

    problems = row_drops(previous, current)
    age = file_age_days(current, snapshot)
    if age > LIMITS['max_file_age_days']:
        problems.append(f'the newest {CURRENT_CYCLE} FEC file was {age} days old on {snapshot}')
    if problems:
        raise SystemExit('FEC inputs look wrong:\n  ' + '\n  '.join(problems))
    print(f'{snapshot}: {len(current)} files read, newest {CURRENT_CYCLE} file {age} days old')

    if baseline.rebaselining():
        with open(PATHS.run_history, 'w', newline='') as f:
            writer = csv.DictWriter(f, FIELDS)
            writer.writeheader()
            writer.writerows([r for r in history if r['snapshot'] != snapshot] + current)


if __name__ == '__main__':
    main()

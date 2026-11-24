#!/usr/bin/env python3
"""Every baseline figure a rebaseline moved, old next to new, as a Markdown table."""

import sys

from receipts.common.files import read_json
from receipts.common.log import run

SHOWN = 120


def changes(old, new):
    """[(key, before, after)] for each figure added, removed or changed; snapshot tags aside."""
    keys = sorted((set(old) | set(new)) - {k for k in set(old) | set(new) if k.startswith('_')})
    return [(key, old.get(key), new.get(key)) for key in keys if old.get(key) != new.get(key)]


def shown(value):
    if value is None:
        return '—'
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f'{value:,.2f}'
    return f'{value:,}' if isinstance(value, int) else str(value)


def table(moved):
    if not moved:
        return 'No baseline figure moved.'
    lines = ['| Figure | Before | After |', '|---|---:|---:|']
    lines += [
        f'| `{key}` | {shown(before)} | {shown(after)} |' for key, before, after in moved[:SHOWN]
    ]
    if len(moved) > SHOWN:
        lines.append(
            f'\n…and {len(moved) - SHOWN} more; see the diff of `data/source/baseline.json`.'
        )
    return '\n'.join(lines)


def main():
    old, new = (read_json(path) for path in sys.argv[1:3])
    moved = changes(old, new)
    print(len(moved) if '--count' in sys.argv else table(moved))


if __name__ == '__main__':
    run(main)

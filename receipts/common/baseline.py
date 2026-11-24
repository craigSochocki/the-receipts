"""Expected figures that move with FEC data, kept in data/source/baseline.json."""

import json
import os

from receipts.common.settings import settings

_SNAPSHOT, _CANDIDATES_SNAPSHOT = '_snapshot', '_candidates_snapshot'


def _path():
    return settings().paths.baseline


def _recorded_this_run():
    return settings().paths.intermediate / '.rebaseline_seen.json'


def rebaselining():
    return os.environ.get('RECEIPTS_REBASELINE') == '1'


def expected(key, observed):
    """The figure to compare `observed` against."""
    key = str(key)
    figures = _read(_path(), {})
    if not rebaselining():
        if key not in figures:
            raise SystemExit(
                f'baseline has no figure for {key!r}; '
                f'run `python3 receipts/rebuild.py --rebaseline` and review the diff'
            )
        return figures[key]

    recorded = set(_read(_recorded_this_run(), []))
    if key in recorded:
        # Another step already recorded it: the two computations must agree.
        return figures[key]
    figures[key] = observed
    _write(_path(), figures)
    _write(_recorded_this_run(), sorted(recorded | {key}))
    return observed


def start_rebaseline_run():
    _recorded_this_run().unlink(missing_ok=True)


def snapshot():
    return _read(_path(), {}).get(_SNAPSHOT)


def candidates_snapshot():
    return _read(_path(), {}).get(_CANDIDATES_SNAPSHOT)


def set_snapshots(bulk, candidates):
    _write(_path(), {**_read(_path(), {}), _SNAPSHOT: bulk, _CANDIDATES_SNAPSHOT: candidates})


def _read(path, default):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def _write(path, data):
    if isinstance(data, dict):
        data = dict(sorted(data.items()))
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp, path)

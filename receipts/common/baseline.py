"""Expected figures that depend on the FEC data, kept in one committed file.

Check mode compares against data/source/baseline.json. Rebaseline mode
(`rebuild.py --rebaseline`) records what it observes; the diff of that
file is the review. Policy values stay in config.yaml.
"""

import json
import os

from receipts.common.config import load_config

_CFG = load_config()
PATH = _CFG['_root'] / _CFG['paths']['baseline']
_RECORDED_THIS_RUN = _CFG['_root'] / _CFG['paths']['intermediate'] / '.rebaseline_seen.json'
_SNAPSHOT, _CANDIDATES_SNAPSHOT = '_snapshot', '_candidates_snapshot'


def rebaselining():
    return os.environ.get('RECEIPTS_REBASELINE') == '1'


def expected(key, observed):
    """The figure to compare `observed` against."""
    key = str(key)
    figures = _read(PATH, {})
    if not rebaselining():
        if key not in figures:
            raise SystemExit(
                f'baseline has no figure for {key!r}; '
                f'run `python3 receipts/rebuild.py --rebaseline` and review the diff'
            )
        return figures[key]

    recorded = set(_read(_RECORDED_THIS_RUN, []))
    if key in recorded:
        # Another step already recorded it: the two computations must agree.
        return figures[key]
    figures[key] = observed
    _write(PATH, figures)
    _write(_RECORDED_THIS_RUN, sorted(recorded | {key}))
    return observed


def start_rebaseline_run():
    _RECORDED_THIS_RUN.unlink(missing_ok=True)


def snapshot():
    return _read(PATH, {}).get(_SNAPSHOT)


def candidates_snapshot():
    return _read(PATH, {}).get(_CANDIDATES_SNAPSHOT)


def set_snapshots(bulk, candidates):
    _write(PATH, {**_read(PATH, {}), _SNAPSHOT: bulk, _CANDIDATES_SNAPSHOT: candidates})


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

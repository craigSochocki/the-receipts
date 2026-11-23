"""The baseline: every data-dependent expected figure, in one committed file.

WHY THIS EXISTS. The FEC updates its bulk files in place, so the roster
totals, counts, and named spot figures the pipeline checks itself against
are only true for ONE set of inputs. They used to live as literals in the
scripts and in config.yaml `verification`, which meant any new filing
"failed" the rebuild and a refresh could never land. Now:

- `data/source/baseline.json` holds every expected figure, plus the
  bulk snapshot (`_snapshot`) those figures were recorded from.
- A script asks `expected('some.key', observed)` and compares the return
  value with what it computed, exactly as it compared a literal before.
- In CHECK mode (the default) the return value is the committed baseline
  figure, so a mismatch fails the run — same gate as always
  (AGENTS.md §5: a mismatch means the code, the data, or the method is
  wrong; stop and report).
- In REBASELINE mode (`python3 src/rebuild.py --rebaseline`, which sets
  RECEIPTS_REBASELINE=1 for every step) the observed value is recorded
  into baseline.json and returned, so the checks pass and the file is
  rewritten for the new inputs. `git diff data/source/baseline.json` is
  then the review: every figure that moved, old next to new. Nothing is
  accepted until that diff is committed by a human decision.

Policy values (thresholds, tolerance presets, committee IDs) are NOT
baseline — they stay in config.yaml. The test: would a new FEC filing
change it? If yes, it belongs here.

Keys are dotted strings; the file is flat, sorted, one key per line, so
diffs read cleanly. Values are JSON scalars, lists, or small objects
(a named spot case pins several fields of one person together).
"""
import json
import os

from src.common.config import load_config

_CFG = load_config()
PATH = _CFG['_root'] / _CFG['paths']['baseline']
SNAPSHOT_KEY = '_snapshot'


def rebaselining():
    return os.environ.get('RECEIPTS_REBASELINE') == '1'


def _load():
    if not PATH.exists():
        return {}
    with open(PATH) as f:
        return json.load(f)


def _save(data):
    tmp = PATH.with_suffix('.json.tmp')
    with open(tmp, 'w') as f:
        json.dump(dict(sorted(data.items())), f, indent=1, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp, PATH)


def expected(key, observed):
    """The baseline figure for `key`.

    CHECK mode: return the committed figure (compare it with `observed`
    yourself). A key missing from the baseline is an error, never a pass.
    REBASELINE mode: record `observed` under `key` and return it.
    """
    key = str(key)
    data = _load()
    if rebaselining():
        seen = _seen_this_run()
        if key in seen:
            # Another step already recorded this figure in THIS rebaseline
            # run. Return theirs, so two independent computations of the
            # same figure still have to agree (the cross-check survives).
            return data[key]
        if data.get(key, _MISSING) != observed:
            data[key] = observed
            _save(data)
        _mark_seen(key)
        return observed
    if key not in data:
        raise SystemExit(
            f'baseline has no figure for {key!r} — run '
            f'`python3 src/rebuild.py --rebaseline` and review the diff '
            f'of {PATH.name} (see src/common/baseline.py)')
    return data[key]


def _seen_path():
    return _CFG['_root'] / _CFG['paths']['intermediate'] / '.rebaseline_seen.json'


def _seen_this_run():
    p = _seen_path()
    return set(json.load(open(p))) if p.exists() else set()


def _mark_seen(key):
    seen = _seen_this_run()
    seen.add(key)
    with open(_seen_path(), 'w') as f:
        json.dump(sorted(seen), f)


def start_rebaseline_run():
    """Forget which keys were recorded (called once by rebuild.py)."""
    _seen_path().unlink(missing_ok=True)


def snapshot():
    """The bulk snapshot tag the committed baseline was recorded from."""
    return _load().get(SNAPSHOT_KEY)


def set_snapshot(tag):
    data = _load()
    data[SNAPSHOT_KEY] = tag
    _save(data)


_MISSING = object()

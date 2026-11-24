"""Complexity and maintainability limits for receipts/, as a ratchet.

New code must stay within the limits. The functions and files listed
below were over them when the limits were set; each may only get
better than its recorded score. Improve one, then tighten or remove
its entry.
"""

from radon.complexity import cc_visit
from radon.metrics import mi_visit

from receipts.common.settings import repo_root

MAX_COMPLEXITY = 20  # radon grade C or better
MIN_MAINTAINABILITY = 20  # radon grade A

COMPLEXITY_DEBT = {}
# Scored without docstrings, so prose cannot lift a file over the line.
MAINTAINABILITY_DEBT = {
    'ingest/pull_freshness.py': 19,
    'ingest/pull_gate.py': 19,
    'site/checks/charts.py': 19,
    'store/other_committees.py': 18,
    'transform/build_roster.py': 15,
}

PACKAGE = repo_root() / 'receipts'


def modules():
    for path in sorted(PACKAGE.rglob('*.py')):
        yield path.relative_to(PACKAGE).as_posix(), path.read_text()


def blocks(code):
    for block in cc_visit(code):
        yield block
        yield from getattr(block, 'methods', [])
        yield from getattr(block, 'closures', [])


def complexity_scores():
    return {
        f'{name}:{block.fullname}': block.complexity
        for name, code in modules()
        for block in blocks(code)
    }


def maintainability_scores():
    return {name: mi_visit(code, multi=False) for name, code in modules()}


def test_functions_stay_within_the_complexity_limit():
    scores = complexity_scores()
    over = {
        name: score
        for name, score in scores.items()
        if score > COMPLEXITY_DEBT.get(name, MAX_COMPLEXITY)
    }
    assert not over, f'too complex (limit {MAX_COMPLEXITY}, or the recorded debt): {over}'


def test_files_stay_above_the_maintainability_limit():
    scores = maintainability_scores()
    under = {
        name: round(score, 2)
        for name, score in scores.items()
        if score < MAINTAINABILITY_DEBT.get(name, MIN_MAINTAINABILITY)
    }
    assert not under, f'hard to maintain (limit {MIN_MAINTAINABILITY}): {under}'


def test_every_recorded_debt_still_exists():
    complexity, maintainability = complexity_scores(), maintainability_scores()
    gone = [name for name in COMPLEXITY_DEBT if name not in complexity]
    gone += [name for name in MAINTAINABILITY_DEBT if name not in maintainability]
    assert not gone, f'remove these entries, the code they name is gone: {gone}'

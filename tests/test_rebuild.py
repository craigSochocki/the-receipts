import pytest

from receipts.rebuild import STEPS, Step, run


def test_a_step_that_returns_or_exits_cleanly_lets_the_rebuild_go_on():
    run(Step('fine', lambda: None))
    run(Step('exits zero', lambda: exit(0)))


def test_a_step_that_exits_with_an_error_aborts_the_rebuild():
    def fails():
        raise SystemExit('the figure moved')

    with pytest.raises(SystemExit, match='broken failed; rebuild aborted'):
        run(Step('broken', fails))


def test_every_step_has_a_unique_name():
    names = [step.name for step in STEPS]
    assert len(names) == len(set(names))

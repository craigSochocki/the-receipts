import pytest

from receipts.store import all_ie

SUMMARY = {
    'roster_targeted': {'senate': 30.0, 'house': 70.0, 'support': 40.0, 'oppose': 60.0},
    'top_committees_roster_targeted': [
        {'committee_id': f'C0000000{n}', 'total': 10.0 * n} for n in range(6, 0, -1)
    ],
}


def baseline_of(summary):
    """Every figure check_current_cycle pins, as the baseline would hold it."""
    seen = {}

    def record(key, observed):
        seen[key] = observed
        return observed

    original = all_ie.expected
    all_ie.expected = record
    try:
        all_ie.check_current_cycle(summary)
    finally:
        all_ie.expected = original
    return seen


def test_pins_the_split_and_the_top_five_spenders():
    pinned = baseline_of(SUMMARY)
    assert len(pinned) == 4 + 2 * 5
    assert pinned[f'all_ie_top_spenders_{all_ie.CURRENT_CYCLE}.1.committee_id'] == 'C00000006'


def test_matching_figures_pass(monkeypatch):
    pinned = baseline_of(SUMMARY)
    monkeypatch.setattr(all_ie, 'expected', lambda key, observed: pinned[key])
    all_ie.check_current_cycle(SUMMARY)


def test_a_moved_figure_stops_the_build(monkeypatch):
    pinned = baseline_of(SUMMARY)
    pinned[f'all_ie_roster_{all_ie.CURRENT_CYCLE}.house'] = 71.0
    monkeypatch.setattr(all_ie, 'expected', lambda key, observed: pinned[key])
    with pytest.raises(SystemExit, match='house is 70.00; the baseline says 71.00'):
        all_ie.check_current_cycle(SUMMARY)


def test_a_new_top_spender_stops_the_build(monkeypatch):
    pinned = baseline_of(SUMMARY)
    pinned[f'all_ie_top_spenders_{all_ie.CURRENT_CYCLE}.2.committee_id'] = 'C99999999'
    monkeypatch.setattr(all_ie, 'expected', lambda key, observed: pinned[key])
    with pytest.raises(SystemExit, match='2.committee_id is C00000005'):
        all_ie.check_current_cycle(SUMMARY)

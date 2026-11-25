from receipts.domain.targets import is_primary_target, latest_record, primary_targets

CLASS_UP_IN_2028 = 3


def member(dirty, tier='dirty', **seat):
    record = {'cycle': 2026, 'dirty': dirty, 'tier_balanced': tier, 'tier_lenient': tier}
    return {
        'in_120th': 'yes',
        'chamber_120': 'House',
        'senate_class': None,
        'verdict_cycle': 2026,
        'cycles': [{'cycle': 2024, 'dirty': 0}, record],
        **seat,
    }


def test_the_latest_record_is_the_verdict_cycle():
    assert latest_record(member(5.0))['dirty'] == 5.0
    assert latest_record({**member(5.0), 'verdict_cycle': None}) is None


def test_any_party_counts_but_only_seats_up_next_cycle():
    assert is_primary_target({**member(5.0), 'party_120': 'Republican'}, 'strict', 2028)
    senator = member(5.0, chamber_120='Senate', senate_class=CLASS_UP_IN_2028)
    assert is_primary_target(senator, 'strict', 2028)
    assert not is_primary_target({**senator, 'senate_class': 1}, 'strict', 2028)
    assert not is_primary_target({**member(5.0), 'in_120th': 'no'}, 'strict', 2028)


def test_the_preset_decides_dirty():
    below = member(5.0, tier='below_threshold')
    assert is_primary_target(below, 'strict', 2028)
    assert not is_primary_target(below, 'balanced', 2028)
    assert not is_primary_target(member(0), 'strict', 2028)
    assert not is_primary_target({**member(5.0), 'verdict_cycle': None}, 'strict', 2028)


def test_targets_rank_dirtiest_first():
    people = [{**member(1.0), 'n': 'a'}, {**member(9.0), 'n': 'b'}, member(0)]
    assert [p['n'] for p in primary_targets(people, 'strict', 2028)] == ['b', 'a']

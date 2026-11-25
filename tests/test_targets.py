from receipts.domain.targets import is_primary_target, latest_record, primary_targets

CLASS_UP_IN_2028 = 3
MONEY = {'individual': 0, 'corp': 0, 'aipac_direct': 0, 'udp_benefit': 0, 'total_receipts': 0}


def cycle(year, dirty, **fields):
    return {'cycle': year, **MONEY, 'dirty': dirty, 'corp': dirty, 'unopposed': False,
            'cash_on_hand': year, **fields}  # fmt: skip


def member(dirty, tier='dirty', **seat):
    return {
        'in_120th': 'yes',
        'chamber_120': 'House',
        'senate_class': None,
        'verdict_cycle': 2024,
        'clean': dirty <= 0,
        'dirty': dirty,
        'tier_balanced': tier,
        'tier_lenient': tier,
        'cycles': [cycle(2022, 99), cycle(2024, dirty - 1), cycle(2026, 1)],
        **seat,
    }


def test_the_latest_record_is_the_election_and_every_cycle_since():
    record = latest_record(member(5.0))
    assert (record['cycle'], record['corp'], record['cash_on_hand']) == (2024, 5.0, 2026)
    assert record['dirty'] == 5.0
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

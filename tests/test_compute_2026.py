import pytest

from receipts.domain.committee_classes import OTHER_COMMITTEE_CLASSES
from receipts.transform.compute_2026 import add_cycle_records, has_2026_linkage, money_in

RACE = ('H', 'NY', '16')


def record(key='p', ids=('H1',), in_120th='yes', **lists):
    blank = {
        'per_cycle': [],
        'udp_per_cycle': [],
        'self_funding_per_cycle': [],
        'other_committees_per_cycle': [],
        'all_ie_per_cycle': [],
    }
    return {
        'person_key': key,
        'fec_candidate_ids': list(ids),
        'in_120th': in_120th,
        'chamber_120': 'House',
        'senate_class': None,
        'data_notes': '',
        **blank,
        **lists,
    }


def money(cycle=2026, individual=0.0, corp=0.0, aipac=0.0):
    return {
        'cycle': cycle,
        'individual': individual,
        'corporate_pac': corp,
        'aipac_pac_direct': aipac,
    }


def finances(cycle=2026, loans=0.0, receipts=0.0, coverage_end='10/14/2026'):
    return {
        'cycle': cycle,
        'candidate_contributions': 0.0,
        'candidate_loans': loans,
        'total_receipts': receipts,
        'total_disbursements': 0.0,
        'cash_on_hand': 5.0,
        'coverage_end_date': coverage_end,
    }


def contested(*ids):
    """A race the person's IDs share with a funded opponent."""
    return {RACE: [*((i, 100) for i in ids), ('H_OPPONENT', 500)]}, dict.fromkeys(ids, RACE)


def unopposed(*ids):
    return {RACE: [*((i, 100) for i in ids), ('H_ZERO', 0)]}, dict.fromkeys(ids, RACE)


def test_dirty_money_is_corporate_plus_aipac_plus_udp_benefit_never_individual():
    m = money_in(
        record(
            per_cycle=[money(individual=900.0, corp=100.0, aipac=10.0)],
            udp_per_cycle=[{'cycle': 2026, 'udp_ie_support': 40.0}],
        ),
        2026,
        50.0,
    )
    assert m['udp_benefit'] == 90.0
    assert m['dirty'] == 200.0
    assert m['aipac_udp_flag'] is True
    assert m['dep_share'] == round(110 / 1010, 4)


def test_a_family_with_no_2026_entry_reads_integer_zero_and_cash_on_hand_null():
    m = money_in(record(per_cycle=[money(cycle=2024, individual=5.0)]), 2026, 0.0)
    assert m['individual'] == 0 and isinstance(m['individual'], int)
    assert m['self_funding'] == 0 and m['other_committees_total'] == 0
    assert m['cash_on_hand'] is None
    assert m['dep_share'] is None


def test_other_committee_money_sums_every_class():
    entry = {'cycle': 2026, **{c.value: 1.0 for c in OTHER_COMMITTEE_CLASSES}}
    m = money_in(record(other_committees_per_cycle=[entry]), 2026, 0.0)
    assert m['other_committees_total'] == len(OTHER_COMMITTEE_CLASSES)


@pytest.mark.parametrize(
    'lists, linked',
    [
        ({'per_cycle': [money()]}, True),
        ({'udp_per_cycle': [{'cycle': 2026, 'udp_ie_support': 1.0}]}, True),
        ({'self_funding_per_cycle': [finances()]}, True),
        ({'self_funding_per_cycle': [finances(coverage_end='07/15/2025')]}, False),
        ({'all_ie_per_cycle': [{'cycle': 2026, 'all_ie_total': 9.0}]}, False),
        ({}, False),
    ],
)
def test_linkage_needs_2026_committee_money_or_a_2026_weball_report(lists, linked):
    assert has_2026_linkage(record(**lists)) is linked


def run(*records, credits=None, races=None):
    found = races or contested('H1')
    by_cycle = {(2026, key): credit for key, credit in (credits or {}).items()}
    return add_cycle_records(list(records), by_cycle, lambda cycle: found)


def test_a_linked_contested_member_with_no_net_dirty_money_is_clean():
    (r,) = run(record(per_cycle=[money(individual=500.0, aipac=-15.0)]))
    assert r['clean_2026'] is True
    assert r['tier_balanced_2026'] == 'clean'


def test_an_unlinked_120th_member_is_null_with_a_note():
    (r,) = run(record())
    assert r['clean_2026'] is None
    assert r['tier_lenient_2026'] is None
    assert '2026 clean status UNVERIFIED' in r['data_notes']


def test_an_unopposed_member_with_no_dirty_money_is_null_not_clean():
    (r,) = run(record(per_cycle=[money(individual=500.0)]), races=unopposed('H1'))
    assert r['unopposed_2026'] is True
    assert r['clean_2026'] is None
    assert '2026 clean status UNOPPOSED — ran unopposed in 2026 (NY-16)' in r['data_notes']


def test_an_unopposed_member_with_dirty_money_stays_dirty():
    (r,) = run(record(per_cycle=[money(corp=5.0)]), races=unopposed('H1'))
    assert r['clean_2026'] is False


def test_the_2026_opposition_credit_comes_from_the_credits_given():
    (r,) = run(record(per_cycle=[money(individual=10.0)]), credits={'p': 25.0})
    assert r['udp_opp_credit_2026'] == 25.0
    assert r['clean_2026'] is False
    assert r['tier_balanced_2026'] == 'dirty'


def test_corporate_money_without_individual_money_gets_a_data_gap_note():
    (r,) = run(record(per_cycle=[money(corp=3500.0)]))
    assert '2026 DATA GAP: corporate PAC $3,500 in 2026 but $0 individual' in r['data_notes']


def test_every_cycle_with_money_gets_its_own_record():
    (r,) = run(record(per_cycle=[money(cycle=2024, individual=5.0, corp=1.0), money()]))
    assert [c['cycle'] for c in r['cycles']] == [2024, 2026]
    past = r['cycles'][0]
    assert past['dirty'] == 1.0 and past['clean'] is False
    assert {k: v for k, v in r['cycles'][1].items() if k not in ('cycle', 'up_for_election')} == {
        k.removesuffix('_2026'): v for k, v in r.items() if k.endswith('_2026')
    }


def test_the_headline_verdict_is_the_current_cycle_if_up_else_the_latest_cycle_up():
    past_dirty = money(cycle=2024, corp=1.0)
    (off_year,) = add_cycle_records(
        [record(per_cycle=[past_dirty, money(individual=5.0)])],
        {}, lambda cycle: contested('H1'), filed={('H1', 2024): {2024}, ('H1', 2026): {2028}},
    )  # fmt: skip
    assert [c['up_for_election'] for c in off_year['cycles']] == [True, False]
    assert (off_year['verdict_cycle'], off_year['clean']) == (2024, False)
    (up_now,) = add_cycle_records(
        [record(per_cycle=[past_dirty, money(individual=5.0)])],
        {}, lambda cycle: contested('H1'), filed={('H1', 2024): {2024}, ('H1', 2026): {2026}},
    )  # fmt: skip
    assert (up_now['verdict_cycle'], up_now['clean']) == (2026, True)
    (unlinked,) = add_cycle_records(
        [record(per_cycle=[past_dirty])], {}, lambda cycle: contested('H1'),
        filed={('H1', 2024): {2024}},
    )  # fmt: skip
    assert (unlinked['verdict_cycle'], unlinked['clean']) == (2026, None)

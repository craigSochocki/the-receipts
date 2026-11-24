import pytest

from receipts.domain.committee_classes import OTHER_COMMITTEE_CLASSES
from receipts.transform.compute_2026 import add_2026_columns, has_2026_linkage, money_2026

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
    m = money_2026(
        record(
            per_cycle=[money(individual=900.0, corp=100.0, aipac=10.0)],
            udp_per_cycle=[{'cycle': 2026, 'udp_ie_support': 40.0}],
        ),
        credit=50.0,
    )
    assert m['udp_benefit_2026'] == 90.0
    assert m['dirty_2026'] == 200.0
    assert m['aipac_udp_flag_2026'] is True
    assert m['dep_share_2026'] == round(110 / 1010, 4)


def test_a_family_with_no_2026_entry_reads_integer_zero_and_cash_on_hand_null():
    m = money_2026(record(per_cycle=[money(cycle=2024, individual=5.0)]), credit=0.0)
    assert m['individual_2026'] == 0 and isinstance(m['individual_2026'], int)
    assert m['self_funding_2026'] == 0 and m['other_committees_total_2026'] == 0
    assert m['cash_on_hand_2026'] is None
    assert m['dep_share_2026'] is None


def test_other_committee_money_sums_every_class():
    entry = {'cycle': 2026, **{c.value: 1.0 for c in OTHER_COMMITTEE_CLASSES}}
    m = money_2026(record(other_committees_per_cycle=[entry]), credit=0.0)
    assert m['other_committees_total_2026'] == len(OTHER_COMMITTEE_CLASSES)


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
    race_map, race_of = races or contested('H1')
    return add_2026_columns(list(records), credits or {}, race_map, race_of)


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

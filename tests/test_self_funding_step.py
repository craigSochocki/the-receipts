from receipts.domain.campaign_finances import CampaignFinances
from receipts.domain.money import Money
from receipts.domain.roster import Roster
from receipts.domain.weball_double_counts import FINANCIAL_FIELDS
from receipts.store.self_funding import person_summary, self_funding_by_person


def finances(**dollars):
    amounts = {field: Money(round(dollars.get(field, 0) * 100)) for field in FINANCIAL_FIELDS}
    return CampaignFinances.from_weball(amounts)


def person(key, *ids):
    return {'person_key': key, 'full_name': key.title(), 'fec_candidate_ids': list(ids)}


FINANCES = {
    ('H1', 2022): finances(candidate_loans=100, cash_end=40, debts_owed_by=5),
    ('S1', 2024): finances(candidate_contributions=30, candidate_loans=20, cash_end=70),
    ('S1', 2026): finances(candidate_loans=10, cash_end=90, debts_owed_by=15),
}


def test_flows_sum_across_ids_and_cycles_and_stocks_take_the_latest_cycle():
    career, current, latest = person_summary(person('p', 'H1', 'S1'), FINANCES)
    assert career['candidate_loans'] == Money(130_00)
    assert career['self_funding'] == Money(160_00)
    assert career['cash_on_hand'] == Money(90_00)
    assert career['debts_owed_by'] == Money(15_00)
    assert latest == '2026'
    assert current['self_funding'] == Money(10_00)


def test_a_person_without_an_fec_id_is_unknown_not_zero():
    career, current, latest = person_summary(person('p'), FINANCES)
    assert set(career.values()) == {None} and set(current.values()) == {None}
    assert latest == ''


def test_a_person_with_no_weball_rows_has_null_stocks_and_a_note():
    rows, persons = self_funding_by_person(
        Roster([person('quiet', 'H9')]), FINANCES, coverage_end={}, differing=[]
    )
    (row,) = rows
    assert row['cash_on_hand_career'] == ''
    assert row['self_funding_career'] == '0.00'
    assert row['data_notes'] == 'no weball rows found'
    assert persons['quiet']['per_cycle'] == []


def test_per_cycle_entries_carry_their_coverage_date():
    _, persons = self_funding_by_person(
        Roster([person('p', 'S1')]),
        FINANCES,
        coverage_end={('S1', 2026): '10/14/2026'},
        differing=[],
    )
    entries = persons['p']['per_cycle']
    assert [(e['cycle'], e['coverage_end_date']) for e in entries] == [
        (2024, ''),
        (2026, '10/14/2026'),
    ]

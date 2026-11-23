import pytest

from receipts.domain.campaign_finances import CampaignFinances
from receipts.domain.money import ZERO, Money
from receipts.domain.weball_double_counts import FINANCIAL_FIELDS, remove_double_counts


def weball_amounts(**cents):
    return {field: Money(cents.get(field, 0)) for field in FINANCIAL_FIELDS}


def test_finances_map_weball_fields_and_sum_loan_repayments():
    finances = CampaignFinances.from_weball(
        weball_amounts(
            cash_end=500,
            candidate_contributions=100,
            candidate_loans=250,
            candidate_loan_repayments=30,
            other_loan_repayments=20,
        )
    )
    assert finances.cash_on_hand == Money(500)
    assert finances.loan_repayments == Money(50)
    assert finances.self_funding == Money(350)


def test_a_cycle_with_only_zeros_has_no_money():
    assert not CampaignFinances.from_weball(weball_amounts())
    assert CampaignFinances.from_weball(weball_amounts(debts_owed_by=1))


def record(**overrides):
    return {
        'person_key': 'P1',
        'name': 'Pat',
        'cycle': 2024,
        'kept_id': 'S1',
        'dropped_ids': ['H1'],
        'amount': '10.00',
        **overrides,
    }


def test_identical_columns_of_the_dropped_copy_are_zeroed():
    amounts = {
        ('S1', 2024): weball_amounts(individual_contributions=1000, total_receipts=5000),
        ('H1', 2024): weball_amounts(individual_contributions=1000, total_receipts=5000),
    }
    report = remove_double_counts(amounts, [record()], {'P1'})

    assert amounts['H1', 2024]['total_receipts'] == ZERO
    assert amounts['S1', 2024]['total_receipts'] == Money(5000)
    assert (report.groups_applied, report.cells_zeroed, report.differing) == (1, 2, [])


def test_a_differing_column_is_flagged_not_corrected():
    amounts = {
        ('S1', 2024): weball_amounts(individual_contributions=1000, total_receipts=5000),
        ('H1', 2024): weball_amounts(individual_contributions=1000, total_receipts=4000),
    }
    report = remove_double_counts(amounts, [record()], {'P1'})

    assert amounts['H1', 2024]['total_receipts'] == Money(4000)
    assert [(dropped_id, field) for _, dropped_id, field, _, _ in report.differing] == [
        ('H1', 'total_receipts')
    ]


def test_the_recorded_amount_must_match_both_copies():
    amounts = {
        ('S1', 2024): weball_amounts(individual_contributions=999),
        ('H1', 2024): weball_amounts(individual_contributions=1000),
    }
    with pytest.raises(SystemExit):
        remove_double_counts(amounts, [record()], {'P1'})

from receipts.domain.committee_money import is_voided_earmark, reported_once
from receipts.domain.money import Money
from receipts.fec.committee_contributions import CommitteeContribution


def contribution(**overrides):
    blank = dict.fromkeys(CommitteeContribution._fields, '')
    defaults = {'committee_id': 'C1', 'candidate_id': 'H1', 'amount_text': '500',
                'transaction_id': 'T1', 'file_number_text': '10'}
    return CommitteeContribution(**{**blank, **defaults, **overrides})


def test_only_a_negative_earmark_is_a_voided_earmark():
    assert is_voided_earmark(contribution(memo_text='EARMARK OF A', amount_text='-250'))
    assert not is_voided_earmark(contribution(memo_text='EARMARK OF A', amount_text='250'))
    assert not is_voided_earmark(contribution(memo_text='VOIDED CHECK', amount_text='-250'))


def test_a_contribution_reported_twice_counts_once():
    reported = reported_once()
    reported.add(contribution())
    reported.add(contribution(file_number_text='11'))

    assert [c.file_number for c in reported] == [10]
    assert [c.amount for c in reported.dropped] == [Money(50000)]


def test_non_memo_row_wins_over_memo_row():
    reported = reported_once()
    reported.add(contribution(memo_code='X', file_number_text='5'))
    reported.add(contribution(file_number_text='9'))

    assert [(c.is_memo, c.file_number) for c in reported] == [(False, 9)]


def test_distinct_contributions_sharing_a_transaction_id_both_count():
    reported = reported_once()
    reported.add(contribution(amount_text='500'))
    reported.add(contribution(amount_text='750'))

    assert sorted(c.amount.cents for c in reported) == [50000, 75000]
    assert reported.dropped == []

from receipts.domain.money import Money
from receipts.fec.bulk_file import BulkFile
from receipts.fec.committee_contributions import CommitteeContribution
from receipts.fec.committees import Committee


def contribution(**overrides):
    blank = dict.fromkeys(CommitteeContribution._fields, '')
    return CommitteeContribution(**{**blank, **overrides})


def committee(**overrides):
    blank = dict.fromkeys(Committee._fields, '')
    return Committee(**{**blank, **overrides})


def test_bulk_file_names_fields_and_counts_malformed_rows(tmp_path):
    path = tmp_path / 'cm.txt'
    good = '|'.join(['C001', 'ACME PAC'] + [''] * 7 + ['Q', '', '', 'C', '', ''])
    path.write_text(good + '\nC002|too|short\n')
    rows = BulkFile(path, Committee)

    parsed = list(rows)

    assert [c.committee_id for c in parsed] == ['C001']
    assert parsed[0].is_corporate_pac
    assert (rows.rows_read, rows.malformed_rows) == (2, 1)


def test_corporate_pac_needs_pac_type_and_corporate_sponsor():
    assert committee(committee_type='Q', organization_type='C').is_corporate_pac
    assert committee(committee_type='N', organization_type='W').is_corporate_pac
    assert not committee(committee_type='Q', organization_type='L').is_corporate_pac
    assert not committee(committee_type='H', organization_type='C').is_corporate_pac


def test_only_direct_contributions_count_as_to_candidate():
    assert contribution(transaction_type='24K').is_to_candidate
    assert contribution(transaction_type='24P').is_to_candidate
    assert not contribution(transaction_type='24Z').is_to_candidate


def test_earmark_is_read_from_the_memo_text():
    assert contribution(memo_text='EARMARK OF JANE DOE').is_earmark
    assert contribution(memo_text='ERMK: JANE DOE').is_earmark
    assert not contribution(memo_text='VOIDED CHECK').is_earmark


def test_identity_falls_back_to_submission_id_and_ignores_filing():
    first = contribution(committee_id='C1', candidate_id='H1', amount_text='500',
                         submission_id='S9', file_number_text='10')
    refiled = first._replace(file_number_text='11', memo_code='X')
    other_amount = first._replace(amount_text='501')

    assert first.identity == refiled.identity
    assert first.identity != other_amount.identity
    assert first.amount == Money(50000)


def test_unreadable_file_number_is_zero():
    assert contribution(file_number_text='abc').file_number == 0
    assert contribution(file_number_text='').file_number == 0
    assert contribution(file_number_text='1899771').file_number == 1899771

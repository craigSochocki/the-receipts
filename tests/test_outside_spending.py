import pytest

from receipts.domain.money import ZERO, Money
from receipts.domain.outside_spending import (
    BLANK_CANDIDATE,
    CANDIDATE_NOT_IDENTIFIED,
    UNREGISTERED_COMMITTEE,
    exclusion,
    latest_filings,
)
from receipts.fec.independent_expenditures import IndependentExpenditure, independent_expenditures


def expenditure(position=0, **fields):
    blank = dict.fromkeys(IndependentExpenditure._fields[:-1], '')
    defaults = {
        'spe_id': 'C1',
        'cand_id': 'H1',
        'tran_id': 'SE.1',
        'exp_amo': '100',
        'receipt_dat': '01-OCT-26',
        'file_num': '10',
        'fec_election_yr': '2026',
    }
    return IndependentExpenditure(**{**blank, **defaults, **fields}, position=position)


def test_amounts_are_exact_and_tolerate_currency_formatting():
    assert expenditure(exp_amo='1234.56').amount == Money(123456)
    assert expenditure(exp_amo='$1,000').amount == Money(100000)
    assert expenditure(exp_amo='').amount == ZERO
    with pytest.raises(ValueError):
        _ = expenditure(exp_amo='n/a').amount


def test_an_amended_filing_replaces_the_original():
    filings = latest_filings()
    filings.add(expenditure(exp_amo='100', receipt_dat='01-OCT-26'))
    filings.add(expenditure(exp_amo='150', receipt_dat='05-OCT-26'))
    filings.add(expenditure(exp_amo='90', receipt_dat='03-OCT-26'))

    assert [e.amount for e in filings] == [Money(15000)]
    assert len(filings.dropped) == 2


def test_same_receipt_date_keeps_the_higher_file_number():
    filings = latest_filings()
    filings.add(expenditure(exp_amo='100', file_num='12'))
    filings.add(expenditure(exp_amo='200', file_num='11'))

    assert [e.amount for e in filings] == [Money(10000)]


def test_rows_without_a_transaction_id_never_merge():
    filings = latest_filings()
    filings.add(expenditure(position=1, tran_id=''))
    filings.add(expenditure(position=2, tran_id=''))

    assert len(list(filings)) == 2


def test_the_same_transaction_id_from_two_spenders_stays_separate():
    filings = latest_filings()
    filings.add(expenditure(spe_id='C1'))
    filings.add(expenditure(spe_id='C2'))

    assert len(list(filings)) == 2


def test_exclusion_reasons_apply_in_order():
    registered, identified = {'C1'}, {'H1'}
    assert (
        exclusion(expenditure(spe_id='C9', cand_id=''), registered, identified)
        == UNREGISTERED_COMMITTEE
    )
    assert exclusion(expenditure(cand_id=' '), registered, identified) == BLANK_CANDIDATE
    assert exclusion(expenditure(cand_id='H9'), registered, identified) == CANDIDATE_NOT_IDENTIFIED
    assert exclusion(expenditure(), registered, identified) is None


def test_reads_the_bulk_csv_into_named_records(tmp_path):
    folder = tmp_path / '2026'
    folder.mkdir()
    header = ','.join(IndependentExpenditure._fields[:-1])
    row = ','.join(
        '"%s"' % v
        for v in ['H1', 'DOE, JANE', 'C1'] + [''] * 6 + ['2500'] + [''] * 10 + ['2026', '', '']
    )
    (folder / 'independent_expenditure_2026.csv').write_text(header + '\n' + row + '\n')
    rows = independent_expenditures(tmp_path, 2026)

    parsed = list(rows)

    assert [(e.candidate_id, e.amount, e.cycle) for e in parsed] == [('H1', Money(250000), 2026)]
    assert rows.rows_read == 1

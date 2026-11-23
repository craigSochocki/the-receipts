import copy
import json
from pathlib import Path

import pytest

from receipts.ingest import pull_f6, pull_f24
from receipts.ingest import pull_freshness as freshness

EVIDENCE = Path(__file__).resolve().parents[1] / 'data' / 'evidence'
F6_CSV = (EVIDENCE / 'f6_2044138.csv').read_text()  # Constantino's Oct 29, 2026 48-hour notice


def recorded(name):
    return json.loads((EVIDENCE / name).read_text())


# Every Schedule E row the API returned for UDP vs El-Sayed, 2026 (recorded Nov 12, 2026).
EL_SAYED_ROWS = recorded('schede_elsayed.json')['results']


class RecordedApi:
    """Answers each path with a recorded response; records the params it was asked."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, path, params):
        self.calls.append((path, params))
        answer = self.responses[path]
        return copy.deepcopy(answer(params) if callable(answer) else answer)

    def fetch_text(self, url):
        self.calls.append((url, None))
        return F6_CSV


@pytest.fixture
def use_api(monkeypatch):
    def install(responses):
        api = RecordedApi(responses)
        for module in (pull_f6, pull_f24, freshness):
            monkeypatch.setattr(module, 'fec_api', api)
        return api

    return install


def test_the_f6_csv_header_and_line_item():
    parsed = pull_f6.parse_f6_csv(F6_CSV)
    assert parsed['header']['candidate_id'] == 'H6NY21157'
    assert parsed['header']['committee_name'] == 'CONSTANTINO FOR CONGRESS, INC.'
    assert parsed['header']['filing_date'] == '20261029'
    [item] = parsed['items']
    assert item['contributor_type'] == 'CAN' and item['is_candidate']
    assert item['amount'] == 1_000_000.0
    assert item['date'] == '2026-10-29'
    assert (item['employer'], item['occupation']) == ('STICKER MULE', 'CEO')


def test_amounts_and_dates_are_read_leniently():
    assert pull_f6.parse_amount(' 1,250.50 ') == 1250.5
    assert pull_f6.parse_amount('') == 0.0
    assert pull_f6.parse_amount('n/a') is None
    assert pull_f6.parse_date('20261029') == '2026-10-29'
    assert pull_f6.parse_date(' 10/29/2026 ') == '10/29/2026'


def test_short_rows_read_missing_fields_as_blank():
    parsed = pull_f6.parse_f6_csv('"F65","C00892737","F6.01","IND"\n')
    assert parsed['items'][0]['amount'] == 0.0
    assert parsed['items'][0]['employer'] == ''
    assert not parsed['items'][0]['is_candidate']


def test_only_the_latest_filing_in_an_amendment_chain_counts():
    filings = [
        {'file_number': 2045386, 'amendment_chain': [2044921, 2045386]},
        {'file_number': 2044921, 'amendment_chain': [2044921]},
    ]
    assert pull_f6.superseded_file_numbers(filings) == {2044921}


def test_a_committee_pull_splits_candidate_loans_from_contributions(use_api):
    use_api({'/filings/': recorded('f6_constantino.json')})
    report = pull_f6.pull_committee('C00892737', since='2026-10-15')
    assert report['n_filings'] == 1
    assert report['total_candidate_loans'] == 1_000_000.0
    assert report['total_contributions'] == 0.0
    assert report['filings'][0]['candidate_id'] == 'H6NY21157'


def test_f6_discovery_stops_before_the_window(use_api):
    use_api({'/filings/': recorded('f6_constantino.json')})
    assert pull_f6.discover_f6('C00892737', since='2026-10-30') == []


def f24_only(params):
    rows = EL_SAYED_ROWS
    if params.get('filing_form') == 'F24':
        rows = [r for r in rows if r['filing_form'] == 'F24']
    return {'results': rows, 'pagination': {}}


def test_the_f24_sweep_reconciles_against_the_double_returned_rows(use_api):
    use_api({'/schedules/schedule_e/': f24_only})
    result = pull_f24.sweep('C00799031', 'S6MI00418', 2026)
    assert result['naive_total'] == 41_044_346.31
    assert result['deduped_total'] == 20_904_442.10
    assert result['residual_unexplained'] == 0
    assert result['residual'] == result['residual_explained']
    assert {r['filing_form'] for r in result['residual_rows']} == {'F3X'}


def test_schedule_e_follows_the_cursor(use_api, monkeypatch):
    monkeypatch.setattr(pull_f24, 'PER_PAGE', 5)
    first = recorded('schede_f24.json')  # 5 rows per page, with a last_indexes cursor
    pages = iter([first, {'results': []}])
    api = use_api({'/schedules/schedule_e/': lambda params: next(pages)})
    rows = pull_f24.fetch_schedule_e('C00799031', 'S6MI00418', 2026, 'F24')
    assert len(rows) == 5
    assert 'last_index' not in api.calls[0][1]
    assert api.calls[1][1]['last_index'] == first['pagination']['last_indexes']['last_index']


def test_a_repeated_schedule_e_page_stops_the_sweep(use_api, monkeypatch):
    monkeypatch.setattr(pull_f24, 'PER_PAGE', 5)
    use_api({'/schedules/schedule_e/': recorded('schede_f24.json')})
    with pytest.raises(SystemExit, match='repeated the same page'):
        pull_f24.fetch_schedule_e('C00799031', cycle=2026)


def test_a_full_schedule_e_page_without_a_cursor_stops_the_sweep(use_api, monkeypatch):
    monkeypatch.setattr(pull_f24, 'PER_PAGE', 5)
    page = {**recorded('schede_f24.json'), 'pagination': {}}
    use_api({'/schedules/schedule_e/': page})
    with pytest.raises(SystemExit, match='no pagination.last_indexes cursor'):
        pull_f24.fetch_schedule_e('C00799031', cycle=2026)


def test_f24_rows_are_attributed_by_candidate_and_every_dollar_lands_once():
    rows = [r for r in EL_SAYED_ROWS if r['filing_form'] == 'F24']
    rows += [
        {**rows[0], 'candidate_id': 'H9XX00000'},
        {**rows[0], 'candidate_id': None},
        {**rows[0], 'support_oppose_indicator': None},
    ]
    by_candidate = {'S6MI00418': {'person_key': 'abdulelsayedmisenate'}}
    attributed, non_roster, unclassified, n_unclassified = freshness.attribute_f24_rows(
        rows, by_candidate
    )
    [el_sayed] = attributed
    assert el_sayed['person_key'] == 'abdulelsayedmisenate'
    assert el_sayed['n_rows'] == len(rows) - 2
    assert non_roster['n_rows'] == 2
    assert n_unclassified == 1 and unclassified == rows[-1]['expenditure_amount']
    total = round(sum(float(r['expenditure_amount']) for r in rows), 2)
    assert round(el_sayed['total'] + non_roster['total'], 2) == total
    for tally in (el_sayed, non_roster):
        parts = tally['support'] + tally['oppose'] + tally['unclassified']
        assert round(parts, 2) == tally['total']


def test_totals_newer_than_the_bulk_cutoff_are_flagged(use_api):
    totals = recorded('constantino_totals_2026.json')  # coverage ends 2026-10-14, the cutoff
    use_api({'/candidate/H6NY21157/totals/': totals})
    row = freshness.totals_refresh('H6NY21157')
    assert row['found'] and not row['newer_than_bulk']
    assert row['total_receipts'] == 14_464_951.19
    totals['results'][0]['coverage_end_date'] = '2026-10-31T00:00:00'
    assert freshness.totals_refresh('H6NY21157')['newer_than_bulk']


def test_principal_committees_are_designation_p(use_api):
    use_api({'/candidate/H6NY21157/committees/': recorded('constantino_committees.json')})
    assert freshness.principal_committees('H6NY21157') == ['C00892737']


def test_the_snapshot_keeps_file_numbers_not_whole_filings():
    decision = {
        'gated': True,
        'families': {'F6': {'n_new_filings': 1, 'new_filings': [{'file_number': 7}]}},
        'new_state': {'families': {}},
    }
    record = freshness.snapshot_gate_record(decision)
    assert record['families']['F6'] == {'n_new_filings': 1, 'new_filing_file_numbers': [7]}
    assert 'new_state' not in record
    assert freshness.snapshot_gate_record(None)['reason'] == 'gate did not run'


def test_the_summary_adds_up_the_legs():
    entries = [
        {
            'person_key': 'p',
            'totals': [{'candidate_id': 'H1', 'newer_than_bulk': True}],
            'f6': [{'total_candidate_loans': 10.004, 'total_contributions': 2.0}],
            'f24': [{'f24_total': 5.0, 'residual_unexplained': 1.5, 'committee_id': 'C1'}],
        }
    ]
    sweeps = [{'committee_id': 'C2', 'f24_total': 3.0, 'residual_unexplained': 0}]
    summary = freshness.summarize(entries, sweeps)
    assert summary['new_f6_candidate_loans'] == 10.0
    assert summary['new_f24_ie'] == 5.0
    assert summary['totals_newer_than_bulk'] == ['H1']
    assert summary['open_f24_residuals'][0]['residual_unexplained'] == 1.5
    assert summary['committee_sweeps_f24_ie'] == 3.0
    assert summary['committee_sweeps_open_residuals'] == []
    assert summary['gate_applied'] is False

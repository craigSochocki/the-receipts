import copy
import json
from pathlib import Path

import pytest

from receipts.ingest import pull_gate

EVIDENCE = Path(__file__).resolve().parents[1] / 'data' / 'evidence'
# Five newest F6 filings, recorded live Nov 12, 2026: received Nov 11, 10, 10, 9, 9.
RECENT_F6 = json.loads((EVIDENCE / 'f6_all.json').read_text())['results']

# The same committees' rows in the 2026 committee master (designation, CAND_ID).
COMMITTEE_MAP = {
    'C00632257': {'candidate_id': 'H6FL18097', 'designation': 'P'},
    'C00943563': {'candidate_id': 'H6MP01027', 'designation': 'P'},
    'C00787812': {'candidate_id': 'H2IL13153', 'designation': 'P'},
    'C00366948': {'candidate_id': 'H2MA09072', 'designation': 'P'},
    'C00536680': {'candidate_id': 'H2CA06259', 'designation': 'P'},
    'C00799031': {'candidate_id': None, 'designation': 'U'},
}
BY_CANDIDATE = {
    'H6FL18097': {'person_key': 'M001199'},
    'H2IL13153': {'person_key': 'B001315'},
    'H2MA09072': {'person_key': 'L000562'},
    'H2CA06259': {'person_key': 'H001068'},
}


class RecordedFilings:
    """/filings/ answering every form family with the recorded rows, one page per call."""

    def __init__(self, rows=RECENT_F6, per_page=None, pages=1):
        self.rows = rows
        self.pages = pages
        self.calls = []

    def get(self, path, params):
        self.calls.append((path, params))
        if params['page'] > self.pages:
            return {'results': []}
        return {'results': copy.deepcopy(self.rows)}


def test_filings_after_the_last_seen_day_are_new():
    result = pull_gate.check_family('F6', '2026-11-10', api=RecordedFilings(), per_page=100)
    assert result['newest_seen'] == '2026-11-11'
    assert [r['file_number'] for r in result['new_filings']] == [2047161, 2047047, 2047075]
    assert result['n_rows_scanned'] == 3
    assert result['boundary_file_numbers'] == [2047161]
    assert result['calls_used'] == 1


def test_the_boundary_day_is_rescanned_but_seen_filings_are_not_new():
    result = pull_gate.check_family(
        'F6', '2026-11-10', seen_file_numbers=[2047047], api=RecordedFilings(), per_page=100
    )
    assert [r['file_number'] for r in result['new_filings']] == [2047161, 2047075]


def test_nothing_new_is_a_skip():
    result = pull_gate.check_family(
        'F6', '2026-11-11', seen_file_numbers=[2047161], api=RecordedFilings(), per_page=100
    )
    assert result['skipped'] and result['new_filings'] == []


def test_full_pages_keep_paging_until_the_window_ends():
    api = RecordedFilings(pages=2)
    result = pull_gate.check_family('F6', '2026-10-15', api=api, per_page=5)
    assert result['calls_used'] == 3
    assert result['n_rows_scanned'] == 10


def test_the_page_guard_is_an_error_not_a_skip():
    with pytest.raises(RuntimeError, match='max_pages=2'):
        pull_gate.check_family(
            'F6', '2026-10-15', api=RecordedFilings(pages=9), per_page=5, max_pages=2
        )


def test_an_unexpected_response_is_an_error_not_a_skip():
    class Broken:
        def get(self, path, params):
            return {'error': 'oops'}

    with pytest.raises(ValueError, match='unexpected /filings/ response shape'):
        pull_gate.check_family('F6', '2026-10-15', api=Broken())


def test_filings_map_through_the_committee_master_to_roster_people():
    def person(committee_id):
        return pull_gate.map_filing_to_person(
            {'committee_id': committee_id}, COMMITTEE_MAP, BY_CANDIDATE
        )

    assert person('C00632257') == ('M001199', None)
    assert person('C00943563') == (None, 'candidate_not_on_roster')
    assert person('C00799031') == (None, 'no_candidate_id')
    assert person('C99999999') == (None, 'unknown_committee')
    assert person(None) == (None, 'unknown_committee')


def gate(api, families=('F6', 'F24', 'F3'), state=None):
    return pull_gate.gate_run(
        by_candidate=BY_CANDIDATE,
        state=state or pull_gate.default_state(list(families)),
        api=api,
        committee_map=COMMITTEE_MAP,
        families=list(families),
    )


def test_the_gate_names_who_has_new_filings_per_leg():
    decision = gate(RecordedFilings())
    assert not decision['run_full']
    assert decision['f6_person_keys'] == ['B001315', 'H001068', 'L000562', 'M001199']
    assert decision['totals_person_keys'] == decision['f6_person_keys']
    assert [f['committee_id'] for f in decision['unattributed_filings']] == ['C00943563'] * 2
    assert decision['f24_sweep_committees'] == []
    assert set(decision['non_sweep_f24_committees']) == {r['committee_id'] for r in RECENT_F6}
    assert decision['non_sweep_f24_committees']['C00787812'] == {
        'n_filings': 1,
        'file_numbers': [2047075],
        'latest_receipt_date': '2026-11-10',
    }
    assert decision['calls_used'] == 3
    families = decision['new_state']['families']
    assert families['F6'] == {'last_seen': '2026-11-11', 'seen_file_numbers': [2047161]}


def test_an_f24_from_a_sweep_committee_runs_that_sweep():
    sweep_id = pull_gate.sweep_committees()[0]['committee_id']
    rows = [{**RECENT_F6[0], 'committee_id': sweep_id}]
    decision = gate(RecordedFilings(rows), families=['F24'])
    assert [c['committee_id'] for c in decision['f24_sweep_committees']] == [sweep_id]
    assert len(decision['f24_sweeps_skipped']) == len(pull_gate.sweep_committees()) - 1


def test_non_principal_committees_are_recorded():
    cmap = {**COMMITTEE_MAP, 'C00632257': {'candidate_id': 'H6FL18097', 'designation': 'A'}}
    decision = pull_gate.gate_run(
        by_candidate=BY_CANDIDATE,
        state=pull_gate.default_state(['F6']),
        api=RecordedFilings(RECENT_F6[:1]),
        committee_map=cmap,
        families=['F6'],
    )
    assert decision['non_principal_committee_filings'][0]['designation'] == 'A'
    assert decision['f6_person_keys'] == ['M001199']


def test_nothing_new_anywhere_skips_all():
    state = pull_gate.default_state(['F6'])
    state['families']['F6'] = {'last_seen': '2026-11-11', 'seen_file_numbers': [2047161]}
    decision = gate(RecordedFilings(), families=['F6'], state=state)
    assert decision['all_skipped']
    assert decision['new_state']['families']['F6'] == state['families']['F6']


def test_a_gate_error_runs_everything_and_keeps_state(capsys):
    class RateLimited:
        def get(self, path, params):
            raise SystemExit('FEC API /filings/ failed: HTTP 429')

    decision = gate(RateLimited())
    assert decision['run_full']
    assert decision['gate_error'] == {'family': 'F6', 'error': 'FEC API /filings/ failed: HTTP 429'}
    assert decision['new_state'] is None
    assert 'GATE ERROR in family F6' in capsys.readouterr().err


def test_a_malformed_state_file_is_never_reset(tmp_path):
    path = tmp_path / 'state.json'
    path.write_text('{not json')
    with pytest.raises(ValueError, match='refusing to reset the baseline'):
        pull_gate.load_state(path)


def test_a_missing_family_gets_no_baseline(tmp_path):
    path = tmp_path / 'state.json'
    path.write_text(json.dumps({'families': {'F6': {'last_seen': '2026-11-01'}}}))
    state = pull_gate.load_state(path)
    assert state['families']['F6'] == {'last_seen': '2026-11-01', 'seen_file_numbers': []}
    assert state['families']['F3'] == {'last_seen': None, 'seen_file_numbers': []}

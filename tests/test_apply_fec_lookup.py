import pytest

from receipts.transform.apply_fec_lookup import (
    apply_lookup_results,
    apply_note_appends,
    public_roster,
)


def row(key, last='Zed', first='Ann', ids=None, notes=''):
    return {'person_key': key, 'last_name': last, 'first_name': first,
            'fec_candidate_ids': ids or [], 'notes': notes, '_bioguide': key}  # fmt: skip


def test_found_ids_are_set_and_labeled_by_how_they_were_found():
    rows = [row('a'), row('b'), row('c')]
    counts = apply_lookup_results(
        rows,
        {
            'a': {'status': 'found', 'value': 'H1'},
            'b': {'status': 'found-manual', 'value': 'H2'},
            'c': {'status': 'ambiguous', 'value': None},
        },
        cycle=2026,
    )
    assert counts == {'found': 1, 'found-manual': 1, 'skipped': 1}
    assert (rows[0]['fec_candidate_ids'], rows[0]['_fec_source']) == (['H1'], 'fec-api-2026')
    assert rows[1]['_fec_source'] == 'fec-api-2026-manual'
    assert rows[2]['fec_candidate_ids'] == [] and '_fec_source' not in rows[2]


def test_a_result_for_someone_off_the_roster_stops_the_run():
    with pytest.raises(SystemExit, match='unknown person_key ghost'):
        apply_lookup_results([row('a')], {'ghost': {'status': 'found', 'value': 'H1'}}, 2026)


def test_a_note_append_lands_once():
    rows = [row('a', notes='Seated.'), row('b', notes='Seated. Filed as J. Doe.')]
    notes = {'a': ' Filed as J. Doe.', 'b': ' Filed as J. Doe.'}
    assert apply_note_appends(rows, notes) == (1, 1)
    assert rows[0]['notes'] == rows[1]['notes'] == 'Seated. Filed as J. Doe.'
    assert apply_note_appends(rows, notes) == (0, 2)


def test_the_public_roster_drops_working_fields_puts_ids_last_and_sorts_by_name():
    public = public_roster([row('b', last='barragán', ids=['H2']), row('a', last='Adams')])
    assert [r['person_key'] for r in public] == ['a', 'b']
    assert list(public[0])[-1] == 'fec_candidate_ids'
    assert not any(k.startswith('_') for r in public for k in r)

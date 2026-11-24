from receipts.transform.fec_lookup import choose, look_up_missing, matching_candidates

PARTY = {'Democrat': 'DEM', 'Republican': 'REP'}


def person(key='p', first='Ann', last='Able', chamber='House', district='3', party='Democrat'):
    return {'person_key': key, 'full_name': f'{first} {last}', 'first_name': first,
            'last_name': last, 'state': 'NY', 'chamber_120': chamber, 'chamber_119': '',
            'district_120': district, 'district_119': '', 'party_120': party,
            'party_119': '', 'fec_candidate_ids': []}  # fmt: skip


def candidate(cid, name='ABLE, ANN', office='H', district='03', party='DEM', years=(2026,)):
    return {'candidate_id': cid, 'name': name, 'state': 'NY', 'office': office,
            'district_number': district, 'party': party, 'election_years': list(years)}  # fmt: skip


def test_candidates_must_match_seat_party_and_cycle():
    candidates = [
        candidate('H_OK'),
        candidate('H_WRONG_DISTRICT', district='04'),
        candidate('H_WRONG_PARTY', party='REP'),
        candidate('H_OLD', years=(2020,)),
        candidate('S_WRONG_OFFICE', office='S'),
    ]
    matching = matching_candidates(person(), candidates, 2026, PARTY)
    assert [c['candidate_id'] for c in matching] == ['H_OK']


def test_one_match_is_found_and_several_are_settled_by_first_name_or_left_ambiguous():
    assert choose(person(), [candidate('H1')], []) == ('found', 'H1')
    two = [candidate('H1', name='ABLE, BOB'), candidate('H2', name='ABLE, ANN')]
    assert choose(person(), two, two) == ('found', 'H2')
    assert choose(person(first='Cy'), two, two) == ('ambiguous', ['H1', 'H2'])


def test_no_match_reports_what_the_api_returned():
    assert choose(person(), [], [candidate('H9')]) == ('not_found', ['H9'])


def test_found_ids_are_set_and_a_rate_limit_stops_the_run():
    rows = [person('a'), person('b', first='Bo', last='Bee'), person('c')]
    answers = iter([([candidate('H1')], None), (None, ('http_error', 429))])
    results = look_up_missing(
        rows, 2026, PARTY, search=lambda params: next(answers), pause=lambda seconds: None
    )
    assert results['a']['status'] == 'found' and rows[0]['fec_candidate_ids'] == ['H1']
    assert rows[0]['_fec_source'] == 'fec-api-2026'
    assert results['b'] == {'name': 'Bo Bee', 'state': 'NY', 'status': 'http_error', 'value': 429}
    assert 'c' not in results

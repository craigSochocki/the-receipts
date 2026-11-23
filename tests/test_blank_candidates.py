from src.domain.blank_candidates import name_key, roster_matches

PEOPLE = [
    {'last_name': 'Davis', 'first_name': 'Donald', 'state': 'NC', 'district_119': 1},
    {'last_name': 'Davis', 'first_name': 'Danny', 'state': 'IL', 'district_119': 7},
    {'last_name': 'Mullin', 'first_name': 'Markwayne', 'state': 'OK', 'district_120': None},
]


def test_matches_on_last_name_first_initial_state_and_district():
    assert roster_matches('DAVIS, DON', 'NC', '01', PEOPLE) == [PEOPLE[0]]
    assert roster_matches('DAVIS, DON', 'NC', '02', PEOPLE) == []


def test_a_name_without_a_comma_is_matched_as_a_last_name():
    assert roster_matches('Mullin', 'OK', '00', PEOPLE) == [PEOPLE[2]]


def test_name_key_ignores_case_of_the_name_only():
    assert name_key('Davis, Don', 'NC', '01', 'H') == ('DAVIS, DON', 'NC', '01', 'H')


from collections import namedtuple

from src.domain.blank_candidates import resolve

Row = namedtuple('Row', 'candidate_name state district office direction')
WITH_IDS = [{**PEOPLE[0], 'fec_candidate_ids': ['H2NC01999']},
            {**PEOPLE[1], 'fec_candidate_ids': ['H4IL07001', 'S6IL00001']}]


def test_the_name_index_wins_then_the_roster():
    row = Row('DAVIS, DON', 'NC', '01', 'H', 'S')
    assert resolve(row, {name_key('DAVIS, DON', 'NC', '01', 'H'): 'H0FROMINDEX'}, WITH_IDS) == (
        'H0FROMINDEX', 'name_index')
    assert resolve(row, {}, WITH_IDS) == ('H2NC01999', 'roster')


def test_a_roster_match_with_two_ids_stays_unresolved():
    assert resolve(Row('DAVIS, DANNY', 'IL', '07', 'H', 'S'), {}, WITH_IDS) == (None, None)


def test_an_unknown_supported_candidate_gets_a_name_stand_in_and_opposed_gets_nothing():
    assert resolve(Row('Irwin, Steven', 'PA', '12', 'H', 'S'), {}, WITH_IDS) == (
        '__name__:IRWIN, STEVEN|PA|12|H', 'name_only')
    assert resolve(Row('Irwin, Steven', 'PA', '12', 'H', 'O'), {}, WITH_IDS) == (None, None)

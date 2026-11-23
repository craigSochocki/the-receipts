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

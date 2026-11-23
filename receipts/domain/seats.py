"""Seats in Congress: stable positions that races are held for and members hold.

A House seat is a district under one map; when a state redraws its map
the districts become new seats. A Senate seat is a state's seat in one
of the three classes, one class up for election every two years.
"""

DELEGATE_STATES = ('AS', 'DC', 'GU', 'MP', 'PR', 'VI')
FIRST_ELECTION_COVERED = 2024
SENATE_TERM_END = {1: '2031-01-03', 2: '2033-01-03', 3: '2029-01-03'}


def house_map_year(state, election_year, new_map_states):
    """The first covered election that used the state's map for `election_year`."""
    if election_year >= 2026 and state in new_map_states:
        return 2026
    return FIRST_ELECTION_COVERED


def house_seat_id(state, district, election_year, new_map_states):
    return f'H-{state}-{int(district):02d}/{house_map_year(state, election_year, new_map_states)}'


def senate_seat_id(state, senate_class):
    return f'S-{state}-{senate_class}'


def regular_senate_class(election_year):
    """The class up for regular election: 2024 → 1, 2026 → 2, 2028 → 3."""
    return (election_year - 2024) // 2 % 3 + 1

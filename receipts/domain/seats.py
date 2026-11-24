"""Seats in Congress: a House district under one map, or a state's Senate class."""

DELEGATE_STATES = ('AS', 'DC', 'GU', 'MP', 'PR', 'VI')


def congress_elected_in(year):
    """The Congress an election year seats: 2 years per Congress, the 1st elected in 1788."""
    return (year - 1788) // 2 + 1


def congress_start(congress):
    return f'{1787 + 2 * congress}-01-03'


def regular_senate_class(election_year):
    """The Senate class up for regular election: classes 1, 2, 3 rotate on a six-year cycle."""
    return (election_year % 6) // 2 or 3


def senate_term_end(senate_class, after_year):
    """The day a term in `senate_class` ends, for a term won after `after_year`."""
    year = after_year + 2
    while regular_senate_class(year) != senate_class:
        year += 2
    return f'{year + 1}-01-03'


def house_map_year(state, election_year, new_maps, first_election):
    """The first covered election that used the state's map for `election_year`."""
    years = [y for y, states in new_maps.items() if y <= election_year and state in states]
    return max(years, default=first_election)


def house_seat_id(state, district, election_year, new_maps, first_election):
    map_year = house_map_year(state, election_year, new_maps, first_election)
    return f'H-{state}-{int(district):02d}/{map_year}'


def senate_seat_id(state, senate_class):
    return f'S-{state}-{senate_class}'

"""Seats, terms and candidacies for the silver store."""
from collections import defaultdict

import yaml

from receipts.domain.seats import (DELEGATE_STATES, SENATE_TERM_END, house_seat_id,
                              regular_senate_class, senate_seat_id)
from receipts.fec.candidates import candidates

CONGRESS_119 = ('2025-01-03', '2027-01-03')
CONGRESS_120 = ('2027-01-03', '2029-01-03')
LEGISLATORS = 'congress-legislators (data/source/legislators-*.yaml)'
ROSTER_120 = '120th roster: media calls, unofficial until certified (data/source/120th_roster.json)'
CONGRESS_TYPES = {'rep': 'House', 'sen': 'Senate'}
CANDIDATE_OFFICES = {'H': 'House', 'S': 'Senate'}


def read_legislators(source_dir):
    loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
    people = []
    for name in ('legislators-current.yaml', 'legislators-historical.yaml'):
        with open(source_dir / name) as f:
            people.extend(yaml.load(f, Loader=loader))
    return people


def served_in_119th(term):
    start, end = CONGRESS_119
    return term['type'] in CONGRESS_TYPES and term['start'] < end and term['end'] > start


def terms_119th(legislators, new_map_states):
    for person in legislators:
        for term in person.get('terms', []):
            if not served_in_119th(term):
                continue
            state = term['state']
            if term['type'] == 'rep':
                seat = house_seat_id(state, term['district'], 2024, new_map_states)
            else:
                seat = senate_seat_id(state, term['class'])
            yield {'person_key': person['id']['bioguide'], 'seat_id': seat, 'congress': 119,
                   'start_date': term['start'], 'end_date': term['end'],
                   'party': term.get('party'), 'source': LEGISLATORS}


def terms_120th(roster, new_map_states):
    for person in roster:
        if person.get('in_120th') != 'yes':
            continue
        state = person['state']
        if person['chamber_120'] == 'House':
            seat, end = house_seat_id(state, person['district_120'] or 0, 2026,
                                      new_map_states), CONGRESS_120[1]
        else:
            seat, end = (senate_seat_id(state, person['senate_class']),
                         SENATE_TERM_END[person['senate_class']])
        yield {'person_key': person['person_key'], 'seat_id': seat, 'congress': 120,
               'start_date': CONGRESS_120[0], 'end_date': end,
               'party': person.get('party_120'), 'source': ROSTER_120}


def seat_rows(terms, house_districts_2026, senate_classes):
    """Every seat a 119th or 120th term sits in, plus the 2026-map seats nobody holds yet."""
    seats = {}

    def add(seat_id, chamber, state, district=None, senate_class=None, map_year=None):
        seats.setdefault(seat_id, {
            'seat_id': seat_id, 'chamber': chamber, 'state': state,
            'district': district, 'senate_class': senate_class,
            'voting': state not in DELEGATE_STATES, 'map_first_election': map_year})

    for term in terms:
        kind, state, rest = term['seat_id'].split('-', 2)
        if kind == 'H':
            district, map_year = rest.split('/')
            add(term['seat_id'], 'House', state, int(district), map_year=int(map_year))
        else:
            add(term['seat_id'], 'Senate', state, senate_class=int(rest))
    for state, districts in house_districts_2026.items():
        for district, seat_id in districts.items():
            add(seat_id, 'House', state, district, map_year=int(seat_id.rsplit('/', 1)[1]))
    for state, classes in senate_classes.items():
        for senate_class in classes:
            add(senate_seat_id(state, senate_class), 'Senate', state, senate_class=senate_class)
    return list(seats.values())


def candidacy_rows(bulk_dir, cycles, new_map_states, senate_classes, seat_ids):
    """Every registered candidate. A seat link the seats table does not
    have (a filing error, such as MI-80) is left empty; the filed district stays."""
    for cycle in cycles:
        for c in candidates(bulk_dir, cycle):
            seat = seat_for(c, new_map_states, senate_classes)
            yield {'candidate_id': c.candidate_id, 'cycle': cycle, 'name': c.name,
                   'party': c.party, 'election_year': int(c.election_year or 0) or None,
                   'office': CANDIDATE_OFFICES.get(c.office, c.office),
                   'office_state': c.office_state, 'office_district': c.office_district,
                   'incumbent_challenger': c.incumbent_challenger, 'status': c.status,
                   'principal_committee': c.principal_committee,
                   'seat_id': seat if seat in seat_ids else None}


def seat_for(candidate, new_map_states, senate_classes):
    """The seat a 2024 or 2026 House/Senate candidacy is for, when the file says."""
    try:
        year = int(candidate.election_year)
    except ValueError:
        return None
    if year not in (2024, 2026):
        return None
    if candidate.office == 'H' and candidate.office_district.isdigit():
        # Delegates file under district 01 as well as 00.
        district = 0 if candidate.office_state in DELEGATE_STATES else candidate.office_district
        return house_seat_id(candidate.office_state, district, year, new_map_states)
    if candidate.office == 'S':
        regular = regular_senate_class(year)
        # A state without a seat in the regular class is holding a special
        # election, which the file cannot tell apart; leave it unlinked.
        if regular in senate_classes.get(candidate.office_state, ()):
            return senate_seat_id(candidate.office_state, regular)
    return None


def senate_classes_by_state(terms):
    classes = defaultdict(set)
    for term in terms:
        if term['seat_id'].startswith('S-'):
            _, state, senate_class = term['seat_id'].split('-')
            classes[state].add(int(senate_class))
    return {state: sorted(found) for state, found in classes.items()}

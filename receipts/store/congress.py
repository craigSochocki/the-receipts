"""Seats, terms and candidacies for the silver store."""

from collections import defaultdict

import yaml

from receipts.domain.seats import (
    DELEGATE_STATES,
    congress_elected_in,
    congress_start,
    house_seat_id,
    regular_senate_class,
    senate_seat_id,
    senate_term_end,
)
from receipts.fec.candidates import candidates

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


def served_in(term, congress):
    start, end = congress_start(congress), congress_start(congress + 1)
    return term['type'] in CONGRESS_TYPES and term['start'] < end and term['end'] > start


def terms_sitting(legislators, new_maps, election):
    """Terms of the Congress `election` seated, from the legislators files."""
    congress = congress_elected_in(election)
    for person in legislators:
        for term in person.get('terms', []):
            if not served_in(term, congress):
                continue
            state = term['state']
            if term['type'] == 'rep':
                seat = house_seat_id(state, term['district'], election, new_maps, election)
            else:
                seat = senate_seat_id(state, term['class'])
            yield {
                'person_key': person['id']['bioguide'],
                'seat_id': seat,
                'congress': congress,
                'start_date': term['start'],
                'end_date': term['end'],
                'party': term.get('party'),
                'source': LEGISLATORS,
            }


def terms_incoming(roster, new_maps, first_election, election):
    """Terms of the Congress `election` seats, from the roster."""
    congress = congress_elected_in(election)
    for person in roster:
        if person.get('in_120th') != 'yes':
            continue
        state = person['state']
        if person['chamber_120'] == 'House':
            seat, end = (
                house_seat_id(
                    state, person['district_120'] or 0, election, new_maps, first_election
                ),
                congress_start(congress + 1),
            )
        else:
            seat, end = (
                senate_seat_id(state, person['senate_class']),
                senate_term_end(person['senate_class'], election),
            )
        yield {
            'person_key': person['person_key'],
            'seat_id': seat,
            'congress': congress,
            'start_date': congress_start(congress),
            'end_date': end,
            'party': person.get('party_120'),
            'source': ROSTER_120,
        }


def seat_rows(terms, redrawn_districts, senate_classes):
    """Every seat a covered term sits in, plus the redrawn seats nobody holds yet."""
    seats = {}

    def add(seat_id, chamber, state, district=None, senate_class=None, map_year=None):
        seats.setdefault(
            seat_id,
            {
                'seat_id': seat_id,
                'chamber': chamber,
                'state': state,
                'district': district,
                'senate_class': senate_class,
                'voting': state not in DELEGATE_STATES,
                'map_first_election': map_year,
            },
        )

    for term in terms:
        kind, state, rest = term['seat_id'].split('-', 2)
        if kind == 'H':
            district, map_year = rest.split('/')
            add(term['seat_id'], 'House', state, int(district), map_year=int(map_year))
        else:
            add(term['seat_id'], 'Senate', state, senate_class=int(rest))
    for state, districts in redrawn_districts.items():
        for district, seat_id in districts.items():
            add(seat_id, 'House', state, district, map_year=int(seat_id.rsplit('/', 1)[1]))
    for state, classes in senate_classes.items():
        for senate_class in classes:
            add(senate_seat_id(state, senate_class), 'Senate', state, senate_class=senate_class)
    return list(seats.values())


def candidacy_rows(bulk_dir, cycles, new_maps, elections, senate_classes, seat_ids):
    """Every registered candidate; a seat the seats table lacks (a filing error) stays unlinked."""
    for cycle in cycles:
        for c in candidates(bulk_dir, cycle):
            seat = seat_for(c, new_maps, elections, senate_classes)
            yield {
                'candidate_id': c.candidate_id,
                'cycle': cycle,
                'name': c.name,
                'party': c.party,
                'election_year': int(c.election_year or 0) or None,
                'office': CANDIDATE_OFFICES.get(c.office, c.office),
                'office_state': c.office_state,
                'office_district': c.office_district,
                'incumbent_challenger': c.incumbent_challenger,
                'status': c.status,
                'principal_committee': c.principal_committee,
                'seat_id': seat if seat in seat_ids else None,
            }


def seat_for(candidate, new_maps, elections, senate_classes):
    """The seat a House/Senate candidacy in a covered election is for, when the file says."""
    try:
        year = int(candidate.election_year)
    except ValueError:
        return None
    if year not in elections:
        return None
    if candidate.office == 'H' and candidate.office_district.isdigit():
        # Delegates file under district 01 as well as 00.
        district = 0 if candidate.office_state in DELEGATE_STATES else candidate.office_district
        return house_seat_id(candidate.office_state, district, year, new_maps, elections[0])
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

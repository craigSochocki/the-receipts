"""Finding the candidate behind an expenditure filed with a blank candidate ID.

Two ways, tried in order by the IE scripts: a name index built from rows
that do carry an ID, then the roster, matched on name, state and district.
"""


def name_key(candidate_name, state, district, office):
    return candidate_name.upper(), state, district, office


def roster_matches(candidate_name, state, district, people):
    """Roster people whose last name, first-name start, state and district match."""
    last, first = _last_and_first(candidate_name)
    return [p for p in people
            if p['last_name'].upper() == last
            and (not first or p['first_name'].upper().startswith(first.split()[0]))
            and p['state'] == state
            and _represents(p, district)]


def _last_and_first(candidate_name):
    if ',' not in candidate_name:
        return candidate_name.strip().upper(), ''
    last, first = candidate_name.split(',')[:2]
    return last.strip().upper(), first.strip().upper()


def _represents(person, district):
    return any(str(person.get(seat) or '').zfill(2) == district
               for seat in ('district_119', 'district_120'))

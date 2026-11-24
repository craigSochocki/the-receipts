#!/usr/bin/env python3
"""FEC candidate-ID lookup for roster rows with no FEC ID yet.

Uses api.open.fec.gov with the API key from the FEC_API_KEY environment
variable (config fec_api.api_key_default as fallback). Matches on office +
state + district + party; stops on rate limiting and leaves the rest empty
rather than guessing.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from receipts.common.files import read_json, write_json
from receipts.common.settings import settings
from receipts.domain.names import norm

RATE_LIMITED = 429


def office_of(person):
    return 'S' if (person['chamber_120'] or person['chamber_119']) == 'Senate' else 'H'


def search_params(person, cycle):
    return {
        'name': f'{person["last_name"]}, {person["first_name"]}',
        'election_year': cycle,
        'office': office_of(person),
        'state': person['state'],
        'per_page': 20,
    }


def wanted_district(person):
    if office_of(person) != 'H':
        return None
    district = person['district_120'] or person['district_119']
    return int(district) if district not in ('', None) else None


def matching_candidates(person, candidates, cycle, party_codes):
    """The API's candidates that run for this person's seat, party and cycle."""
    office, district = office_of(person), wanted_district(person)
    party = party_codes.get(person['party_120'] or person['party_119'])
    return [
        c
        for c in candidates
        if c.get('state') == person['state']
        and c.get('office') == office
        and not (
            district is not None
            and c.get('district_number') is not None
            and int(c['district_number']) != district
        )
        and not (party and c.get('party') and c['party'] != party)
        and cycle in (c.get('election_years') or [])
    ]


def choose(person, matching, candidates):
    """(status, value): one match is found; several are settled by first name, or ambiguous."""
    if len(matching) == 1:
        return 'found', matching[0]['candidate_id']
    if matching:
        first = norm(person['first_name']).split()
        for c in matching:
            if first and first[0] in norm(c.get('name', '')):
                return 'found', c['candidate_id']
        return 'ambiguous', [c['candidate_id'] for c in matching]
    return 'not_found', [c.get('candidate_id') for c in candidates]


def search(params):
    """The API's candidates for these parameters, or (error status, detail)."""
    api = settings().fec_api
    key = os.environ.get(api.api_key_env, api.api_key_default)
    url = api.base_url + '?' + urllib.parse.urlencode({'api_key': key, **params})
    try:
        with urllib.request.urlopen(url, timeout=api.request_timeout_seconds) as resp:
            return json.load(resp).get('results', []), None
    except urllib.error.HTTPError as e:
        return None, ('http_error', e.code)
    except Exception as e:
        return None, ('error', str(e))


def lookup(person, cycle, party_codes, search=search):
    candidates, failure = search(search_params(person, cycle))
    if failure:
        return failure
    return choose(person, matching_candidates(person, candidates, cycle, party_codes), candidates)


def look_up_missing(rows, cycle, party_codes, search=search, pause=time.sleep):
    """{person_key: result} for every row without an FEC ID, setting found IDs on the rows."""
    missing = [r for r in rows if not r['fec_candidate_ids']]
    print('rows missing FEC IDs:', len(missing))
    results = {}
    for i, person in enumerate(missing):
        status, value = lookup(person, cycle, party_codes, search)
        results[person['person_key']] = {
            'name': person['full_name'],
            'state': person['state'],
            'status': status,
            'value': value,
        }
        if status == 'found':
            person['fec_candidate_ids'] = [value]
            person['_fec_source'] = f'fec-api-{cycle}'
        print(f'{i + 1}/{len(missing)} {person["full_name"]} ({person["state"]}): {status} {value}')
        if status == 'http_error' and value == RATE_LIMITED:
            print('RATE LIMITED — stopping')
            break
        pause(settings().fec_api.sleep_between_requests_seconds)
    return results


def main():
    """Look up missing FEC candidate IDs through the OpenFEC API."""
    paths = settings().paths
    rows = read_json(paths.roster_intermediate)
    results = look_up_missing(rows, settings().cycles.current, settings().party_codes)
    write_json(paths.fec_lookup_results, results)
    write_json(paths.roster_intermediate, rows)
    found = sum(1 for v in results.values() if v['status'] == 'found')
    print(f'found {found} of {len(results)} attempted')


if __name__ == '__main__':
    main()

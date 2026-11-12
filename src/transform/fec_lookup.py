#!/usr/bin/env python3
"""FEC candidate-ID lookup for roster rows with no FEC ID yet.
Uses api.open.fec.gov with the API key from the FEC_API_KEY environment
variable (config fec_api.api_key_default as fallback). Matches on
office + state + district + party; stops on rate limiting and leaves the
rest empty rather than guessing."""
import json, time, urllib.request, urllib.parse, unicodedata, re, os

from config import load_config

CFG = load_config()
ROOT = CFG['_root']
WORK = str(ROOT / CFG['paths']['work'])
API = CFG['fec_api']['base_url']
API_KEY = os.environ.get(CFG['fec_api']['api_key_env'], CFG['fec_api']['api_key_default'])
CURRENT_ELECTION_YEAR = CFG['cycles']['current']
PARTY = CFG['party_codes']

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z ]', '', s.lower()).strip()

rows = json.load(open(f'{WORK}/roster_intermediate.json'))
missing = [r for r in rows if not r['fec_candidate_ids']]
print('rows missing FEC IDs:', len(missing))

results = {}

def lookup(r):
    chamber = r['chamber_120'] or r['chamber_119']
    office = 'S' if chamber == 'Senate' else 'H'
    name_q = f"{r['last_name']}, {r['first_name']}"
    params = {'api_key': API_KEY, 'name': name_q, 'election_year': CURRENT_ELECTION_YEAR,
              'office': office, 'state': r['state'], 'per_page': 20}
    url = API + '?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=CFG['fec_api']['request_timeout_seconds']) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        return ('http_error', e.code)
    except Exception as e:
        return ('error', str(e))
    cands = data.get('results', [])
    # filter: state + office already filtered by API; check district + party
    want_dist = None
    if office == 'H':
        d = r['district_120'] or r['district_119']
        want_dist = int(d) if d not in ('', None) else None
    want_party = PARTY.get(r['party_120'] or r['party_119'])
    scored = []
    for c in cands:
        if c.get('state') != r['state']:
            continue
        if c.get('office') != office:
            continue
        if want_dist is not None and c.get('district_number') is not None \
                and int(c['district_number']) != want_dist:
            continue
        if want_party and c.get('party') and c['party'] != want_party:
            continue
        if CURRENT_ELECTION_YEAR not in (c.get('election_years') or []):
            continue
        scored.append(c)
    if len(scored) == 1:
        return ('found', scored[0]['candidate_id'])
    if len(scored) > 1:
        # prefer the one whose name matches best (first-name token present)
        ft = norm(r['first_name']).split()
        for c in scored:
            nm = norm(c.get('name', ''))
            if ft and ft[0] in nm:
                return ('found', c['candidate_id'])
        return ('ambiguous', [c['candidate_id'] for c in scored])
    return ('not_found', [c.get('candidate_id') for c in cands])

for i, r in enumerate(missing):
    status, val = lookup(r)
    results[r['person_key']] = {'name': r['full_name'], 'state': r['state'],
                                'status': status, 'value': val}
    if status == 'found':
        r['fec_candidate_ids'] = [val]
        r['_fec_source'] = f'fec-api-{CURRENT_ELECTION_YEAR}'
    print(f"{i+1}/{len(missing)} {r['full_name']} ({r['state']}): {status} {val}")
    if status == 'http_error' and val == 429:
        print('RATE LIMITED — stopping')
        break
    time.sleep(CFG['fec_api']['sleep_between_requests_seconds'])

json.dump(results, open(f'{WORK}/fec_lookup_results.json', 'w'), indent=1)
json.dump(rows, open(f'{WORK}/roster_intermediate.json', 'w'), indent=1)
found = sum(1 for v in results.values() if v['status'] == 'found')
print(f"found {found} of {len(results)} attempted")

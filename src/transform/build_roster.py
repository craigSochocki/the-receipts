#!/usr/bin/env python3
"""Build union roster 119th + 120th Congress.
Sources:
 - 119th: unitedstates/congress-legislators legislators-current.yaml (fetched 2026-11-12)
 - 120th: Wikipedia '120th United States Congress' (crawled 2026-11-12 11:26 UTC),
   transcribed to 120th_roster.json; new-members page cross-checked.
 - Returning former members: legislators-historical.yaml via historical_lookup.json
"""
import json, re, unicodedata, csv, collections
import yaml

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
SRC = str(ROOT / CFG['paths']['source'])
IM = str(ROOT / CFG['paths']['intermediate'])

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z ]', '', s.lower()).strip()

NICK = {'bob': 'robert', 'mike': 'michael', 'jim': 'james', 'dan': 'daniel',
        'dave': 'david', 'joe': 'joseph', 'tom': 'thomas', 'bill': 'william',
        'chuck': 'charles', 'hank': 'henry', 'jerry': 'gerald', 'rick': 'richard',
        'steve': 'steven', 'chris': 'christopher', 'andy': 'andrew', 'matt': 'matthew',
        'sam': 'samuel', 'ben': 'benjamin', 'alex': 'alexander', 'nick': 'nicholas',
        'rob': 'robert', 'ron': 'ronald', 'don': 'donald', 'ray': 'raymond',
        'fred': 'frederick', 'greg': 'gregory', 'jeff': 'jeffrey', 'jon': 'john',
        'johnny': 'john', 'josh': 'joshua', 'zach': 'zachary', 'zack': 'zachary',
        'jake': 'jacob', 'kat': 'katherine', 'kate': 'katherine',
        'kathy': 'katherine', 'lizzie': 'elizabeth', 'liz': 'elizabeth',
        'beth': 'elizabeth', 'susan': 'susan', 'sue': 'susan',
        'debbie': 'deborah', 'deb': 'deborah',
        'terri': 'teresa', 'maggie': 'margaret', 'peggy': 'margaret',
        'tony': 'anthony', 'tim': 'timothy', 'ed': 'edward',
        'pat': 'patrick', 'randy': 'randall', 'doug': 'douglas',
        'val': 'valerie', 'ted': 'theodore', 'pete': 'peter', 'dick': 'richard',
        'jen': 'jennifer', 'jess': 'jessica', 'will': 'william', 'gabe': 'gabriel',
        'don': 'donald', 'ron': 'ronald', 'al': 'alan', 'herb': 'herbert',
        'lou': 'luis', 'gil': 'gilbert', 'jack': 'john', 'bernie': 'bernard'}

# Multiword last names: display name -> (first, last)
MULTI_LAST = {
    'Lisa Blunt Rochester': ('Lisa', 'Blunt Rochester'),
    'Chris Van Hollen': ('Chris', 'Van Hollen'),
    'Catherine Cortez Masto': ('Catherine', 'Cortez Masto'),
    'Debbie Wasserman Schultz': ('Debbie', 'Wasserman Schultz'),
    'Marie Gluesenkamp Perez': ('Marie', 'Gluesenkamp Perez'),
    'Beth Van Duyne': ('Beth', 'Van Duyne'),
    'Teresa Leger Fernandez': ('Teresa', 'Leger Fernandez'),
    'April McClain Delaney': ('April', 'McClain Delaney'),
    'Matt Van Epps': ('Matt', 'Van Epps'),
    'Darline Graham Nordone': ('Darline', 'Graham Nordone'),
}

def first_norm(first):
    f = norm(first).split()
    if not f:
        return ''
    return NICK.get(f[0], f[0])

def split_name(full):
    """Return (first, last) for a display name; handles suffixes and known multiword names."""
    multi_first = {'La Shawn Ford': ('La Shawn', 'Ford'),
                   'Mary Gay Scanlon': ('Mary Gay', 'Scanlon'),
                   'Luz Maria Rivas': ('Luz Maria', 'Rivas'),
                   'J.D. Ford': ('J.D.', 'Ford'),
                   'Darializa Avila Chevalier': ('Darializa', 'Avila Chevalier'),
                   'Katy Padilla Stout': ('Katy', 'Padilla Stout'),
                   'Jessica Hart Steinmann': ('Jessica', 'Steinmann'),
                   'Pablo Hernández Rivera': ('Pablo José', 'Hernández Rivera'),
                   'Amata Coleman Radewagen': ('Amata Coleman', 'Radewagen')}
    if full in MULTI_LAST:
        return MULTI_LAST[full]
    if full in multi_first:
        return multi_first[full]
    s = full.strip()
    for suf in (' Jr.', ' Sr.', ' III', ' II', ' IV'):
        if s.endswith(suf):
            s = s[:-len(suf)]
            break
    parts = s.split()
    if len(parts) == 1:
        return parts[0], ''
    return ' '.join(parts[:-1]), parts[-1]

def slug(first, last, state, extra=''):
    base = norm(f"{first}-{last}-{state}-{extra}")
    return re.sub(r'[^a-z0-9]+', '-', base).strip('-')

# ---------- 119th base ----------
cur = yaml.safe_load(open(f'{SRC}/legislators-current.yaml'))
rows = {}  # bioguide -> row dict
for p in cur:
    bg = p['id'].get('bioguide')
    t = p['terms'][-1]
    n = p['name']
    full = n.get('official_full') or f"{n.get('first','')} {n.get('last','')}".strip()
    rows[bg] = {
        'person_key': bg, 'full_name': full,
        'first_name': n.get('first', ''), 'last_name': n.get('last', ''),
        'chamber_119': 'House' if t['type'] == 'rep' else 'Senate',
        'chamber_120': '', 'state': t.get('state', ''),
        'district_119': '' if t['type'] == 'sen' else str(t.get('district', '')),
        'district_120': '', 'party_119': t.get('party', ''),
        'party_120': '', 'leadership_119': '', 'leadership_120': 'TBD',
        'fec_candidate_ids': list(p['id'].get('fec') or []),
        'in_119th': 'yes', 'in_120th': 'no', 'notes': '',
        '_bioguide': bg, '_fec_source': 'repo-current',
        '_nickname': n.get('nickname', ''), '_official': full,
    }

# index base by (state, norm last name)
by_state_last = collections.defaultdict(list)
for bg, r in rows.items():
    by_state_last[(r['state'], norm(r['last_name']))].append(r)

hist = json.load(open(f'{SRC}/historical_lookup.json'))

def first_agrees(entry_first, row):
    """Nickname-aware first-name agreement, using the repo's nickname and
    official_full fields (e.g. Bernie/Bernard, Jack/John, Rick/Eric,
    Andy/Garland, French/J. French Hill, Lou/Luis Correa)."""
    etoks = [NICK.get(t, t) for t in norm(entry_first).split()]
    btoks = set()
    for src in (row['first_name'], row.get('_nickname', ''), row.get('_official', '')):
        for t in norm(src).split():
            btoks.add(NICK.get(t, t))
            btoks.add(t)
    return any(t in btoks for t in etoks)

def match_base(entry_name, state):
    """Match a 120th entry to a 119th base row by state + last name (+ first name)."""
    first, last = split_name(entry_name)
    cands = by_state_last.get((state, norm(last)), [])
    if len(cands) == 1:
        # require first-name agreement (nickname-aware) to avoid same-state
        # same-last-name collisions (e.g. Johnny Garcia vs Sylvia Garcia,
        # Trever Nehls vs Troy Nehls, Stefany Shaheen vs Jeanne Shaheen)
        if not first_agrees(first, cands[0]):
            return None
        return cands[0]
    if len(cands) > 1:
        for c in cands:
            if first_agrees(first, c):
                return c
        return None  # ambiguous
    return None

def match_hist(entry_name, state):
    first, last = split_name(entry_name)
    for key in (norm(f"{first} {last}"), norm(entry_name)):
        if key in hist:
            h = hist[key]
            lt = h.get('last_term') or {}
            # guard against namesakes from long ago: require recent service
            # in the same state (admits Bean 2011, Solis 2009; excludes 1800s namesakes)
            if lt.get('state') == state and (lt.get('end') or '') >= '2000':
                return h
    return None

# ---------- 120th roster ----------
r120 = json.load(open(f'{SRC}/120th_roster.json'))
entries = []
for s in r120['senate']:
    entries.append({'name': s['name'], 'state': s['state'], 'district': None,
                    'party': s['party'], 'chamber': 'Senate'})
for h in r120['house']:
    entries.append({'name': h['name'], 'state': h['state'], 'district': h['district'],
                    'party': h['party'], 'chamber': 'House'})
for d in r120['delegates']:
    entries.append({'name': d['name'], 'state': d['state'], 'district': d['district'],
                    'party': d['party'], 'chamber': 'House'})

unmatched_120 = []
new_persons = []
for e in entries:
    r = match_base(e['name'], e['state'])
    if r is not None:
        r['chamber_120'] = e['chamber']
        r['district_120'] = '' if e['chamber'] == 'Senate' else str(e['district'])
        r['party_120'] = 'Democrat' if e['party'] == 'DFL' else e['party']
        r['in_120th'] = 'yes'
        if e['party'] == 'DFL':
            r['notes'] = (r['notes'] + '; ' if r['notes'] else '') + 'Party listed as DFL (Minnesota Democratic-Farmer-Labor, Democratic affiliate).'
        if e['party'] == 'PPD':
            r['notes'] = (r['notes'] + '; ' if r['notes'] else '') + 'Resident Commissioner; party PPD (caucuses with Democrats).'
        continue
    # returning former member?
    h = match_hist(e['name'], e['state'])
    if h is not None:
        first, last = split_name(e['name'])
        key = h['bioguide'] or slug(first, last, e['state'], e['chamber'])
        nr = {'person_key': key, 'full_name': e['name'], 'first_name': first,
              'last_name': last, 'chamber_119': '', 'chamber_120': e['chamber'],
              'state': e['state'], 'district_119': '',
              'district_120': '' if e['chamber'] == 'Senate' else str(e['district']),
              'party_119': '', 'party_120': 'Democrat' if e['party'] == 'DFL' else e['party'],
              'leadership_119': '', 'leadership_120': 'TBD',
              'fec_candidate_ids': list(h.get('fec') or []),
              'in_119th': 'no', 'in_120th': 'yes',
              'notes': f"Returning former member; last served {h['last_term'].get('type')} {h['last_term'].get('state')} ending {h['last_term'].get('end')} (prior service, not 119th).",
              '_bioguide': h.get('bioguide'), '_fec_source': 'repo-historical'}
        rows[key] = nr
        new_persons.append(('returning', e['name'], e['state']))
        continue
    first, last = split_name(e['name'])
    key = slug(first, last, e['state'], e['chamber'])
    nr = {'person_key': key, 'full_name': e['name'], 'first_name': first,
          'last_name': last, 'chamber_119': '', 'chamber_120': e['chamber'],
          'state': e['state'], 'district_119': '',
          'district_120': '' if e['chamber'] == 'Senate' else str(e['district']),
          'party_119': '', 'party_120': 'Democrat' if e['party'] == 'DFL' else e['party'],
          'leadership_119': '', 'leadership_120': 'TBD',
          'fec_candidate_ids': [], 'in_119th': 'no', 'in_120th': 'yes',
          'notes': 'New member of the 120th Congress (first term in Congress).',
          '_bioguide': None, '_fec_source': 'none-fec-api-pending'}
    rows[key] = nr
    new_persons.append(('brand-new', e['name'], e['state']))
    unmatched_120.append(e)

# ---------- special cases ----------
def add_note(key, txt):
    r = rows[key]
    r['notes'] = (r['notes'] + '; ' if r['notes'] else '') + txt

# Sherrod Brown: not in current file (term ended Jan 2025); won OH special Nov 3, 2026;
# takes Senate seat Dec 15, 2026 (still 119th) and serves in 120th.
hb = hist[norm('Sherrod Brown')]
rows['B000944'] = {'person_key': 'B000944', 'full_name': 'Sherrod Brown',
    'first_name': 'Sherrod', 'last_name': 'Brown', 'chamber_119': 'Senate',
    'chamber_120': 'Senate', 'state': 'OH', 'district_119': '', 'district_120': '',
    'party_119': 'Democrat', 'party_120': 'Democrat', 'leadership_119': '',
    'leadership_120': 'TBD', 'fec_candidate_ids': list(hb.get('fec') or []),
    'in_119th': 'yes', 'in_120th': 'yes',
    'notes': 'Won OH Senate special election Nov 3, 2026 (defeated appointed incumbent Jon Husted); takes seat Dec 15, 2026, so serves in both the 119th (from Dec 15) and 120th; term runs to Jan 2029.',
    '_bioguide': 'B000944', '_fec_source': 'repo-historical'}

# Kevin Hern: House OK-1 in 119th; elected Senator, sworn in Nov 30, 2026.
add_note('H001082', 'Elected to Senate Nov 3, 2026; sworn in Nov 30, 2026 to fill remainder of 119th term (succeeding appointed Sen. Alan Armstrong) and full 120th term. House OK-1 successor Mark Tedford takes that seat in the 120th.')
# Alan Armstrong: appointed senator, out Nov 30, 2026.
add_note('A000383', 'Appointed senator Mar 24, 2026 (after Markwayne Mullin resigned to become Homeland Security Secretary); term ends Nov 30, 2026 when Kevin Hern is sworn in; not in 120th.')
# Jon Husted: serves until Dec 15, 2026.
add_note('H001104', 'Appointed senator Jan 21, 2025; lost OH special election Nov 3, 2026 to Sherrod Brown; serves until Dec 15, 2026; not in 120th.')
# Ashley Moody: re-elected in FL special.
add_note('M001244', 'Appointed senator Jan 21, 2025; re-elected in FL special election Nov 3, 2026; serves in both 119th and 120th.')
# Darline Graham: appointed after Lindsey Graham died; lost Nov 3.
add_note('G000608', 'Appointed senator Jul 14, 2026 after Sen. Lindsey Graham died Jul 11, 2026; lost Nov 3, 2026 election to Annie Andrews; not in 120th.')
# Klobuchar / Blackburn: elected governor, resign Jan 2027.
for k, r in rows.items():
    if r['last_name'] == 'Blackburn' and r['state'] == 'TN':
        add_note(k, 'Elected Tennessee governor Nov 3, 2026; plans to resign from Senate Jan 2027; successor to be appointed until a special election in Nov 2028 (per Wikipedia 120th Congress). Counted in 120th as seated at its start.')
    if r['last_name'] == 'Klobuchar':
        add_note(k, 'Elected Minnesota governor Nov 3, 2026; plans to resign from Senate Jan 2027; successor to be appointed until a special election in Nov 2027 (per Wikipedia 120th Congress). Counted in 120th as seated at its start.')

# 120th membership unknown (uncalled / runoff): mark in_120th='unknown' for incumbents.
unknown_seats = {('AK', 'Senate'): 'Dan Sullivan (R) — AK Senate race uncalled as of Nov 12, 2026.',
                 ('AK', 'House'): 'Nick Begich III (R) — AK at-large House race uncalled as of Nov 12, 2026.',
                 ('CA', 'House', '4'): 'Mike Thompson (D) — CA-04 listed TBD (D) on Wikipedia 120th page, Nov 12, 2026.',
                 ('CA', 'House', '23'): 'Jay Obernolte (R) — CA-23 listed TBD on Wikipedia 120th page, Nov 12, 2026.',
                 ('LA', 'House', '6'): 'Cleo Fields (D) — LA-06 runoff Dec 12, 2026; winner TBD.'}
for k, r in rows.items():
    if r['in_119th'] != 'yes':
        continue
    key = None
    if r['chamber_119'] == 'Senate' and r['state'] == 'AK' and r['last_name'] == 'Sullivan':
        key = ('AK', 'Senate')
    elif r['chamber_119'] == 'House' and r['state'] == 'AK':
        key = ('AK', 'House')
    elif r['chamber_119'] == 'House' and r['state'] == 'CA' and r['district_119'] == '4':
        key = ('CA', 'House', '4')
    elif r['chamber_119'] == 'House' and r['state'] == 'CA' and r['district_119'] == '23':
        key = ('CA', 'House', '23')
    elif r['chamber_119'] == 'House' and r['state'] == 'LA' and r['district_119'] == '6':
        key = ('LA', 'House', '6')
    if key:
        r['in_120th'] = 'unknown'
        add_note(k, '120th membership UNKNOWN: ' + unknown_seats[key])

# Jasmine Clark (GA-13): new-members page note says elected in special election to
# replace David Scott; whether seated before Jan 3, 2027 is unverified.
for k, r in rows.items():
    if r['last_name'] == 'Clark' and r['first_name'] == 'Jasmine' and r['state'] == 'GA':
        add_note(k, 'Wikipedia new-members note says elected in a special election to replace David Scott (d. Apr 22, 2026); whether she is seated before Jan 3, 2027 is UNVERIFIED — counted as 120th-only pending confirmation.')

# ---------- leadership 119th (verified) ----------
LEAD119 = {
    ('Mike Johnson', 'House'): 'Speaker of the House',
    ('Steve Scalise', 'House'): 'Majority Leader',
    ('Tom Emmer', 'House'): 'Majority Whip',
    ('Lisa McClain', 'House'): 'Chair, House Republican Conference',
    ('Kevin Hern', 'House'): 'Chair, House Republican Policy Committee',
    ('Blake Moore', 'House'): 'Vice Chair, House Republican Conference',
    ('Hakeem Jeffries', 'House'): 'Minority Leader',
    ('Katherine Clark', 'House'): 'Minority Whip',
    ('Pete Aguilar', 'House'): 'Chair, House Democratic Caucus',
    ('Ted Lieu', 'House'): 'Vice Chair, House Democratic Caucus',
    ('John Thune', 'Senate'): 'Majority Leader',
    ('John Barrasso', 'Senate'): 'Majority Whip',
    ('Tom Cotton', 'Senate'): 'Chair, Senate Republican Conference',
    ('Chuck Grassley', 'Senate'): 'President pro tempore',
    ('Chuck Schumer', 'Senate'): 'Minority Leader; Chair, Senate Democratic Caucus',
    ('Dick Durbin', 'Senate'): 'Minority Whip',
    ('Amy Klobuchar', 'Senate'): 'Chair, Senate Democratic Steering and Policy Committee',
}
for k, r in rows.items():
    if r['in_119th'] != 'yes':
        continue
    for (lname, chamber), role in LEAD119.items():
        if chamber != r['chamber_119']:
            continue
        first, last = split_name(lname)
        if norm(last) == norm(r['last_name']) and first_agrees(first, r):
            r['leadership_119'] = role

# ---------- leadership 120th: TBD per brief; Wikipedia-listed names kept in notes ----------
LEAD120_WIKI = {
    'John Thune': 'Senate Minority Leader',
    'John Barrasso': 'Senate Minority Whip',
    'Tom Cotton': 'Chair, Senate Republican Conference',
    'Bernie Moreno': 'Chair, National Republican Senatorial Committee',
    'Jim Jordan': 'House Minority Leader',
    'Tom Emmer': 'House Minority Whip',
    'Lisa McClain': 'Chair, House Republican Conference',
    'Brian Jack': 'Chair, National Republican Congressional Committee',
}
for k, r in rows.items():
    if r['full_name'] in LEAD120_WIKI and r['in_120th'] == 'yes':
        add_note(k, f"UNVERIFIED 120th leadership: Wikipedia 120th Congress page (Nov 12, 2026) lists as {LEAD120_WIKI[r['full_name']]}; leadership elections are Nov 18-19, 2026, so role is TBD pending confirmation.")

# ---------- outgoing notes: 120th holder of the same seat ----------
# House: same state+district number in 120th roster; Senate: other senator(s) of same state new in 120th
h120_by_seat = {(h['state'], str(h['district'])): h for h in r120['house']}
s120_by_state = collections.defaultdict(list)
for s in r120['senate']:
    s120_by_state[s['state']].append(s['name'])
for k, r in rows.items():
    if r['in_119th'] == 'yes' and r['in_120th'] == 'no':
        if r['chamber_119'] == 'House' and (r['state'], r['district_119']) in h120_by_seat:
            h = h120_by_seat[(r['state'], r['district_119'])]
            add_note(k, f"Not in 120th; {r['state']}-{r['district_119']} in the 120th is held by {h['name']} ({h['party']}).")
        elif r['chamber_119'] == 'Senate':
            new_sens = [n for n in s120_by_state[r['state']]
                        if not any(rr['full_name'] == n and rr['in_119th'] == 'yes' for rr in rows.values())]
            if new_sens:
                add_note(k, f"Not in 120th; new senator(s) from {r['state']} in the 120th: {', '.join(new_sens)}.")

# ---------- senate_class ----------
# Senate class (1/2/3) for every senator row, from the legislators yaml:
# each Senate term carries its class directly. A person holding a Senate
# seat into 2026 takes their own latest term's class; a new senator (no
# Senate term of their own) takes the class of whoever held that seat
# during 2026 — the appointee or outgoing holder, whose term carries the
# seat's class. Render-time derivation from FEC cycles was tested and
# fails (every senator fundraises every cycle; special-election winners
# break the cycle-mod-6 pattern), so it is computed here, not on the page.
_sen_terms = {}
for _p in cur:
    _sen_terms[_p['id'].get('bioguide')] = [
        t for t in _p['terms'] if t.get('type') == 'sen']
_cont_sen = {r['person_key'] for r in rows.values()
             if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate'}
def _senate_class(r):
    if r['chamber_119'] != 'Senate' and r['chamber_120'] != 'Senate':
        return None
    own = [t for t in _sen_terms.get(r.get('_bioguide') or r['person_key'], [])
           if (t.get('end') or '') >= '2026-01-01']
    if own:
        return own[-1].get('class')
    holders = set()
    for _p in cur:
        for t in _p['terms']:
            if (t.get('type') == 'sen' and t.get('state') == r['state']
                    and (t.get('start') or '') <= '2026-12-31'
                    and (t.get('end') or '') >= '2026-01-01'
                    and _p['id'].get('bioguide') not in _cont_sen):
                holders.add(t.get('class'))
    return holders.pop() if len(holders) == 1 else None
for r in rows.values():
    r['senate_class'] = _senate_class(r)

json.dump(list(rows.values()), open(f'{IM}/roster_intermediate.json', 'w'), indent=1)
print('total rows:', len(rows))
print('in 119th:', sum(1 for r in rows.values() if r['in_119th'] == 'yes'))
print('in 120th:', sum(1 for r in rows.values() if r['in_120th'] == 'yes'))
print('in 120th unknown:', sum(1 for r in rows.values() if r['in_120th'] == 'unknown'))
print('in both:', sum(1 for r in rows.values() if r['in_119th'] == 'yes' and r['in_120th'] == 'yes'))
print('119th only:', sum(1 for r in rows.values() if r['in_119th'] == 'yes' and r['in_120th'] == 'no'))
print('120th only:', sum(1 for r in rows.values() if r['in_119th'] == 'no' and r['in_120th'] == 'yes'))
print('new persons (returning/brand-new):', collections.Counter(x[0] for x in new_persons))
print('brand-new list:')
for kind, name, st in new_persons:
    if kind == 'brand-new':
        print('  ', name, st)
print('returning list:')
for kind, name, st in new_persons:
    if kind == 'returning':
        print('  ', name, st)
print('120th entries matched to base:', sum(1 for r in rows.values() if r['in_120th'] == 'yes' and r['in_119th'] == 'yes'))
# sanity: any 120th-named person missing?
print('rows with in_120th=yes but no chamber_120:', [r['full_name'] for r in rows.values() if r['in_120th'] == 'yes' and not r['chamber_120']])
print('rows with in_119th=yes but no chamber_119:', [r['full_name'] for r in rows.values() if r['in_119th'] == 'yes' and not r['chamber_119']])
print('UNKNOWN rows:', [(r['full_name'], r['state'], r['chamber_119'], r['district_119']) for r in rows.values() if r['in_120th'] == 'unknown'])
# verify every 120th entry is represented by exactly one row
# (nickname-aware: a row matches an entry when state+chamber+last agree and
# first_agrees holds against the row's first/nickname/official_full)
missing, dup = [], []
for e in entries:
    first, last = split_name(e['name'])
    hits = [r for r in rows.values()
            if r['in_120th'] == 'yes' and r['state'] == e['state']
            and r['chamber_120'] == e['chamber'] and norm(r['last_name']) == norm(last)
            and first_agrees(first, r)]
    if not hits:
        missing.append(e)
    elif len(hits) > 1:
        dup.append((e, [h['full_name'] for h in hits]))
print('120th entries with NO row:', missing)
print('120th entries with >1 row:', dup)

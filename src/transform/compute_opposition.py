#!/usr/bin/env python3
"""
Opposition-credit computation for the Congress money tracker.

Rule (conservative, per task): for each committee and race phase (FEC cycle +
office + state + district + election phase), determine the committee's backed
candidate(s) from its own IE SUPPORT rows in that phase. If it backed EXACTLY
ONE candidate, credit all of that committee's IE spending OPPOSING other
candidates in the same phase to that one backed candidate. If it backed zero
or two or more, credit NOTHING for that phase.

The phase is the filing's `ele_type` (P primary, G general, O other), already
parsed on every row. Expenditure dates cannot be used instead: the date is
blank on 100% of UDP rows in all three cycles. Each ele_type code is its own
phase, O included — no special-casing. Backing different candidates in the
primary and the general therefore credits each phase's opposition spending to
that phase's backed candidate (MI-Sen 2026: Stevens in the primary, Rogers in
the general).

Sources: staged bulk IE files data/raw/ie/<cycle>/independent_expenditure_<cycle>.csv
(cycles from config cycles.udp). Dedup by tran_id, keep latest receipt_dat, tie-break
highest file_num (same rule as the UDP support pull). AIPAC PAC (see config
committees.aipac_pac) has ZERO Schedule E rows in all three cycles, so no AIPAC
opposition column is built.
"""
import csv, json, collections
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
IE_DIR = str(ROOT / CFG['paths']['ie'])
UDP = CFG['committees']['udp']
AIPAC = CFG['committees']['aipac_pac']
CYCLES = tuple(CFG['cycles']['udp'])

def parse_amt(s):
    return float(str(s).replace('$', '').replace(',', '').strip() or 0)

def parse_date(s):
    s = (s or '').strip()
    if not s:
        return datetime.min
    try:
        return datetime.strptime(s, '%d-%b-%y')
    except ValueError:
        return datetime.min

def parse_filenum(s):
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return 0

# ---------- 1. Load + dedup per cycle ----------
all_rows = []          # deduped rows, all cycles
dedup_stats = {}
for yr in CYCLES:
    path = f'{IE_DIR}/{yr}/independent_expenditure_{yr}.csv'
    best = {}          # tran_id -> row (kept copy)
    n_raw = n_udp = 0
    with open(path, newline='') as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r):
            if row['spe_id'] not in (UDP, AIPAC):
                continue
            n_raw += 1
            tid = (row.get('tran_id') or '').strip()
            key = tid if tid else f'__blank__{yr}_{i}'
            cand = {
                'cycle': int(row['fec_election_yr']),
                'cand_id': (row['cand_id'] or '').strip(),
                'cand_name': (row['cand_name'] or '').strip(),
                'spe_id': row['spe_id'],
                'sup_opp': (row['sup_opp'] or '').strip(),
                'office': (row['can_office'] or '').strip(),
                'state': (row['can_office_state'] or '').strip(),
                'district': (row['can_office_dis'] or '').strip(),
                'ele_type': (row['ele_type'] or '').strip(),
                'amount': parse_amt(row['exp_amo']),
                'receipt_dat': row.get('receipt_dat', ''),
                'file_num': parse_filenum(row.get('file_num')),
                'tran_id': tid,
            }
            if key not in best:
                best[key] = cand
            else:
                prev = best[key]
                if (parse_date(cand['receipt_dat']), cand['file_num']) > (parse_date(prev['receipt_dat']), prev['file_num']):
                    best[key] = cand
    dedup_stats[yr] = (n_raw, len(best))
    all_rows.extend(best.values())
    print(f'{yr}: {n_raw} committee rows raw -> {len(best)} deduped')

udp_rows = [r for r in all_rows if r['spe_id'] == UDP]
aipac_rows = [r for r in all_rows if r['spe_id'] == AIPAC]
print(f'UDP deduped rows: {len(udp_rows)} (S={sum(1 for r in udp_rows if r["sup_opp"]=="S")}, '
      f'O={sum(1 for r in udp_rows if r["sup_opp"]=="O")})')
print(f'AIPAC PAC deduped Schedule E rows: {len(aipac_rows)}')

# ---------- 2. Resolve blank cand_id via name index ----------
# index: (NAME upper, state, district, office) -> cand_id, from deduped non-blank rows
name_index = {}
collisions = []
for r in udp_rows:
    if r['cand_id']:
        key = (r['cand_name'].upper(), r['state'], r['district'], r['office'])
        if key in name_index and name_index[key] != r['cand_id']:
            collisions.append((key, name_index[key], r['cand_id']))
        name_index[key] = r['cand_id']

# roster fallback: (LAST, FIRST, state, district, office) -> fec id(s)
roster = json.load(open(ROOT / CFG['paths']['roster']))
id_to_person = {}
for p in roster:
    for cid in (p.get('fec_candidate_ids') or []):
        id_to_person.setdefault(cid, p['person_key'])

unresolved = []
resolved = 0
for r in udp_rows:
    if not r['cand_id']:
        key = (r['cand_name'].upper(), r['state'], r['district'], r['office'])
        cid = name_index.get(key)
        if cid:
            r['cand_id'] = cid
            r['resolved_via'] = 'name_index'
            resolved += 1
        else:
            # roster fallback on last/first name
            nm = r['cand_name']
            last = nm.split(',')[0].strip().upper() if ',' in nm else nm.strip().upper()
            first = nm.split(',')[1].strip().upper() if ',' in nm and len(nm.split(',')) > 1 else ''
            cands = [p for p in roster if p['last_name'].upper() == last
                     and (not first or p['first_name'].upper().startswith(first.split()[0]))
                     and p['state'] == r['state']
                     and (str(p.get('district_119') or '').zfill(2) == r['district'] or str(p.get('district_120') or '').zfill(2) == r['district'])]
            if len(cands) == 1 and len(cands[0].get('fec_candidate_ids') or []) >= 1:
                # pick the ID matching office/state/district is not encoded; take the
                # single ID if only one, else leave unresolved
                ids = cands[0]['fec_candidate_ids']
                if len(ids) == 1:
                    r['cand_id'] = ids[0]
                    r['resolved_via'] = 'roster'
                    resolved += 1
                else:
                    unresolved.append(r)
            elif r['sup_opp'] == 'S':
                # Support rows with no FEC ID anywhere still identify a backed
                # candidate in the race: use a name-based synthetic key. This
                # matters for the credit rule (e.g. Steven Irwin, PA-12 2022:
                # $660,319.30 of UDP support, non-roster, no FEC ID in the file).
                # Such a candidate can never map to a roster person, so any
                # credit to them lands in the non-roster bucket.
                r['cand_id'] = f"__name__:{r['cand_name'].upper()}|{r['state']}|{r['district']}|{r['office']}"
                r['resolved_via'] = 'name_only'
                resolved += 1
            else:
                unresolved.append(r)
print(f'blank cand_id UDP rows resolved: {resolved}; unresolved: {len(unresolved)} '
      f"(support: {sum(1 for r in unresolved if r['sup_opp'] == 'S')}, "
      f"oppose: {sum(1 for r in unresolved if r['sup_opp'] == 'O')})")
for r in unresolved[:20]:
    print('  UNRESOLVED:', r['cycle'], r['cand_name'], r['state'], r['district'], r['office'], r['sup_opp'], r['amount'])
print('name-index collisions:', collisions[:5], 'count:', len(collisions))

# ---------- 3. Sanity: reproduce existing support totals ----------
support_by_id = collections.defaultdict(float)
for r in udp_rows:
    if r['sup_opp'] == 'S' and r['cand_id']:
        support_by_id[r['cand_id']] += r['amount']
person_support = collections.defaultdict(float)
for cid, amt in support_by_id.items():
    pk = id_to_person.get(cid)
    if pk:
        person_support[pk] += amt
    else:
        person_support[f'__nonroster__{cid}'] += amt

existing = {}
with open(ROOT / CFG['paths']['dataset_csv'], newline='') as f:
    for row in csv.DictReader(f):
        existing[row['person_key']] = float(row['udp_ie_support_career']) if row['udp_ie_support_career'] not in ('unknown', '') else None
mismatch = []
for pk, val in existing.items():
    mine = round(person_support.get(pk, 0.0), 2)
    if val is None:
        continue
    if abs(mine - val) > 0.005:
        mismatch.append((pk, val, mine))
print(f'support reproduction: {len(existing)} persons checked, {len(mismatch)} mismatches')
for m in mismatch[:10]:
    print('  MISMATCH:', m)
nonroster_support = {k: v for k, v in person_support.items() if k.startswith('__nonroster__')}
print('non-roster backed candidates (support $):', {k: round(v, 2) for k, v in sorted(nonroster_support.items(), key=lambda x: -x[1])})

# ---------- 4. Race-level credit rule ----------
races = collections.defaultdict(lambda: {'backed': set(), 'backed_names': {}, 'oppose_total': 0.0,
                                         'oppose_rows': 0, 'support_total': 0.0, 'opposed_names': collections.Counter(),
                                         'self_oppose_total': 0.0, 'self_oppose_rows': []})
for r in udp_rows:
    key = (r['cycle'], r['office'], r['state'], r['district'], r['ele_type'])
    rec = races[key]
    if r['sup_opp'] == 'S':
        if r['cand_id']:
            rec['backed'].add(r['cand_id'])
            rec['backed_names'][r['cand_id']] = r['cand_name']
        rec['support_total'] += r['amount']
    elif r['sup_opp'] == 'O':
        rec['oppose_total'] += r['amount']
        rec['oppose_rows'] += 1
        rec['opposed_names'][r['cand_name']] += r['amount']

credit_by_person = collections.defaultdict(float)   # person_key -> credited oppose $
credit_detail = []      # (race, backed person_key/name, oppose_total, opposed names)
no_credit = []          # (race, n_backed, backed names, oppose_total, opposed names)
nonroster_credit = collections.defaultdict(float)
for key, rec in sorted(races.items()):
    if rec['oppose_total'] <= 0:
        continue
    if len(rec['backed']) == 1:
        bid = next(iter(rec['backed']))
        # Self-opposition guard: spending opposing the backed candidate themself is
        # NOT spending against an opponent, so it is excluded from the credit.
        # (NY-16 2024 has one such row: $84,325.84 opposing Latimer, whom UDP backed.)
        backed_name = rec['backed_names'][bid].upper()
        self_opp = 0.0
        for r in udp_rows:
            if (r['cycle'], r['office'], r['state'], r['district'], r['ele_type']) != key or r['sup_opp'] != 'O':
                continue
            if r['cand_id'] == bid or (not r['cand_id'] and r['cand_name'].upper() == backed_name):
                self_opp += r['amount']
                rec['self_oppose_rows'].append((r['cand_name'], r['amount'], r['ele_type'], r['tran_id']))
        rec['self_oppose_total'] = self_opp
        creditable = rec['oppose_total'] - self_opp
        pk = id_to_person.get(bid)
        if pk:
            credit_by_person[pk] += creditable
            credit_detail.append((key, pk, rec['backed_names'][bid], creditable, dict(rec['opposed_names'])))
        else:
            nonroster_credit[bid] += creditable
            credit_detail.append((key, f'__nonroster__{bid}', rec['backed_names'][bid], creditable, dict(rec['opposed_names'])))
    else:
        no_credit.append((key, len(rec['backed']), [rec['backed_names'].get(b, b) for b in sorted(rec['backed'])],
                          rec['oppose_total'], dict(rec['opposed_names'])))

print(f'\nraces with UDP oppose spending: {len(credit_detail) + len(no_credit)}')
print(f'races credited (exactly one backed): {len(credit_detail)}; races NOT credited: {len(no_credit)}')
print(f'total credited to roster persons: ${sum(credit_by_person.values()):,.2f}')
print(f'total credited to NON-roster backed candidates: ${sum(nonroster_credit.values()):,.2f}')
print('\n--- races NOT credited, oppose >= $%s ---' % f"{CFG['verification']['opposition_uncredited_report_threshold']:,}")
for key, n, names, opp, opposed in sorted(no_credit, key=lambda x: -x[3]):
    if opp >= CFG['verification']['opposition_uncredited_report_threshold']:
        print(f'  {key}: backed={n} {names}; oppose=${opp:,.2f}; opposed={opposed}')

print('\n--- TEST 1: NY-16 2024 (House, NY, 16) ---')
for key, rec in sorted(races.items()):
    if key[:4] == (2024, 'H', 'NY', '16'):
        print(f"  phase {key[4]}: backed:", [(b, rec['backed_names'][b]) for b in sorted(rec['backed'])])
        print('    support total: $', f"{rec['support_total']:,.2f}")
        print('    oppose total (all): $', f"{rec['oppose_total']:,.2f}")
        print('    self-opposition excluded: $', f"{rec['self_oppose_total']:,.2f}", rec['self_oppose_rows'])
        print('    creditable oppose: $', f"{rec['oppose_total'] - rec['self_oppose_total']:,.2f}")
        print('    opposed:', dict(rec['opposed_names']))
print('--- TEST 2: MI-Sen 2026 (Senate, MI, 00) ---')
for key, rec in sorted(races.items()):
    if key[:4] == (2026, 'S', 'MI', '00'):
        print(f"  phase {key[4]}: backed:", [(b, rec['backed_names'][b]) for b in sorted(rec['backed'])])
        print('    support total: $', f"{rec['support_total']:,.2f}")
        print('    oppose total: $', f"{rec['oppose_total']:,.2f}")
        print('    opposed:', dict(rec['opposed_names']))

# Latimer + Rogers/Stevens/El-Sayed person figures
for name in ('George Latimer', 'Mike Rogers', 'Haley Stevens', 'Abdul El-Sayed'):
    for p in roster:
        if name.split()[0].lower() in p['first_name'].lower() and name.split()[-1].lower() in p['last_name'].lower():
            pk = p['person_key']
            print(f'{name}: person_key={pk} support=${person_support.get(pk,0):,.2f} '
                  f'opposing-opponents credit=${credit_by_person.get(pk,0):,.2f} '
                  f'total benefit=${person_support.get(pk,0)+credit_by_person.get(pk,0):,.2f}')

# per-cycle reconciliation vs the prior UDP pull's deduped totals (S+O, all candidates)
prior_cycle_totals = {int(k): v for k, v in CFG['verification']['udp_prior_cycle_totals'].items()}
for yr in CYCLES:
    tot = sum(r['amount'] for r in udp_rows if r['cycle'] == yr)
    print(f'cycle {yr}: my deduped S+O total ${tot:,.2f} vs prior pull ${prior_cycle_totals[yr]:,.2f} '
          f'diff ${tot - prior_cycle_totals[yr]:,.2f}')
print('all-cycles S+O total: $', f"{sum(r['amount'] for r in udp_rows):,.2f}")

# save intermediates for the merge step
json.dump({
    'credit_by_person': {k: round(v, 2) for k, v in credit_by_person.items()},
    'credit_detail': [[list(k), pk, nm, round(opp, 2), opp_names] for k, pk, nm, opp, opp_names in credit_detail],
    'no_credit': [[list(k), n, names, round(opp, 2), opp_names] for k, n, names, opp, opp_names in no_credit],
    'nonroster_credit': {k: round(v, 2) for k, v in nonroster_credit.items()},
    'support_mismatches': mismatch,
    'unresolved_blank_rows': len(unresolved),
    'aipac_schedule_e_rows': len(aipac_rows),
}, open(ROOT / CFG['paths']['opposition_computed'], 'w'), indent=1)
print('\nwrote data/intermediate/opposition-computed.json')

#!/usr/bin/env python3
"""UDP independent-expenditure pull for the Congress money tracker.

Reads the staged bulk IE files (`data/raw/ie/<cycle>/
independent_expenditure_<cycle>.csv`, cycles from config `cycles.udp`)
and produces, per roster person:
- `data/intermediate/money_udp.csv` — career UDP support total + `data_notes`
  (665 rows, roster order).
- `data/intermediate/money_udp_per_cycle.json` — per-cycle UDP support breakdown
  (the input `merge_dataset.py` reads for `udp_per_cycle`).

This is the script the original UDP pull (see `research/pull-log-b.md`) never
had saved: methodology §6 records that the merge independently recomputed
these figures from the staged IE files with the same rules and reproduced
`money_udp.csv` exactly (0 mismatches). The rules, all from pull-log-b:

- Committee: UDP (`spe_id` from config `committees.udp`). Support rows
  only (`sup_opp = 'S'`) count toward a person's support total; oppose
  rows (`sup_opp = 'O'`) are never added to any total — they are recorded
  in `data_notes` only, for the people UDP spent against.
- Dedup by `tran_id`: keep the latest `receipt_dat`, tie-break highest
  `file_num` (the IE files carry original + amended reports).
- Blank `cand_id` rows are resolved, in order: (1) a name index built
  from deduped non-blank rows, keyed on (candidate name, state, district,
  office); (2) a roster fallback on last/first name + state + district,
  which only fires when exactly one roster person matches and that person
  has exactly one FEC ID. Support rows that still have no ID get a
  name-based identity (`__name__:NAME|STATE|DISTRICT|OFFICE`) so they
  still count as a backed candidate for the opposition-credit race rule —
  they can never map to a roster person. Oppose rows that still have no
  ID stay unresolved (30 in 2022, all Cisneros/Garcia) and are never
  counted as support.
- Amounts resolved from a blank `cand_id` are flagged: the
  `udp_per_cycle` entry carries
  `"attribution": "name_state_district_office_match; cand_id blank in FEC
  file"` and the person's note records the attributed amount. (2022 only:
  Davis $2,102,637.82, Foushee $2,128,196.18, Mullin $588,768.26.)

Note text, per person (verified against the committed file):
- No FEC IDs: `No FEC candidate ID on file; not searchable in IE data.`
- Support > 0: `UDP support by cycle (<current> partial) — <cycle>:
  $<amt>; ...` (cycles with support, ascending), then
  ` Summed across <n> candidate IDs.` when the person has > 1 FEC ID,
  then one ` Includes $<amt> of <cycle> support identified by candidate
  name/state/district; the FEC file left cand_id blank for those rows.`
  per name-attributed cycle, then the oppose suffix.
- Support = 0: `No UDP support spending found in <cycles> IE files.`
  (cycles joined with `/`), then the same `Summed across` suffix, then
  the oppose suffix.
- Oppose suffix (when UDP spent against the person):
  ` UDP also spent $<amt> opposing this person (excluded from support
  total).`

The per-cycle reconciliation totals are printed and checked against
config `verification.udp_prior_cycle_totals` (deduped S+O, all
candidates). If an old `money_udp.csv` is present it is compared
(informational only — a re-pull on newer filings is expected to differ).
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
CURRENT = CFG['cycles']['current']
ATTRIBUTION = 'name_state_district_office_match; cand_id blank in FEC file'


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


# ---------- 1. Load + dedup per cycle (same rule as compute_opposition.py) ----------
all_rows = []
dedup_stats = {}
for yr in CYCLES:
    path = f'{IE_DIR}/{yr}/independent_expenditure_{yr}.csv'
    best = {}
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
print(f'UDP deduped rows: {len(udp_rows)} (S={sum(1 for r in udp_rows if r["sup_opp"] == "S")}, '
      f'O={sum(1 for r in udp_rows if r["sup_opp"] == "O")})')
print(f'AIPAC PAC deduped Schedule E rows: {len(aipac_rows)} (expected 0; '
      f'if nonzero, there is no AIPAC opposition column by design)')

# ---------- 2. Resolve blank cand_id via name index, then roster ----------
name_index = {}
collisions = []
for r in udp_rows:
    if r['cand_id']:
        key = (r['cand_name'].upper(), r['state'], r['district'], r['office'])
        if key in name_index and name_index[key] != r['cand_id']:
            collisions.append((key, name_index[key], r['cand_id']))
        name_index[key] = r['cand_id']

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
            nm = r['cand_name']
            last = nm.split(',')[0].strip().upper() if ',' in nm else nm.strip().upper()
            first = nm.split(',')[1].strip().upper() if ',' in nm and len(nm.split(',')) > 1 else ''
            cands = [p for p in roster if p['last_name'].upper() == last
                     and (not first or p['first_name'].upper().startswith(first.split()[0]))
                     and p['state'] == r['state']
                     and (str(p.get('district_119') or '').zfill(2) == r['district'] or str(p.get('district_120') or '').zfill(2) == r['district'])]
            if len(cands) == 1 and len(cands[0].get('fec_candidate_ids') or []) >= 1:
                ids = cands[0]['fec_candidate_ids']
                if len(ids) == 1:
                    r['cand_id'] = ids[0]
                    r['resolved_via'] = 'roster'
                    resolved += 1
                else:
                    unresolved.append(r)
            elif r['sup_opp'] == 'S':
                r['cand_id'] = f"__name__:{r['cand_name'].upper()}|{r['state']}|{r['district']}|{r['office']}"
                r['resolved_via'] = 'name_only'
                resolved += 1
            else:
                unresolved.append(r)
print(f'blank cand_id UDP rows resolved: {resolved}; unresolved: {len(unresolved)} '
      f"(support: {sum(1 for r in unresolved if r['sup_opp'] == 'S')}, "
      f"oppose: {sum(1 for r in unresolved if r['sup_opp'] == 'O')})")
print('name-index collisions:', len(collisions))

# ---------- 3. Aggregate support / oppose per candidate ID ----------
# support[(cand_id, cycle)] = dollars; attributed[(cand_id, cycle)] = dollars
# that came from blank-cand_id rows; oppose[cand_id] = dollars.
support = collections.defaultdict(float)
attributed = collections.defaultdict(float)
oppose = collections.defaultdict(float)
for r in udp_rows:
    if not r['cand_id']:
        continue  # unresolved oppose rows: never counted as support
    if r['sup_opp'] == 'S':
        support[(r['cand_id'], r['cycle'])] += r['amount']
        if r.get('resolved_via') in ('name_index', 'roster'):
            attributed[(r['cand_id'], r['cycle'])] += r['amount']
    elif r['sup_opp'] == 'O':
        oppose[r['cand_id']] += r['amount']

# ---------- 4. Reconciliation vs the prior pull's deduped totals ----------
prior = {int(k): v for k, v in CFG['verification']['udp_prior_cycle_totals'].items()}
for yr in CYCLES:
    tot = sum(r['amount'] for r in udp_rows if r['cycle'] == yr)
    mark = 'OK' if abs(tot - prior[yr]) < 0.005 else 'MISMATCH'
    print(f'cycle {yr}: deduped S+O total ${tot:,.2f} vs prior ${prior[yr]:,.2f} [{mark}]')
    if mark == 'MISMATCH':
        raise SystemExit(f'UDP S+O total for {yr} does not reconcile with the prior pull')
for yr in CYCLES:
    roster_tot = round(sum(amt for (cid, cy), amt in support.items()
                           if cy == yr and cid in id_to_person), 2)
    print(f'cycle {yr}: roster support total ${roster_tot:,.2f}')

# ---------- 5. Per-person rows ----------
out_rows = []
per_cycle = {}
for p in roster:
    pk = p['person_key']
    ids = p.get('fec_candidate_ids') or []
    entries = []
    for (cid, cy), amt in sorted(support.items()):
        if cid in ids and amt != 0:
            entry = {'cycle': cy, 'candidate_id': cid,
                     'udp_ie_support': round(amt, 2)}
            if attributed.get((cid, cy), 0):
                entry['attribution'] = ATTRIBUTION
            entries.append(entry)
    entries.sort(key=lambda e: (e['cycle'], e['candidate_id']))
    total = round(sum(e['udp_ie_support'] for e in entries), 2)
    opp_total = round(sum(oppose.get(cid, 0.0) for cid in ids), 2)

    # data_notes
    if not ids:
        note = 'No FEC candidate ID on file; not searchable in IE data.'
    else:
        if total != 0:
            by_cycle = '; '.join(
                f"{e['cycle']}: ${e['udp_ie_support']:,.2f}" for e in entries)
            note = f'UDP support by cycle ({CURRENT} partial) — {by_cycle}.'
        else:
            cycles = '/'.join(str(c) for c in CYCLES)
            note = f'No UDP support spending found in {cycles} IE files.'
        if len(ids) > 1:
            note += f' Summed across {len(ids)} candidate IDs.'
        for e in entries:
            attr = attributed.get((e['candidate_id'], e['cycle']), 0)
            if attr:
                note += (f' Includes ${attr:,.2f} of {e["cycle"]} support identified by '
                         f'candidate name/state/district; the FEC file left cand_id blank '
                         f'for those rows.')
        if opp_total:
            note += (f' UDP also spent ${opp_total:,.2f} opposing this person '
                     f'(excluded from support total).')
    out_rows.append({'person_key': pk, 'full_name': p['full_name'],
                     'fec_candidate_ids': ';'.join(ids),
                     'udp_ie_support_career': f'{total:.2f}',
                     'data_notes': note})
    per_cycle[pk] = {'person_key': pk, 'full_name': p['full_name'],
                     'udp_per_cycle': entries}

with open(ROOT / CFG['paths']['money_udp'], 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['person_key', 'full_name', 'fec_candidate_ids',
                                      'udp_ie_support_career', 'data_notes'])
    w.writeheader()
    w.writerows(out_rows)
print(f"wrote {CFG['paths']['money_udp']} ({len(out_rows)} rows)")

with open(ROOT / CFG['paths']['money_udp_per_cycle'], 'w') as f:
    json.dump(per_cycle, f, indent=1)
print(f"wrote {CFG['paths']['money_udp_per_cycle']} "
      f"({sum(len(v['udp_per_cycle']) for v in per_cycle.values())} entries, "
      f"{sum(1 for v in per_cycle.values() if v['udp_per_cycle'])} persons with support)")

# Informational comparison against the previous money_udp.csv, if present.
# (A re-pull on newer filings is expected to differ; this only reports.)
print(f"roster UDP support total: ${sum(float(r['udp_ie_support_career']) for r in out_rows):,.2f}")

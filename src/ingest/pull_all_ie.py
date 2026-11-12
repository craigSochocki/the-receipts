#!/usr/bin/env python3
"""All-independent-expenditures pull for the Congress money tracker.

Reads the staged bulk IE files (`data/raw/ie/<cycle>/
independent_expenditure_<cycle>.csv`, cycles 2022/2024/2026 from config
`cycles.udp`) and produces:
- `data/intermediate/all_ie_per_cycle.json` — per candidate, per-cycle support/oppose
  totals for ALL identified candidates (not just roster members), plus a
  per-committee breakdown of the top spenders.
- `data/intermediate/all_ie.csv` — one row per roster person with career all-IE
  support, oppose and total, plus the same for the latest cycle (2026).
  "Career" here means the covered cycles (2022+2024+2026) only: no IE
  files are staged for earlier cycles, so these are NOT full-career
  totals. Ranks are computed later; this script writes totals only.

These columns are SEPARATE from `total_accepted` (individual + corporate
PAC + AIPAC direct). Nothing in this script touches that definition.

Filter rules (applied in this order, per cycle, on deduped rows):
1. Dedup by (spe_id, tran_id) — keep the latest `receipt_dat`,
   tie-break highest `file_num`. This is the pull_udp /
   compute_opposition rule, scoped to the filer: the FEC file
   description says TRA_ID is "unique within the specific filing", and
   the FEC's own dedup guidance is to sort "by filer and date and
   targeted candidate". Tran IDs are NOT globally unique — e.g. `SE.4117`
   is shared by many committees — so deduping by tran_id alone across
   all committees wrongly drops real spending (it understates the
   roster total by ~$105M in 2022, ~$147M in 2024, ~$455M in 2026).
   Within one committee (UDP) the two keys coincide, which is why the
   UDP pull's tran_id-only dedup was correct there.
2. REGISTERED committee: `spe_id` must be present in the same-cycle
   committee master (`data/raw/cm/<cycle>/cm.txt`, col 1). This kills
   the bogus billions: "Committee of 300" C00800508, C00874586,
   C00785352, "Warren Buffet" C00946087, C00944025, etc. are in no cm
   file for their cycle.
3. IDENTIFIED candidate: non-blank `cand_id` that resolves to a real
   candidate — present in ANY staged weball file (all cycles
   1980-2026, `data/raw/weball/weball*.txt`) OR one of the roster's
   FEC candidate IDs. Same-cycle weball alone is NOT a valid test: real
   roster IDs are missing from every weball file (Glenn Ivey H2MD04315,
   Laura Gillen H4NY04158), while the bogus IDs (Akhlaghy H2NY05118 /
   P40007304 / P40019226, Bettis H6FL11274) are in NO weball file and
   not in the roster. Blank `cand_id` rows are EXCLUDED from the
   published totals (see the blank-attribution diagnostic below).
4. Support (`sup_opp='S'`) and oppose (`sup_opp='O'`) are summed
   separately, never netted. Rows with blank `sup_opp` (a handful,
   ~$10k/cycle) count in the total only and are reported.

Blank-cand_id attribution (DIAGNOSTIC ONLY, not added to totals):
the pull_udp name-index + roster-fallback machinery is run over the
registered blank rows and the amounts are reported, but they are NOT
added to any published total. Reason: the validation targets for this
pull (see below) exclude them — with global name-index attribution,
Congressional Leadership Fund alone would add ~$199M of 2026 oppose
spending and appear as the #2 roster-targeted spender, while the
validated top-5 list has no CLF and matches the no-attribution figures
to the dollar. CLF files `cand_id` blank systematically (2029 blank
rows in 2024, 787 in 2026); attributing a systematic blank-filer by
name needs a coordinator decision, not a silent inclusion. The
diagnostic amounts are in the JSON under
`blank_attribution_diagnostic`.

Form-type double-count check (F24 vs F3X trap):
the FEC API Schedule E endpoint returns every expenditure twice (an
F24 24/48-hour notice + the F3X Schedule E itemization, same
transaction_id). This pull uses the BULK files, not the API. The bulk
file has NO form-type column, so F24/F3X cannot be separated by form
— but pull-log-b §7 verified the bulk file carries ONE copy (the
notice copy: its file_num/image_num match the F24 filing), and the
(spe_id, tran_id) dedup removes any same-transaction repeat. Proof in
this run: the UDP 2024 deduped S+O total reproduces the tracker's
$38,044,932.69 TO THE CENT; if the file double-counted across form
types it would be ~2x. A near-duplicate scan (same committee +
candidate + exp_date + amount + sup_opp under DIFFERENT tran_ids, with
different image numbers = different filings) is also run and reported;
those rows are treated as separate expenditures, NOT collapsed —
collapsing them would break the exact UDP 2024 reproduction (UDP
2024 alone has 27 such groups, $2,850,554.43).

Validation targets (from the task brief — the coordinator's prior
filtered, deduped figures; printed, not hard-failed except UDP):
- UDP 2024 deduped S+O = $38,044,932.69 (HARD check, to the cent).
- Roster-targeted IE: 2022 $635.2M / 2024 $959.1M / 2026 $2,264.3M.
- Top 2026 non-UDP roster-targeted spenders: NO GOING BACK PAC
  $202.5M (O), HMP $146.7M (O), WinSenate $131.1M (O), TEXAS PAC
  $112.2M (O), DEFEND AMERICAN JOBS $70.7M (S).
- 2026 roster split: Senate $1,376.4M vs House $887.9M;
  oppose $1,479M vs support $785M.

Coverage: staged IE files cover 2022/2024/2026 only. Per the FEC
independent-expenditures file description (fetched Nov 12, 2026),
historical data is available beginning with the 2010 cycle, and the
bulk-data index publishes `independent_expenditure_YYYY.csv` per cycle
— so 2010/2012/2014/2016/2018/2020 files exist and are NOT staged
here. Expanding to them is a follow-up (each file is ~14-19 MB);
pre-2010 cycles have no such file.
"""
import csv, glob, json, collections
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
IM = str(ROOT / CFG['paths']['intermediate'])
IE_DIR = str(ROOT / CFG['paths']['ie'])
BULK_DIR = str(ROOT / CFG['paths']['bulk'])
UDP = CFG['committees']['udp']
CYCLES = tuple(CFG['cycles']['udp'])
CURRENT = CFG['cycles']['current']
DATA_AS_OF = CFG.get('data_as_of', '')

# Validation targets from the task brief (coordinator's prior figures).
EXPECTED_ROSTER_TOTAL = {2022: 635.2e6, 2024: 959.1e6, 2026: 2264.3e6}
EXPECTED_TOP_2026 = [  # (committee name, direction, $M)
    ('NO GOING BACK PAC INC.', 'O', 202.5e6),
    ('HOUSE MAJORITY PAC', 'O', 146.7e6),   # filed as HMP; name matched loosely
    ('WINSENATE', 'O', 131.1e6),
    ('TEXAS PAC', 'O', 112.2e6),
    ('DEFEND AMERICAN JOBS', 'S', 70.7e6),
]
EXPECTED_SENATE_HOUSE_2026 = (1376.4e6, 887.9e6)
EXPECTED_SO_2026 = (785e6, 1479e6)  # (support, oppose)


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


def r2(x):
    return round(x + 0.0, 2)


# ---------- 0. Identity sources ----------
# Committee master per cycle (registered committees).
cm_by_cycle = {}
for yr in CYCLES:
    s = set()
    with open(f'{BULK_DIR}/cm/{yr}/cm.txt') as f:
        for line in f:
            parts = line.split('|')
            if parts and parts[0].strip():
                s.add(parts[0].strip())
    cm_by_cycle[yr] = s
    print(f'cm {yr}: {len(s):,} registered committees')

# Identified candidates: any staged weball file (all cycles 1980-2026)
# UNION the roster's FEC IDs. Same-cycle weball alone is invalid (see
# docstring: real roster IDs Ivey H2MD04315 / Gillen H4NY04158 are in
# no weball file at all).
weball_ids = set()
for path in glob.glob(f'{BULK_DIR}/weball/weball*.txt'):
    with open(path) as f:
        for line in f:
            p = line.rstrip('\n').split('|')
            if p and p[0].strip():
                weball_ids.add(p[0].strip())
print(f'weball (all staged cycles): {len(weball_ids):,} distinct candidate IDs')

roster = json.load(open(ROOT / CFG['paths']['roster']))
id_to_person = {}
person_by_key = {}
for p in roster:
    person_by_key[p['person_key']] = p
    for cid in (p.get('fec_candidate_ids') or []):
        id_to_person.setdefault(cid, p['person_key'])
print(f'roster: {len(roster)} persons, {len(id_to_person)} FEC IDs; '
      f'no-ID persons: {[p["full_name"] for p in roster if not p.get("fec_candidate_ids")]}')


def identified(cid):
    return cid in weball_ids or cid in id_to_person


# ---------- 1. Load + dedup per cycle (key: filer + tran_id) ----------
# dedup_stats[yr] and all_rows hold deduped rows, all cycles.
all_rows = []
exclusions = {}   # yr -> bucket dicts (rows + dollars, sequential/disjoint)
udp_totals = {}
near_dup = {}     # yr -> {groups, extra_amount}
for yr in CYCLES:
    path = f'{IE_DIR}/{yr}/independent_expenditure_{yr}.csv'
    with open(path, newline='') as f:
        header = f.readline().strip().split(',')
    assert 'file_num' in header and 'tran_id' in header
    has_form_type = any(h in ('form_type', 'form_tp', 'filing_form') for h in header)
    best = {}
    n_raw = 0
    raw_amt = 0.0
    dedup_removed_rows = 0
    dedup_removed_amt = 0.0
    with open(path, newline='') as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r):
            n_raw += 1
            amt = parse_amt(row['exp_amo'])
            raw_amt += amt
            tid = (row.get('tran_id') or '').strip()
            # Blank tran_id: never deduped against another row.
            key = (row['spe_id'], tid) if tid else (row['spe_id'], f'__blank__{yr}_{i}')
            cand = {
                'cycle': int(row['fec_election_yr']),
                'cand_id': (row['cand_id'] or '').strip(),
                'cand_name': (row['cand_name'] or '').strip(),
                'spe_id': row['spe_id'],
                'spe_nam': (row.get('spe_nam') or '').strip(),
                'sup_opp': (row['sup_opp'] or '').strip(),
                'office': (row['can_office'] or '').strip(),
                'state': (row['can_office_state'] or '').strip(),
                'district': (row['can_office_dis'] or '').strip(),
                'ele_type': (row['ele_type'] or '').strip(),
                'exp_date': (row.get('exp_date') or '').strip(),
                'amount': amt,
                'receipt_dat': row.get('receipt_dat', ''),
                'file_num': parse_filenum(row.get('file_num')),
                'tran_id': tid,
                'image_num': (row.get('image_num') or '').strip(),
            }
            if key not in best:
                best[key] = cand
            else:
                prev = best[key]
                if (parse_date(cand['receipt_dat']), cand['file_num']) > \
                   (parse_date(prev['receipt_dat']), prev['file_num']):
                    dedup_removed_amt += prev['amount']
                    best[key] = cand
                else:
                    dedup_removed_amt += cand['amount']
                dedup_removed_rows += 1
    rows = list(best.values())
    all_rows.extend(rows)

    # Near-duplicate scan (form-type double-count check): same committee,
    # candidate, exp_date, amount and direction under DIFFERENT tran_ids.
    # These have different image numbers (different filings) and are
    # treated as separate expenditures; the scan only quantifies them.
    groups = collections.defaultdict(set)
    for x in rows:
        if x['cand_id']:
            groups[(x['spe_id'], x['cand_id'], x['exp_date'], x['amount'], x['sup_opp'])].add(x['tran_id'])
    multi = {k: v for k, v in groups.items() if len(v) > 1}
    near_dup[yr] = {
        'groups': len(multi),
        'extra_amount_if_collapsed': r2(sum((len(v) - 1) * k[3] for k, v in multi.items())),
    }

    # Sequential exclusion buckets (disjoint; applied in this order).
    unreg = [x for x in rows if x['spe_id'] not in cm_by_cycle[yr]]
    rest = [x for x in rows if x['spe_id'] in cm_by_cycle[yr]]
    blank = [x for x in rest if not x['cand_id']]
    rest2 = [x for x in rest if x['cand_id']]
    notid = [x for x in rest2 if not identified(x['cand_id'])]
    included = [x for x in rest2 if identified(x['cand_id'])]
    for x in included:
        x['included'] = True
    exclusions[yr] = {
        'raw_rows': n_raw,
        'raw_amount': r2(raw_amt),
        'deduped_rows': len(rows),
        'deduped_amount': r2(sum(x['amount'] for x in rows)),
        'dedup_removed': {'rows': dedup_removed_rows, 'amount': r2(dedup_removed_amt)},
        'unregistered_committee': {'rows': len(unreg),
                                   'amount': r2(sum(x['amount'] for x in unreg))},
        'blank_candidate': {'rows': len(blank),
                            'amount': r2(sum(x['amount'] for x in blank))},
        'candidate_not_identified': {'rows': len(notid),
                                     'amount': r2(sum(x['amount'] for x in notid))},
        'included': {'rows': len(included),
                     'amount': r2(sum(x['amount'] for x in included))},
        'has_form_type_column': has_form_type,
        'near_duplicates_distinct_tran_id': near_dup[yr],
        'blank_sup_opp_included': {
            'rows': sum(1 for x in included if not x['sup_opp']),
            'amount': r2(sum(x['amount'] for x in included if not x['sup_opp']))},
        'negative_amount_included': {
            'rows': sum(1 for x in included if x['amount'] < 0),
            'amount': r2(sum(x['amount'] for x in included if x['amount'] < 0))},
    }
    udp_totals[yr] = r2(sum(x['amount'] for x in rows if x['spe_id'] == UDP))
    print(f"{yr}: raw {n_raw:,} rows ${raw_amt:,.2f} -> deduped {len(rows):,} "
          f"rows (removed {dedup_removed_rows:,} rows, ${dedup_removed_amt:,.2f}); "
          f"unregistered ${exclusions[yr]['unregistered_committee']['amount']:,.2f}; "
          f"blank cand ${exclusions[yr]['blank_candidate']['amount']:,.2f}; "
          f"not identified ${exclusions[yr]['candidate_not_identified']['amount']:,.2f}; "
          f"included ${exclusions[yr]['included']['amount']:,.2f}")

# ---------- 2. HARD CHECK: UDP 2024 reproduces the tracker total ----------
prior = {int(k): v for k, v in CFG['verification']['udp_prior_cycle_totals'].items()}
for yr in CYCLES:
    mark = 'OK' if abs(udp_totals[yr] - prior[yr]) < 0.005 else 'MISMATCH'
    print(f'UDP cycle {yr}: deduped S+O ${udp_totals[yr]:,.2f} vs prior '
          f'${prior[yr]:,.2f} [{mark}]')
    if mark == 'MISMATCH':
        raise SystemExit(f'UDP S+O total for {yr} does not reconcile with the prior pull')

# ---------- 3. Blank-cand_id attribution DIAGNOSTIC (not added to totals) ----------
# pull_udp machinery: name index from included (identified, non-blank)
# rows, keyed (name, state, district, office); then a roster fallback
# (unique roster person on last/first + state + district with exactly
# one FEC ID). Amounts are REPORTED ONLY. The index is built PER CYCLE:
# the same (name, state, district, office) can legitimately map to
# different candidate IDs in different cycles (a candidate files under
# a new ID), so a cross-cycle index would misattribute.
name_index_by_cycle = {}
name_collisions = 0
for yr in CYCLES:
    idx = {}
    for x in all_rows:
        if x.get('included') and x['cycle'] == yr and x['cand_id']:
            key = (x['cand_name'].upper(), x['state'], x['district'], x['office'])
            if key in idx and idx[key] != x['cand_id']:
                name_collisions += 1
            idx.setdefault(key, x['cand_id'])
    name_index_by_cycle[yr] = idx
blank_diag = {}
for yr in CYCLES:
    name_index = name_index_by_cycle[yr]
    blank_rows = [x for x in all_rows
                  if x['cycle'] == yr and x['spe_id'] in cm_by_cycle[yr] and not x['cand_id']]
    resolved_all = resolved_roster = unresolved = 0.0
    fallback_roster = 0.0
    by_committee = collections.defaultdict(float)
    for x in blank_rows:
        key = (x['cand_name'].upper(), x['state'], x['district'], x['office'])
        cid = name_index.get(key)
        if cid and identified(cid):
            resolved_all += x['amount']
            if cid in id_to_person:
                resolved_roster += x['amount']
                by_committee[(x['spe_id'], x['spe_nam'])] += x['amount']
        else:
            # roster fallback (pull_udp rule)
            nm = x['cand_name']
            last = nm.split(',')[0].strip().upper() if ',' in nm else nm.strip().upper()
            first = nm.split(',')[1].strip().upper() if ',' in nm and len(nm.split(',')) > 1 else ''
            cands = [p for p in roster
                     if p['last_name'].upper() == last
                     and (not first or p['first_name'].upper().startswith(first.split()[0]))
                     and p['state'] == x['state']
                     and (str(p.get('district_119') or '').zfill(2) == x['district']
                          or str(p.get('district_120') or '').zfill(2) == x['district'])]
            if len(cands) == 1 and len(cands[0].get('fec_candidate_ids') or []) == 1:
                fallback_roster += x['amount']
            else:
                unresolved += x['amount']
    blank_diag[yr] = {
        'blank_registered_rows': len(blank_rows),
        'blank_registered_amount': r2(sum(x['amount'] for x in blank_rows)),
        'name_index_resolved_all_candidates': r2(resolved_all),
        'name_index_resolved_roster': r2(resolved_roster),
        'roster_fallback_resolved_roster': r2(fallback_roster),
        'unresolved': r2(unresolved),
        'note': 'DIAGNOSTIC ONLY — none of these amounts is added to any published total.',
        'top_committees_behind_roster_resolved': [
            {'committee_id': sid, 'committee_name': nm, 'amount': r2(amt)}
            for (sid, nm), amt in sorted(by_committee.items(), key=lambda kv: -kv[1])[:5]],
    }
    print(f"{yr} blank diagnostic: registered blank ${blank_diag[yr]['blank_registered_amount']:,.2f}; "
          f"name-index resolved roster ${resolved_roster:,.2f}; "
          f"roster-fallback roster ${fallback_roster:,.2f}; unresolved ${unresolved:,.2f}")
print(f'name-index collisions (same name/state/district/office -> >1 ID): {name_collisions}')

# ---------- 4. Aggregate per candidate, per cycle (ALL identified candidates) ----------
# cand_tot[(cand_id, cycle)] = {support, oppose, no_direction, total, rows}
cand_tot = collections.defaultdict(lambda: {'support': 0.0, 'oppose': 0.0,
                                            'no_direction': 0.0, 'rows': 0})
cand_by_cmte = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0, 0]))
cand_label = {}  # (cand_id, cycle) -> (name, office, state, district) from largest row
for x in all_rows:
    if not x.get('included'):
        continue
    key = (x['cand_id'], x['cycle'])
    t = cand_tot[key]
    if x['sup_opp'] == 'S':
        t['support'] += x['amount']
    elif x['sup_opp'] == 'O':
        t['oppose'] += x['amount']
    else:
        t['no_direction'] += x['amount']
    t['rows'] += 1
    c = cand_by_cmte[key][(x['spe_id'], x['spe_nam'])]
    if x['sup_opp'] == 'S':
        c[0] += x['amount']
    elif x['sup_opp'] == 'O':
        c[1] += x['amount']
    c[2] += 1
    prev = cand_label.get(key)
    if prev is None or abs(x['amount']) > abs(prev[4]):
        cand_label[key] = (x['cand_name'], x['office'], x['state'], x['district'], x['amount'])

per_candidate = []
for (cid, cy), t in sorted(cand_tot.items()):
    name, office, state, district, _ = cand_label[(cid, cy)]
    top_cmtes = []
    for (sid, snam), (s, o, n) in sorted(cand_by_cmte[(cid, cy)].items(),
                                         key=lambda kv: -(kv[1][0] + kv[1][1]))[:5]:
        top_cmtes.append({'committee_id': sid, 'committee_name': snam,
                          'support': r2(s), 'oppose': r2(o), 'total': r2(s + o), 'rows': n})
    per_candidate.append({
        'candidate_id': cid,
        'candidate_name': name,
        'office': office,
        'state': state,
        'district': district,
        'cycle': cy,
        'all_ie_support': r2(t['support']),
        'all_ie_oppose': r2(t['oppose']),
        'all_ie_total': r2(t['support'] + t['oppose'] + t['no_direction']),
        'no_direction_amount': r2(t['no_direction']),
        'rows': t['rows'],
        'is_roster': cid in id_to_person,
        'person_key': id_to_person.get(cid),
        'top_committees': top_cmtes,
    })
per_candidate.sort(key=lambda e: (e['cycle'], -e['all_ie_total']))
print(f'per-candidate entries: {len(per_candidate)} '
      f'({sum(1 for e in per_candidate if e["is_roster"])} roster candidate-ids)')

# ---------- 5. Per-cycle summaries + roster totals + top committees ----------
def _tot(rows):
    return (r2(sum(x['amount'] for x in rows if x['sup_opp'] == 'S')),
            r2(sum(x['amount'] for x in rows if x['sup_opp'] == 'O')),
            r2(sum(x['amount'] for x in rows)))

summaries = {}
for yr in CYCLES:
    inc = [x for x in all_rows if x.get('included') and x['cycle'] == yr]
    ros = [x for x in inc if x['cand_id'] in id_to_person]
    s_all, o_all, t_all = _tot(inc)
    s_ros, o_ros, t_ros = _tot(ros)
    sen = r2(sum(x['amount'] for x in ros if x['office'] == 'S'))
    hou = r2(sum(x['amount'] for x in ros if x['office'] == 'H'))
    other = r2(t_ros - sen - hou)

    def top_cmte(rows, n=10):
        byc = collections.defaultdict(lambda: [0.0, 0.0, ''])
        for x in rows:
            c = byc[x['spe_id']]
            c[2] = x['spe_nam']
            if x['sup_opp'] == 'S':
                c[0] += x['amount']
            elif x['sup_opp'] == 'O':
                c[1] += x['amount']
        out = []
        for sid, (s, o, nm) in sorted(byc.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:n]:
            out.append({'committee_id': sid, 'committee_name': nm,
                        'support': r2(s), 'oppose': r2(o), 'total': r2(s + o)})
        return out

    summaries[yr] = {
        'all_candidates': {'support': s_all, 'oppose': o_all, 'total': t_all,
                           'n_candidates': len({x['cand_id'] for x in inc}),
                           'n_rows': len(inc)},
        'roster_targeted': {'support': s_ros, 'oppose': o_ros, 'total': t_ros,
                            'n_persons_with_spending': len({id_to_person[x['cand_id']] for x in ros}),
                            'senate': sen, 'house': hou, 'other_or_blank_office': other},
        'top_committees_roster_targeted': top_cmte(ros),
        'top_committees_all_candidates': top_cmte(inc),
    }
    print(f"{yr} roster: S ${s_ros:,.2f} / O ${o_ros:,.2f} / total ${t_ros:,.2f} "
          f"(Sen ${sen:,.2f}, House ${hou:,.2f}); all candidates total ${t_all:,.2f}")

# ---------- 6. ROSTER JOIN (separate step — kept apart from the
#     all-candidates aggregation above so the per-candidate output stays
#     reusable for a later all-candidates expansion). ----------
#     Person career = sum over their FEC IDs over the covered cycles
#     (2022+2024+2026). Persons with no FEC IDs get unknown (None), not 0.
per_person = {}   # person_key -> {support, oppose, total, by_cycle}
for p in roster:
    pk = p['person_key']
    # Dedupe defensively: roster.json lists H4MI08218 twice for
    # Kristen McDonald Rivet; without this her totals double-count it.
    ids = list(dict.fromkeys(p.get('fec_candidate_ids') or []))
    if not ids:
        per_person[pk] = None
        continue
    by_cycle = {}
    s_career = o_career = t_career = 0.0
    for yr in CYCLES:
        s = sum(t['support'] for (cid, cy), t in cand_tot.items() if cy == yr and cid in ids)
        o = sum(t['oppose'] for (cid, cy), t in cand_tot.items() if cy == yr and cid in ids)
        nd = sum(t['no_direction'] for (cid, cy), t in cand_tot.items() if cy == yr and cid in ids)
        by_cycle[yr] = {'support': r2(s), 'oppose': r2(o), 'total': r2(s + o + nd)}
        s_career += s
        o_career += o
        t_career += s + o + nd
    per_person[pk] = {'support': r2(s_career), 'oppose': r2(o_career),
                      'total': r2(t_career), 'by_cycle': by_cycle}

out_rows = []
for p in roster:
    pk = p['person_key']
    ids = list(dict.fromkeys(p.get('fec_candidate_ids') or []))
    v = per_person[pk]
    if v is None:
        out_rows.append({'person_key': pk, 'full_name': p['full_name'],
                         'fec_candidate_ids': '',
                         'all_ie_support_career': '', 'all_ie_oppose_career': '',
                         'all_ie_total_career': '',
                         'all_ie_support_2026': '', 'all_ie_oppose_2026': '',
                         'all_ie_total_2026': '',
                         'data_notes': 'No FEC candidate ID on file; not searchable in IE data.'})
        continue
    c26 = v['by_cycle'][CURRENT]
    note = ''
    if v['total'] == 0:
        note = 'No all-IE spending found in 2022/2024/2026 IE files.'
    out_rows.append({'person_key': pk, 'full_name': p['full_name'],
                     'fec_candidate_ids': ';'.join(ids),
                     'all_ie_support_career': f"{v['support']:.2f}",
                     'all_ie_oppose_career': f"{v['oppose']:.2f}",
                     'all_ie_total_career': f"{v['total']:.2f}",
                     'all_ie_support_2026': f"{c26['support']:.2f}",
                     'all_ie_oppose_2026': f"{c26['oppose']:.2f}",
                     'all_ie_total_2026': f"{c26['total']:.2f}",
                     'data_notes': note})

# ---------- 6b. Top 5 committees per person (career) ----------
# Aggregate cand_by_cmte across the person's candidate IDs and the
# covered cycles (2022+2024+2026). Grouped by committee_id: the same
# committee sometimes files under different name casings
# (e.g. 'ROLLING SEA ACTION FUND' vs 'Rolling Sea Action Fund'), so the
# name carried is the one attached to that committee's largest single
# (candidate, cycle) total. Merged into the dataset JSON by
# merge_dataset.py (JSON only, not the CSV). Persons with no FEC IDs
# get null (unknown, not zero); persons with IDs but no spending get [].
top_by_person = {}
for p in roster:
    pk = p['person_key']
    ids = list(dict.fromkeys(p.get('fec_candidate_ids') or []))
    if not ids:
        top_by_person[pk] = None
        continue
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0, '', 0.0])
    for (cid, cy), by_cmte in cand_by_cmte.items():
        if cid not in ids:
            continue
        for (sid, snam), (s, o, n) in by_cmte.items():
            a = agg[sid]
            a[0] += s
            a[1] += o
            a[2] += n
            # Name from the largest single (candidate, cycle) total.
            if s + o > a[4]:
                a[3] = snam
                a[4] = s + o
    ranked = sorted(agg.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:5]
    top_by_person[pk] = [{'committee_id': sid, 'committee_name': a[3],
                          'support': r2(a[0]), 'oppose': r2(a[1]),
                          'total': r2(a[0] + a[1]), 'rows': a[2]}
                         for sid, a in ranked]
with open(f"{IM}/all_ie_top_committees.json", 'w') as f:
    json.dump(top_by_person, f, indent=1)
print(f"wrote data/intermediate/all_ie_top_committees.json "
      f"({sum(1 for v in top_by_person.values() if v)} persons with spending, "
      f"{sum(1 for v in top_by_person.values() if v is None)} unknown)")

with open(f"{IM}/all_ie.csv", 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['person_key', 'full_name', 'fec_candidate_ids',
                                      'all_ie_support_career', 'all_ie_oppose_career',
                                      'all_ie_total_career', 'all_ie_support_2026',
                                      'all_ie_oppose_2026', 'all_ie_total_2026',
                                      'data_notes'])
    w.writeheader()
    w.writerows(out_rows)
print(f"wrote data/intermediate/all_ie.csv ({len(out_rows)} rows, roster order)")

# ---------- 7. Validation report (printed + saved in the JSON) ----------
validation = {'udp_2024_exact': {}, 'roster_totals': {}, 'top_spenders_2026': {},
              'senate_house_2026': {}, 'support_oppose_2026': {}}
validation['udp_2024_exact'] = {
    'computed': udp_totals[2024], 'expected': prior[2024],
    'diff': r2(udp_totals[2024] - prior[2024]), 'status': 'exact' if abs(udp_totals[2024] - prior[2024]) < 0.005 else 'MISMATCH'}
for yr in CYCLES:
    got = summaries[yr]['roster_targeted']['total']
    exp = EXPECTED_ROSTER_TOTAL[yr]
    validation['roster_totals'][yr] = {
        'computed': got, 'expected': exp, 'diff': r2(got - exp),
        'diff_pct': round(100 * (got - exp) / exp, 2),
        'support': summaries[yr]['roster_targeted']['support'],
        'oppose': summaries[yr]['roster_targeted']['oppose'],
        'status': 'within_1pct' if abs(got - exp) / exp < 0.01 else 'CHECK'}
    print(f"VALIDATION roster {yr}: computed ${got:,.2f} vs brief ${exp:,.0f} "
          f"diff ${got - exp:,.2f} ({100 * (got - exp) / exp:+.2f}%)")

# Top-2026 non-UDP roster-targeted spenders, matched by committee name.
top_ros_2026 = summaries[2026]['top_committees_roster_targeted']
for want_name, direction, exp in EXPECTED_TOP_2026:
    hit = None
    for c in top_ros_2026:
        nm = c['committee_name'].upper()
        if want_name in nm or (want_name == 'HOUSE MAJORITY PAC' and nm == 'HMP'):
            hit = c
            break
    if hit is None:
        validation['top_spenders_2026'][want_name] = {'status': 'NOT FOUND in top 10'}
        print(f"VALIDATION top-2026 {want_name}: NOT FOUND in roster top 10")
        continue
    got = hit['support'] if direction == 'S' else hit['oppose']
    validation['top_spenders_2026'][want_name] = {
        'committee_id': hit['committee_id'], 'committee_name': hit['committee_name'],
        'direction': direction, 'computed': got, 'expected': exp,
        'diff': r2(got - exp), 'status': 'match' if abs(got - exp) / exp < 0.005 else 'CHECK'}
    print(f"VALIDATION top-2026 {hit['committee_name']} ({direction}): "
          f"${got:,.2f} vs brief ${exp:,.0f} diff ${got - exp:,.2f}")

sen, hou = EXPECTED_SENATE_HOUSE_2026
got_sen = summaries[2026]['roster_targeted']['senate']
got_hou = summaries[2026]['roster_targeted']['house']
validation['senate_house_2026'] = {
    'senate': {'computed': got_sen, 'expected': sen, 'diff': r2(got_sen - sen)},
    'house': {'computed': got_hou, 'expected': hou, 'diff': r2(got_hou - hou)}}
print(f"VALIDATION 2026 Senate ${got_sen:,.2f} vs ${sen:,.0f} (diff ${got_sen - sen:,.2f}); "
      f"House ${got_hou:,.2f} vs ${hou:,.0f} (diff ${got_hou - hou:,.2f})")
exp_s, exp_o = EXPECTED_SO_2026
got_s = summaries[2026]['roster_targeted']['support']
got_o = summaries[2026]['roster_targeted']['oppose']
validation['support_oppose_2026'] = {
    'support': {'computed': got_s, 'expected': exp_s, 'diff': r2(got_s - exp_s)},
    'oppose': {'computed': got_o, 'expected': exp_o, 'diff': r2(got_o - exp_o)}}
print(f"VALIDATION 2026 S/O: support ${got_s:,.2f} vs ${exp_s:,.0f}; "
      f"oppose ${got_o:,.2f} vs ${exp_o:,.0f}")

# Bogus-example accounting (spot-check that the named filings are excluded).
bogus = {}
for yr, spe, cand, amt_label in [
        (2022, 'C00800508', 'H2NY05118', 'Committee of 300 / Akhlaghy 2022'),
        (2024, 'C00874586', 'P40007304', 'Committee of 300 / Akhlaghy 2024'),
        (2024, 'C00785352', 'P40019226', 'Nader Akhlaghy committee 2024'),
        (2026, 'C00946087', '', 'Warren Buffet / Bettis 2026 (blank cand)'),
        (2026, 'C00944025', '', 'TANKING / APPLE INC DJIA / Bettis 2026 (blank cand)')]:
    rows_hit = [x for x in all_rows if x['cycle'] == yr and x['spe_id'] == spe
                and (not cand or x['cand_id'] == cand)]
    bogus[amt_label] = {
        'committee_id': spe, 'candidate_id': cand or '(blank)',
        'rows_in_file_after_dedup': len(rows_hit),
        'amount_in_file_after_dedup': r2(sum(x['amount'] for x in rows_hit)),
        'amount_included': r2(sum(x['amount'] for x in rows_hit if x.get('included'))),
        'excluded_because': 'unregistered committee (not in same-cycle cm.txt)'
                             + ('' if cand else '; candidate ID blank'),
    }
    print(f"BOGUS {amt_label}: {len(rows_hit)} deduped rows, "
          f"${sum(x['amount'] for x in rows_hit):,.2f} in file, "
          f"${sum(x['amount'] for x in rows_hit if x.get('included')):,.2f} included")

# Roster data finding: two roster entries can share one FEC ID
# (Kristen McDonald Rivet appears as both M001237 and
# kristen-mcdonaldrivetmihouse, both with H4MI08218). Per-row CSV
# values are correct for each roster entry, but a sum across roster
# rows double-counts the shared ID. Record the overcount and the
# distinct-person totals alongside the row-sum totals.
id_to_person_keys = collections.defaultdict(set)
for p in roster:
    for cid in list(dict.fromkeys(p.get('fec_candidate_ids') or [])):
        id_to_person_keys[cid].add(p['person_key'])
dup_entries = []
over_s = over_o = over_t = 0.0
for cid, pks in sorted(id_to_person_keys.items()):
    if len(pks) > 1:
        s = sum(t['support'] for (c2, cy), t in cand_tot.items() if c2 == cid)
        o = sum(t['oppose'] for (c2, cy), t in cand_tot.items() if c2 == cid)
        nd = sum(t['no_direction'] for (c2, cy), t in cand_tot.items() if c2 == cid)
        over_s += (len(pks) - 1) * s
        over_o += (len(pks) - 1) * o
        over_t += (len(pks) - 1) * (s + o + nd)
        dup_entries.append({
            'candidate_id': cid,
            'person_keys': sorted(pks),
            'full_names': sorted({person_by_key[pk]['full_name'] for pk in pks}),
            'shared_id_career_total': r2(s + o + nd),
            'overcounted_in_row_sums': r2((len(pks) - 1) * (s + o + nd)),
        })
        print(f"ROSTER DUP: {cid} shared by {sorted(pks)}; "
              f"row-sum totals overcount by ${over_t:,.2f} career")
row_sum_s = r2(sum(v['support'] for v in per_person.values() if v))
row_sum_o = r2(sum(v['oppose'] for v in per_person.values() if v))
row_sum_t = r2(sum(v['total'] for v in per_person.values() if v))

out = {
    'meta': {
        'script': 'src/ingest/pull_all_ie.py',
        'data_as_of': DATA_AS_OF,
        'cycles': list(CYCLES),
        'current_cycle': CURRENT,
        'note': 'Career totals cover the staged IE cycles (2022+2024+2026) ONLY. '
                'No IE files are staged for earlier cycles; these are not full-career totals. '
                'All-IE columns are separate from total_accepted and are never blended into it.',
        'filter_rules': [
            'dedup by (spe_id, tran_id): keep latest receipt_dat, tie-break highest file_num; '
            'blank tran_id never deduped against another row',
            'registered committee only: spe_id in same-cycle data/raw/cm/<cycle>/cm.txt',
            'identified candidate only: non-blank cand_id in any staged weball file (1980-2026) '
            'OR a roster FEC candidate ID; blank cand_id rows excluded from published totals',
            'support and oppose summed separately, never netted; blank sup_opp rows count in total only',
        ],
        'form_type_double_count_check': {
            'bulk_file_has_form_type_column': any(
                exclusions[yr]['has_form_type_column'] for yr in CYCLES),
            'finding': 'No form-type column exists in the bulk IE files, so F24/F3X cannot be '
                       'separated by form. The bulk file carries ONE copy per expenditure (the '
                       'notice copy; pull-log-b §7 verified file_num/image_num match the F24 '
                       'filing), and (spe_id, tran_id) dedup removes any same-transaction repeat. '
                       'Proof: UDP 2024 deduped S+O reproduces the tracker total $38,044,932.69 '
                       'to the cent — a file that double-counted across form types would be ~2x. '
                       'Near-duplicate rows (same committee/candidate/date/amount/direction, '
                       'different tran_id AND different image_num = different filings) are '
                       'treated as separate expenditures and quantified per cycle in exclusions[].',
        },
        'coverage': {
            'staged_cycles': list(CYCLES),
            'earlier_cycles_available': 'Per the FEC independent-expenditures file description '
                '(fetched Nov 12, 2026), historical data is available beginning with the 2010 '
                'cycle, and the FEC bulk-data index publishes independent_expenditure_YYYY.csv '
                'per cycle. Files for 2010/2012/2014/2016/2018/2020 exist and are NOT staged '
                'here (each ~14-19 MB, same format) — expanding to them is a follow-up, not '
                'done in this pull. Pre-2010 cycles have no such file.',
            'files_not_staged': [2010, 2012, 2014, 2016, 2018, 2020],
        },
    },
    'exclusions_by_cycle': {str(yr): exclusions[yr] for yr in CYCLES},
    'blank_attribution_diagnostic': {str(yr): blank_diag[yr] for yr in CYCLES},
    'name_index_collisions': name_collisions,
    'per_cycle_summaries': {str(yr): summaries[yr] for yr in CYCLES},
    'per_candidate_per_cycle': per_candidate,
    'validation': validation,
    'bogus_examples': bogus,
    'roster_career_totals': {
        # Row sums (one row per roster entry; see duplicate_roster_entries).
        'support': row_sum_s,
        'oppose': row_sum_o,
        'total': row_sum_t,
        'n_persons_with_spending': sum(1 for v in per_person.values() if v and v['total'] != 0),
        'n_persons_unknown_no_fec_id': sum(1 for v in per_person.values() if v is None),
        'duplicate_roster_entries': dup_entries,
        # Distinct-person totals: row sums minus the shared-ID overcount.
        'distinct_person_totals': {
            'support': r2(row_sum_s - over_s),
            'oppose': r2(row_sum_o - over_o),
            'total': r2(row_sum_t - over_t)},
    },
}
with open(f'{IM}/all_ie_per_cycle.json', 'w') as f:
    json.dump(out, f, indent=1)
print(f"wrote data/intermediate/all_ie_per_cycle.json ({len(per_candidate)} per-candidate entries)")
print(f"roster career all-IE (2022+2024+2026): S ${out['roster_career_totals']['support']:,.2f} / "
      f"O ${out['roster_career_totals']['oppose']:,.2f} / total "
      f"${out['roster_career_totals']['total']:,.2f}; "
      f"{out['roster_career_totals']['n_persons_with_spending']} persons with spending, "
      f"{out['roster_career_totals']['n_persons_unknown_no_fec_id']} unknown (no FEC ID); "
      f"distinct-person total ${out['roster_career_totals']['distinct_person_totals']['total']:,.2f} "
      f"(row sums double-count shared IDs — see duplicate_roster_entries)")

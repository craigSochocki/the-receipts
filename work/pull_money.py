#!/usr/bin/env python3
"""Congress money tracker — career money pull from FEC bulk files (pas2 + weball + cm).

Rules (see pull-log-a.md for evidence):
- Individual: weball TTL_INDIV_CONTRIB (col 18, 1-indexed), summed per CAND_ID per cycle.
- AIPAC PAC direct: pas2 rows CMTE_ID=<config committees.aipac_pac>, TRANSACTION_TP in (24K,24P).
  24Z in-kind rows excluded per spec (2 rows / $5,000 in 2024 only).
- Corporate PAC: pas2 rows TRANSACTION_TP in (24K,24P) where the contributing
  committee (same-cycle cm join) has CMTE_TP in (Q,N) and ORG_TP in (C,W).
- Dedup (per cycle file): key (CMTE_ID, TRAN_ID, CAND_ID, TRANSACTION_AMT,
  TRANSACTION_DT, RPT_YR); prefer non-memo row, tie-break latest FILE_NUM.
  TRAN_ID alone is NOT a safe key: some filers reuse line-number-style TRAN_IDs
  (e.g. 'SB23.2000') across distinct contributions in different reports.
- Exclusion: rows whose MEMO_TEXT contains 'EARMARK' (or starts 'ERMK:') AND whose
  amount is NEGATIVE are dropped. These are voided/refunded conduit earmarks
  (individual donors' money being returned); the original earmark transmissions
  are NOT in pas2 (verified: Cantwell S8WA00194 has 31 such voids, $0 positives,
  in any cycle), so netting them creates phantom negatives. Zero such rows
  exist among corporate-matched rows with the narrow wording; the broad
  'EARMARK'+negative rule catches 5 corporate rows (-$2,891, all cycles).
  Generic 'VOIDED CHECK' rows are NOT excluded: those void PAC-treasury
  contributions whose originals ARE in pas2, so they net correctly.
- Earmark breakout: POSITIVE rows whose memo text indicates an earmark
  transmission ('EARMARK OF <donor>' / 'ERMK: <donor>') are individual donors'
  money passed through by the committee, NOT the committee's own funds. They
  are kept in the primary column per the task spec (and OpenSecrets counts
  them the same way), but are ALSO broken out into separate
  *_earmark_transmitted_career columns so the committee's own money is
  recoverable as primary minus earmark. They are also already inside the
  candidate's individual-contribution total (weball), i.e. double-counted
  across the tracker's own columns if the two are added. Scale: AIPAC
  positives $500 (2022), $0 (2024), $180,663 (2026, mostly a Dec-2025
  amended year-end filing); e.g. Gottheimer 2026: $65,730 earmark vs $10,000
  own-money (the $5,000/election cap).
- Negative amounts otherwise INCLUDED (refunds/voids of PAC money net out).
- All amounts summed as integer cents; output in dollars with 2 decimals.
"""
import json, csv, os
from decimal import Decimal
from collections import defaultdict

from config import load_config

CFG = load_config()
ROOT = CFG['_root']
WORK = str(ROOT / CFG['paths']['work'])
BULK = str(ROOT / CFG['paths']['bulk'])
CYCLES = list(range(CFG['cycles']['career_start'], CFG['cycles']['career_end'] + 1, 2))
CURRENT_CYCLE = CFG['cycles']['current']
AIPAC = CFG['committees']['aipac_pac']

def cents(s):
    s = (s or '').strip()
    if not s:
        return 0
    return int((Decimal(s) * 100).to_integral_value())

def fmt(c):
    return f"{c/100:.2f}"

roster = json.load(open(os.path.join(WORK, 'roster.json')))
cand_to_persons = defaultdict(list)
for p in roster:
    for cid in (p.get('fec_candidate_ids') or []):
        cand_to_persons[cid].append(p['person_key'])
roster_cands = set(cand_to_persons)
persons = {p['person_key']: p for p in roster}

# per-(cand, cycle) accumulators
indiv = defaultdict(int)    # (cand, cycle) -> cents
aipac = defaultdict(int)
corp = defaultdict(int)
aipac_earmark = defaultdict(int)
corp_earmark = defaultdict(int)
had_weball = set()          # cand ids with >=1 weball row
had_pas2 = set()            # cand ids with >=1 matched pas2 row (any TP in 24K/24P)
per_cycle_diag = []

# ---------------- weball ----------------
for cy in CYCLES:
    yy = f"{cy % 100:02d}"
    path = os.path.join(BULK, 'weball', f'weball{yy}.txt')
    rows = matched = bad = 0
    cvg_max = ''
    with open(path) as f:
        for line in f:
            rows += 1
            p = line.rstrip('\n').split('|')
            if len(p) != 30:
                bad += 1
                continue
            cid = p[0]
            if cid in roster_cands:
                matched += 1
                had_weball.add(cid)
                indiv[(cid, cy)] += cents(p[17])
            if cy == CURRENT_CYCLE and len(p) > 27 and p[27] > cvg_max:
                cvg_max = p[27]
    per_cycle_diag.append({'cycle': cy, 'weball_rows': rows, 'weball_matched': matched,
                           'weball_bad_fields': bad, f'weball_{CURRENT_CYCLE}_max_cvg_end': cvg_max if cy == CURRENT_CYCLE else ''})

# ---------------- pas2 + cm ----------------
for cy in CYCLES:
    # committee master -> corporate PAC set
    corp_set = set()
    cm_rows = cm_bad = cm_blank_org = 0
    with open(os.path.join(BULK, 'cm', str(cy), 'cm.txt')) as f:
        for line in f:
            cm_rows += 1
            p = line.rstrip('\n').split('|')
            if len(p) != 15:
                cm_bad += 1
                continue
            if not p[12]:
                cm_blank_org += 1
            if p[9] in ('Q', 'N') and p[12] in ('C', 'W'):
                corp_set.add(p[0])
    # pas2
    path = os.path.join(BULK, 'pas2', str(cy), 'itpas2.txt')
    rows = bad = matched = 0
    dedup = {}   # (cmte, tran_id, cand, amt, dt, rpt_yr) -> (memo_flag, file_num, amount_cents, kind, is_earmark)
    dedup_dropped_n = 0
    dedup_dropped_c = 0
    void_earmark_n = 0
    void_earmark_c = 0
    naive_aipac_c = 0
    naive_corp_c = 0
    earmark_aipac_c = 0
    earmark_corp_c = 0
    neg_n = neg_c = 0
    aipac_rows = aipac_c = 0
    corp_rows = corp_c = 0
    with open(path) as f:
        for line in f:
            rows += 1
            p = line.rstrip('\n').split('|')
            if len(p) != 22:
                bad += 1
                continue
            tp = p[5]
            if tp not in ('24K', '24P'):
                continue
            cand = p[16]
            if cand not in roster_cands:
                continue
            matched += 1
            had_pas2.add(cand)
            cmte = p[0]
            amt = cents(p[14])
            if amt < 0:
                neg_n += 1
                neg_c += amt
            memo_text = p[20] or ''
            is_earmark = ('EARMARK' in memo_text) or memo_text.startswith('ERMK:')
            if is_earmark and amt < 0:
                void_earmark_n += 1
                void_earmark_c += amt
                continue  # conduit-earmark void; originals not in pas2 (see header)
            kind = None
            if cmte == AIPAC:
                kind = 'aipac'
            elif cmte in corp_set:
                kind = 'corp'
            else:
                continue  # not AIPAC and not corporate: not counted in any column
            if kind == 'aipac':
                naive_aipac_c += amt
            else:
                naive_corp_c += amt
            tran = p[17] or p[21]  # TRAN_ID, fallback SUB_ID
            try:
                filenum = int(p[18] or 0)
            except ValueError:
                filenum = 0
            memo = 1 if p[19] == 'X' else 0
            key = (cmte, tran, cand, amt, p[13], p[3])
            prev = dedup.get(key)
            if prev is None:
                dedup[key] = (memo, filenum, amt, kind, is_earmark)
            else:
                # prefer non-memo; tie-break latest FILE_NUM
                if (memo, filenum) < (prev[0], prev[1]):
                    dedup[key] = (memo, filenum, amt, kind, is_earmark)
                    dedup_dropped_n += 1
                    dedup_dropped_c += prev[2]
                else:
                    dedup_dropped_n += 1
                    dedup_dropped_c += amt
    # second pass over dedup dict with keys
    for (cmte, tran, cand, amt0, dt, rptyr), (memo, filenum, amt, kind, is_earmark) in dedup.items():
        if kind == 'aipac':
            aipac[(cand, cy)] += amt
            aipac_rows += 1
            aipac_c += amt
            if is_earmark:
                aipac_earmark[(cand, cy)] += amt
                earmark_aipac_c += amt
        else:
            corp[(cand, cy)] += amt
            corp_rows += 1
            corp_c += amt
            if is_earmark:
                corp_earmark[(cand, cy)] += amt
                earmark_corp_c += amt
    # committees in pas2 matched rows missing from this cycle's cm (recompute cheaply)
    # NOTE: skipped here — cm coverage measured separately below
    d = per_cycle_diag[(cy - CFG['cycles']['career_start'])//2]
    d.update({'cm_rows': cm_rows, 'cm_bad_fields': cm_bad, 'cm_blank_org_tp': cm_blank_org,
              'corp_pacs': len(corp_set), 'pas2_rows': rows, 'pas2_bad_fields': bad,
              'pas2_matched_roster': matched, 'pas2_neg_rows': neg_n, 'pas2_neg_cents': neg_c,
              'dedup_dropped_rows': dedup_dropped_n, 'dedup_dropped_cents': dedup_dropped_c,
              'void_earmark_rows': void_earmark_n, 'void_earmark_cents': void_earmark_c,
              'earmark_aipac_cents': earmark_aipac_c, 'earmark_corp_cents': earmark_corp_c,
              'naive_aipac_cents': naive_aipac_c, 'naive_corp_cents': naive_corp_c,
              'aipac_rows_kept': aipac_rows, 'aipac_cents': aipac_c,
              'corp_rows_kept': corp_rows, 'corp_cents': corp_c})

# committees in matched pas2 rows missing from same-cycle cm (classification coverage)
cm_ids = {}
for cy in CYCLES:
    s = set()
    with open(os.path.join(BULK, 'cm', str(cy), 'cm.txt')) as f:
        for line in f:
            p = line.rstrip('\n').split('|')
            if len(p) == 15:
                s.add(p[0])
    cm_ids[cy] = s
missing_stats = {}
for cy in CYCLES:
    miss = set()
    miss_rows = 0
    with open(os.path.join(BULK, 'pas2', str(cy), 'itpas2.txt')) as f:
        for line in f:
            p = line.rstrip('\n').split('|')
            if len(p) != 22 or p[5] not in ('24K', '24P') or p[16] not in roster_cands:
                continue
            if p[0] not in cm_ids[cy]:
                miss.add(p[0])
                miss_rows += 1
    missing_stats[cy] = {'cm_missing_committees': len(miss), 'cm_missing_rows': miss_rows,
                         'cm_missing_ids': sorted(miss)[:20]}

# ---------------- aggregate to persons ----------------
def person_total(acc, p):
    return sum(acc.get((cid, cy), 0) for cid in (p.get('fec_candidate_ids') or []) for cy in CYCLES)

out_rows = []
per_cycle = {}
for p in roster:
    pk = p['person_key']
    ids = p.get('fec_candidate_ids') or []
    it = person_total(indiv, p)
    at = person_total(aipac, p)
    ct = person_total(corp, p)
    ae = person_total(aipac_earmark, p)
    ce = person_total(corp_earmark, p)
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster')
    else:
        any_row = any(cid in had_weball or cid in had_pas2 for cid in ids)
        if not any_row:
            notes.append('no FEC activity found')
        elif it == 0 and at == 0 and ct == 0:
            notes.append('FEC activity found; all totals zero')
    dup = [q for cid in ids for q in cand_to_persons[cid] if q != pk]
    if dup:
        notes.append('duplicate roster entry: FEC ID shared with ' + ', '.join(sorted(set(dup))))
    if at < 0:
        notes.append('net-negative AIPAC total (voids exceed direct contributions)')
    out_rows.append({'person_key': pk, 'full_name': p['full_name'],
                     'fec_candidate_ids': ';'.join(ids),
                     'individual_contribution_total_career': fmt(it),
                     'aipac_pac_direct_career': fmt(at),
                     'aipac_earmark_transmitted_career': fmt(ae),
                     'corporate_pac_career': fmt(ct),
                     'corporate_earmark_transmitted_career': fmt(ce),
                     'data_notes': ' | '.join(notes)})
    # per-cycle breakdown (per candidate id)
    entries = []
    for cy in CYCLES:
        for cid in ids:
            i = indiv.get((cid, cy), 0)
            a = aipac.get((cid, cy), 0)
            c = corp.get((cid, cy), 0)
            aem = aipac_earmark.get((cid, cy), 0)
            cem = corp_earmark.get((cid, cy), 0)
            if i or a or c or aem or cem:
                entries.append({'cycle': cy, 'candidate_id': cid,
                                'individual': fmt(i), 'aipac_pac_direct': fmt(a),
                                'aipac_earmark_transmitted': fmt(aem),
                                'corporate_pac': fmt(c),
                                'corporate_earmark_transmitted': fmt(cem)})
    per_cycle[pk] = {'person_key': pk, 'full_name': p['full_name'], 'per_cycle': entries}

with open(os.path.join(WORK, 'money_pas2_weball.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['person_key', 'full_name', 'fec_candidate_ids',
        'individual_contribution_total_career', 'aipac_pac_direct_career',
        'aipac_earmark_transmitted_career', 'corporate_pac_career',
        'corporate_earmark_transmitted_career', 'data_notes'])
    w.writeheader()
    w.writerows(out_rows)

with open(os.path.join(WORK, 'money_per_cycle.json'), 'w') as f:
    json.dump(per_cycle, f, indent=1)

# coverage counts
n_any_indiv = sum(1 for r in out_rows if float(r['individual_contribution_total_career']) != 0)
n_any_aipac = sum(1 for r in out_rows if float(r['aipac_pac_direct_career']) != 0)
n_any_corp = sum(1 for r in out_rows if float(r['corporate_pac_career']) != 0)
n_any = sum(1 for r in out_rows if float(r['individual_contribution_total_career']) != 0
            or float(r['aipac_pac_direct_career']) != 0 or float(r['corporate_pac_career']) != 0)
n_zero = sum(1 for r in out_rows if 'no FEC activity found' in r['data_notes'])
n_noids = sum(1 for r in out_rows if 'no FEC candidate IDs' in r['data_notes'])
n_allzero = sum(1 for r in out_rows if 'all totals zero' in r['data_notes'])
tot_indiv = sum(int(Decimal(r['individual_contribution_total_career']) * 100) for r in out_rows)
tot_aipac = sum(int(Decimal(r['aipac_pac_direct_career']) * 100) for r in out_rows)
tot_corp = sum(int(Decimal(r['corporate_pac_career']) * 100) for r in out_rows)
print('persons:', len(out_rows))
print('any individual != 0:', n_any_indiv)
print('any aipac != 0:', n_any_aipac)
print('any corporate != 0:', n_any_corp)
print('any of the three != 0:', n_any)
print('no FEC activity found:', n_zero)
print('no FEC IDs:', n_noids)
print('activity found, all totals zero:', n_allzero)
print('TOTAL individual career $:', fmt(tot_indiv))
print('TOTAL aipac career $:', fmt(tot_aipac))
print('TOTAL aipac earmark transmitted $:', fmt(sum(int(Decimal(r['aipac_earmark_transmitted_career']) * 100) for r in out_rows)))
print('TOTAL corporate career $:', fmt(tot_corp))
print('TOTAL corporate earmark transmitted $:', fmt(sum(int(Decimal(r['corporate_earmark_transmitted_career']) * 100) for r in out_rows)))
print('TOTAL dedup dropped rows:', sum(d['dedup_dropped_rows'] for d in per_cycle_diag),
      'cents:', sum(d['dedup_dropped_cents'] for d in per_cycle_diag))
print('TOTAL VOID-earmark rows excluded:', sum(d['void_earmark_rows'] for d in per_cycle_diag),
      'cents:', sum(d['void_earmark_cents'] for d in per_cycle_diag))
print('TOTAL naive aipac (VOID-earmark excluded, no dedup) $:', fmt(sum(d['naive_aipac_cents'] for d in per_cycle_diag)))
print('TOTAL naive corp (no dedup) $:', fmt(sum(d['naive_corp_cents'] for d in per_cycle_diag)))
print('TOTAL pas2 neg rows (matched):', sum(d['pas2_neg_rows'] for d in per_cycle_diag),
      'neg cents:', sum(d['pas2_neg_cents'] for d in per_cycle_diag))
print('TOTAL weball matched rows:', sum(d['weball_matched'] for d in per_cycle_diag))
print('TOTAL pas2 matched rows:', sum(d['pas2_matched_roster'] for d in per_cycle_diag))
print('TOTAL corp rows kept:', sum(d['corp_rows_kept'] for d in per_cycle_diag))
print('TOTAL aipac rows kept:', sum(d['aipac_rows_kept'] for d in per_cycle_diag))
json.dump({'per_cycle': per_cycle_diag, 'cm_missing': missing_stats},
          open(os.path.join(WORK, 'pull-diagnostics.json'), 'w'), indent=1)
print(f'{CURRENT_CYCLE} max CVG_END_DT:', [d.get(f'weball_{CURRENT_CYCLE}_max_cvg_end') for d in per_cycle_diag if d['cycle'] == CURRENT_CYCLE])

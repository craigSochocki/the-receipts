#!/usr/bin/env python3
"""Standing audits for the Congress money tracker dataset.

Usage:
    python3 src/validate/verify_dataset.py [--dataset-csv PATH] [--dataset-json PATH]

Checks (exit non-zero on any mismatch, printing every failure):
  (a) per-cycle sums reproduce every career column (0 mismatches).
  (b) roster totals match config verification.methodology_totals to the
      cent (Armstrong's "unknown" money excluded from every sum).
  (c) all twelve rank columns recompute exactly (competition ranking:
      rank = 1 + count of strictly greater values).
  (d) clean counts match config verification.clean_2026 (True 81 /
      False 579 / None 4; 120th House clean 64 — 61 D, 3 R;
      career-clean 120th House 53 — 50 D, 3 R; 2026-clean but not
      career-clean 11).
  (e) the twenty 2026 columns, the clean rule, and dep_share
      recompute exactly (including the Luria unverified case, the
      generalized linkage rule, the unopposed_2026 flag recomputed
      from weball26, the unopposed nulling of would-be-clean verdicts,
      and the int/float split on empty 2026 sums).
  (f) the opposition career columns recompute from
      opposition-computed.json.
  (g) dedup audit: the dropped per-cycle entries in dedup-applied.json
      are '0.00' in money_per_cycle.json, and the kept entries equal
      the recorded amounts.
  (h) CSV and JSON agree field by field (664 rows, same person_keys,
      same values — CSV floats compare by float value, clean_2026 by
      True/False/empty, dep_share by float value; the per-cycle lists
      compare by repr; all_ie_top_committees is JSON-only and skipped).
  (i) 664 rows, unique person_keys, row order matches roster.json.
  (j) self-funding / topline: per-cycle sums reproduce every new
      career column (flows summed; cash on hand and debts owed by are
      the latest cycle's values); named spot cases (Constantino
      $17,000,000.00 exactly, Scott $89,994,251.12, …); debts owed to
      is null everywhere; Armstrong unknown, not zero.
  (k) other committees: per-cycle sums reproduce every class, earmark
      and total column; the corporate/AIPAC re-derivation in
      other_committees_diagnostics.json matches methodology to the
      cent; Lamb 2026 pas2-derived $96,500 with the $32,650 residual
      recorded.
  (l) all-IE: UDP 2024 deduped S+O is exactly $38,044,932.69; roster
      cycle totals match config all_ie_cycle_totals; the $21,231.43
      row-sum gap is exactly the blank-direction rows; top-committee
      lists are sorted, split correctly, and null for Armstrong.
  (m) clean-rule generalization: Constantino verified clean=True WITH
      2026 linkage evidence (self-funding 2026 loans $14.4M, coverage
      10/14/2026); Luria stays null — her linked ID's 2026 weball row
      covers only through 07/15/2025 while her real 2026 campaign
      (H6VA02198, $8,044,063.94 receipts) is unlinked. Unopposed
      exclusion: Pressley (MA-07), Jacobs (CA-51) and Radewagen (AS)
      ran unopposed in 2026, so they are null, not clean; King-Hinds
      faced a funded opponent (MP district 01, Deleon Guerrero
      $31,476.11) and stays verified-clean; nine people ran unopposed
      in total, six of them dirty.

Caveat (methodology §13): this verifies the dataset against its own
definitions. It cannot catch a missing dimension — e.g. the
self-funding blind spot found Nov 12, 2026 (candidate loans and
contributions were never pulled, so no audit here would have flagged
their absence). A new money dimension needs a new audit, not just a
re-run of this one.
"""
import argparse
import csv
import json
import sys
from decimal import Decimal

import pandas as pd

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
CURRENT = CFG['cycles']['current']
FAILURES = []


def check(label, condition, detail=''):
    status = 'ok ' if condition else 'FAIL'
    print(f'[{status}] {label}' + (f' — {detail}' if detail and not condition else ''))
    if not condition:
        FAILURES.append(f'{label}: {detail}')


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def competition_ranks(records, col):
    values = [r[col] for r in records if is_num(r[col])]
    return {r['person_key']: (None if not is_num(r[col])
                              else 1 + sum(1 for x in values if x > r[col]))
            for r in records}


def cycle_sum(entries, field):
    vals = [e[field] for e in entries if e['cycle'] == CURRENT]
    return round(sum(vals), 2) if vals else 0


def load_weball_2026_races():
    """2026 races from the FEC all-candidates file (weball26).

    Same rule as compute_2026.py, recomputed independently here:
    race_map maps (office, state, district) to [(candidate_id, total
    receipts)]; by_cid maps candidate_id to its race. weball is
    pipe-delimited, 30 fields, no header: p[0] candidate ID (H/S/P
    prefix = office), p[5] total receipts, p[18] state, p[19]
    district. The race comes from the filing's own row, not the
    roster district (MP delegate race is filed under district 01).
    """
    yy = f"{CURRENT % 100:02d}"
    path = ROOT / CFG['paths']['bulk'] / 'weball' / f'weball{yy}.txt'
    race_map = {}
    by_cid = {}
    with open(path) as f:
        for line in f:
            p = line.rstrip('\n').split('|')
            if len(p) != 30:
                continue
            try:
                receipts = float(p[5] or 0)
            except ValueError:
                receipts = 0.0
            race = (p[0][0], p[18], p[19])
            race_map.setdefault(race, []).append((p[0], receipts))
            by_cid[p[0]] = race
    return race_map, by_cid


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dataset-csv', default=CFG['paths']['dataset_csv'])
    ap.add_argument('--dataset-json', default=CFG['paths']['dataset_json'])
    args = ap.parse_args()

    records = json.load(open(ROOT / args.dataset_json))
    by_key = {r['person_key']: r for r in records}
    numeric = [r for r in records
               if r['individual_contribution_total_career'] != 'unknown']

    # (i) row count, uniqueness, order
    check('row count is 664', len(records) == 664, f'got {len(records)}')
    check('person_keys unique', len(by_key) == len(records))
    roster_keys = [r['person_key'] for r in
                   json.load(open(ROOT / CFG['paths']['roster']))
                   if r['person_key'] != 'kristen-mcdonaldrivetmihouse']
    check('row order matches roster.json',
          [r['person_key'] for r in records] == roster_keys)

    # (a) per-cycle sums reproduce every career column
    pc_map = [('individual', 'individual_contribution_total_career'),
              ('aipac_pac_direct', 'aipac_pac_direct_career'),
              ('aipac_earmark_transmitted', 'aipac_earmark_transmitted_career'),
              ('corporate_pac', 'corporate_pac_career'),
              ('corporate_earmark_transmitted', 'corporate_earmark_transmitted_career')]
    mism = 0
    for r in numeric:
        for src, dst in pc_map:
            if round(sum(e[src] for e in r['per_cycle']), 2) != r[dst]:
                mism += 1
        if round(sum(e['udp_ie_support'] for e in r['udp_per_cycle']), 2) != r['udp_ie_support_career']:
            mism += 1
    check('per-cycle sums reproduce every career column (0 mismatches)',
          mism == 0, f'{mism} mismatches')

    # (j) self-funding / topline per-cycle sums (flows summed; stocks =
    # latest cycle's value); named spot cases; debts owed to null.
    sf_map = [('candidate_contributions', 'cand_contrib_career'),
              ('candidate_loans', 'cand_loans_career'),
              ('loan_repayments', 'loan_repayments_career'),
              ('total_receipts', 'total_receipts_career'),
              ('total_disbursements', 'total_disbursements_career'),
              ('transfers_from_auth', 'transfers_from_auth_career'),
              ('transfers_to_auth', 'transfers_to_auth_career')]
    mism = 0
    for r in numeric:
        entries = r['self_funding_per_cycle']
        for src, dst in sf_map:
            if round(sum(e[src] for e in entries), 2) != r[dst]:
                mism += 1
        if round(sum(e['candidate_contributions'] + e['candidate_loans']
                     for e in entries), 2) != r['self_funding_career']:
            mism += 1
        for src, dst in (('cash_on_hand', 'cash_on_hand_career'),
                         ('debts_owed_by', 'debts_owed_by_career')):
            if entries:
                latest = max(e['cycle'] for e in entries)
                want = round(sum(e[src] for e in entries if e['cycle'] == latest), 2)
            else:
                want = None
            if r[dst] != want:
                mism += 1
        if r['debts_owed_to_career'] is not None:
            mism += 1
    check('self-funding/topline per-cycle sums reproduce career columns (0 mismatches)',
          mism == 0, f'{mism} mismatches')
    named_sf = {
        'anthonyconstantinonyhouse': ('Constantino', 'self_funding_career', 17000000.00),
        'S001217': ('Rick Scott', 'self_funding_career', 89994251.12),
        'R000618': ('Pete Ricketts', 'self_funding_career', 19442012.33),
        'T000488': ('Shri Thanedar', 'self_funding_career', 17456074.00),
        'M001232': ('April McClain Delaney', 'self_funding_career', 14873000.00),
        'J000305': ('Sara Jacobs', 'self_funding_career', 11551385.89),
        'C001123': ('Gilbert Ray Cisneros, Jr.', 'self_funding_career', 9807843.10),
        'S001229': ('Jefferson Shreve', 'self_funding_career', 7943000.00),
    }
    mism = 0
    for pk, (name, col, want) in named_sf.items():
        if by_key[pk][col] != want:
            mism += 1
            print(f'  spot mismatch {name} {col}: {by_key[pk][col]} != {want}')
    check('self-funding named spot cases exact', mism == 0, f'{mism} mismatches')
    const = by_key['anthonyconstantinonyhouse']
    check('Constantino career receipts $17,064,951.19 / disbursements $14,765,966.71',
          const['total_receipts_career'] == 17064951.19
          and const['total_disbursements_career'] == 14765966.71,
          f"got {const['total_receipts_career']} / {const['total_disbursements_career']}")
    check('Constantino 2026 cash $2,298,984.48 / receipts $14,464,951.19',
          const['cash_on_hand_2026'] == 2298984.48
          and const['total_receipts_2026'] == 14464951.19,
          f"got COH {const['cash_on_hand_2026']}")
    check('debts_owed_to_career is null for every numeric row',
          all(r['debts_owed_to_career'] is None for r in numeric))
    arm = by_key.get('A000383')
    check('Armstrong new money columns are unknown, top committees null',
          arm is not None
          and arm['self_funding_career'] == 'unknown'
          and arm['other_committees_total_career'] == 'unknown'
          and arm['all_ie_total_career'] == 'unknown'
          and arm['all_ie_top_committees'] is None)

    # (k) other-committee per-cycle sums (classes, earmarks, total).
    oc_buckets = ['party_committees', 'leadership_pacs', 'labor_pacs', 'trade_pacs',
                  'membership_pacs', 'cooperative_pacs', 'other_unclassified']
    mism = 0
    for r in numeric:
        entries = r['other_committees_per_cycle']
        for b in oc_buckets:
            if round(sum(e[b] for e in entries), 2) != r[f'{b}_career']:
                mism += 1
            if round(sum(e['earmark_transmitted'].get(b, 0.0) for e in entries), 2) != \
                    r[f'{b}_earmark_transmitted_career']:
                mism += 1
        if round(sum(r[f'{b}_career'] for b in oc_buckets), 2) != r['other_committees_total_career']:
            mism += 1
    check('other-committee per-cycle sums reproduce career columns (0 mismatches)',
          mism == 0, f'{mism} mismatches')
    oc_diag = json.load(open(ROOT / CFG['paths']['other_committees_diagnostics']))
    cc = oc_diag['cross_checks_vs_methodology']
    check('other-committee pull re-derives corporate/AIPAC to the cent',
          all(v['match'] for v in cc.values()),
          f"{[k for k, v in cc.items() if not v['match']]}")
    lamb = by_key['marklambazhouse']
    lamb_pc26 = [e for e in lamb['other_committees_per_cycle'] if e['cycle'] == CURRENT]
    lamb_total = round(sum(sum(e[b] for b in oc_buckets) for e in lamb_pc26), 2)
    check('Lamb 2026 other-committee pas2-derived $96,500.00',
          lamb_total == 96500.00 and lamb['other_committees_total_2026'] == 96500.00,
          f'got {lamb_total}')
    check('Lamb data_notes records the $32,650 pending reconciliation',
          'PENDING RECONCILIATION' in lamb['data_notes'] and '$32,650.00' in lamb['data_notes'])

    # (l) all-IE per-cycle sums; UDP 2024 exact; cycle totals; the
    # $21,231.43 blank-direction reconciliation; top committees.
    mism = 0
    for r in numeric:
        entries = r['all_ie_per_cycle']
        for src, dst in (('all_ie_support', 'all_ie_support_career'),
                         ('all_ie_oppose', 'all_ie_oppose_career'),
                         ('all_ie_total', 'all_ie_total_career')):
            if round(sum(e[src] for e in entries), 2) != r[dst]:
                mism += 1
    check('all-IE per-cycle sums reproduce career columns (0 mismatches)',
          mism == 0, f'{mism} mismatches')
    aie_raw = json.load(open(ROOT / CFG['paths']['all_ie_per_cycle']))
    udp24 = aie_raw['validation']['udp_2024_exact']
    check('all-IE UDP 2024 deduped S+O exactly $38,044,932.69',
          udp24['computed'] == 38044932.69 and udp24['status'] == 'exact',
          f"got {udp24['computed']} ({udp24['status']})")
    for yr, want in CFG['verification']['all_ie_cycle_totals'].items():
        got = aie_raw['per_cycle_summaries'][str(yr)]['roster_targeted']['total']
        check(f'all-IE roster total {yr} == {want:,.2f}', got == want, f'got {got:,.2f}')
    nodir = round(sum(r['all_ie_total_career'] - r['all_ie_support_career']
                      - r['all_ie_oppose_career'] for r in numeric), 2)
    check('all-IE row-sum gap is exactly the $21,231.43 blank-direction rows',
          nodir == 21231.43, f'got {nodir}')
    mism = 0
    for r in numeric:
        top = r['all_ie_top_committees']
        if top is None:
            mism += 1
            continue
        totals = [c['total'] for c in top]
        if totals != sorted(totals, reverse=True) or len(top) > 5:
            mism += 1
        for c in top:
            if round(c['support'] + c['oppose'], 2) != c['total']:
                mism += 1
    check('all-IE top-committee lists sorted, split correctly, max 5',
          mism == 0, f'{mism} mismatches')
    elsayed = next(r for r in numeric if 'El-Sayed' in r['full_name'])
    check('El-Sayed all-IE support $41,085,593.24 / oppose $107,400,660.67',
          elsayed['all_ie_support_career'] == 41085593.24
          and elsayed['all_ie_oppose_career'] == 107400660.67,
          f"got {elsayed['all_ie_support_career']} / {elsayed['all_ie_oppose_career']}")

    # (b) roster totals match methodology.md figures
    # (None stocks — cash on hand / debts owed by for people with no
    # weball rows at all — are skipped, exactly as the config totals
    # were computed from the staged CSVs.)
    for col, expected in CFG['verification']['methodology_totals'].items():
        total = round(sum(r[col] for r in numeric if r[col] is not None), 2)
        check(f'roster total {col} == {expected:,.2f}', total == expected,
              f'got {total:,.2f}')

    # (c) rank columns recompute exactly
    rank_defs = [('rank_total_accepted', 'total_accepted_career'),
                 ('rank_individual', 'individual_contribution_total_career'),
                 ('rank_corporate_pac', 'corporate_pac_career'),
                 ('rank_aipac_direct', 'aipac_pac_direct_career'),
                 ('rank_udp_support', 'udp_ie_support_career'),
                 ('rank_udp_opposing_opponents', 'udp_ie_opposing_opponents_career'),
                 ('rank_udp_total_benefit', 'udp_ie_total_benefit_career'),
                 ('rank_self_funding', 'self_funding_career'),
                 ('rank_all_ie_support', 'all_ie_support_career'),
                 ('rank_all_ie_oppose', 'all_ie_oppose_career'),
                 ('rank_all_ie_total', 'all_ie_total_career'),
                 ('rank_other_committees_total', 'other_committees_total_career')]
    # total_accepted itself
    ta_mism = sum(1 for r in numeric
                  if round(r['individual_contribution_total_career']
                           + r['corporate_pac_career']
                           + r['aipac_pac_direct_career'], 2) != r['total_accepted_career'])
    check('total_accepted recomputes exactly', ta_mism == 0, f'{ta_mism} mismatches')
    for rank_col, val_col in rank_defs:
        ranks = competition_ranks(records, val_col)
        mism = sum(1 for r in records if r[rank_col] != ranks[r['person_key']])
        check(f'{rank_col} recomputes exactly', mism == 0, f'{mism} mismatches')

    # (d) clean counts
    exp = CFG['verification']['clean_2026']
    counts = {'true_total': sum(1 for r in records if r['clean_2026'] is True),
              'false_total': sum(1 for r in records if r['clean_2026'] is False),
              'null_total': sum(1 for r in records if r['clean_2026'] is None)}
    for key in ('true_total', 'false_total', 'null_total'):
        check(f'clean_2026 {key} == {exp[key]}', counts[key] == exp[key],
              f"got {counts[key]}")
    house120 = [r for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'House']
    house_clean = [r for r in house120 if r['clean_2026'] is True]
    check('120th House clean == 64', len(house_clean) == exp['house_120th_verified_clean'],
          f"got {len(house_clean)}")
    for party in ('Democrat', 'Republican'):
        n = sum(1 for r in house_clean if r['party_120'] == party)
        check(f"120th House clean {party} == {exp[f'house_120th_verified_clean_{party.lower()}']}",
              n == exp[f'house_120th_verified_clean_{party.lower()}'], f'got {n}')
    career_clean = [r for r in house120 if r['corporate_pac_career'] == 0
                    and r['aipac_pac_direct_career'] == 0 and r['udp_ie_support_career'] == 0]
    check('career-clean 120th House == 53',
          len(career_clean) == exp['house_120th_career_clean'], f'got {len(career_clean)}')
    for party in ('Democrat', 'Republican'):
        n = sum(1 for r in career_clean if r['party_120'] == party)
        check(f"career-clean 120th House {party} == "
              f"{exp[f'house_120th_career_clean_{party.lower()}']}",
              n == exp[f'house_120th_career_clean_{party.lower()}'], f'got {n}')
    career_keys = {r['person_key'] for r in career_clean}
    not_career = sum(1 for r in house_clean if r['person_key'] not in career_keys)
    check('2026-clean but not career-clean (120th House) == 11',
          not_career == exp['house_120th_clean_2026_not_career_clean'], f'got {not_career}')

    # (e) 2026 columns, clean rule, dep_share
    opp = json.load(open(ROOT / CFG['paths']['opposition_computed']))
    race_map, by_cid = load_weball_2026_races()
    credit_2026 = {}
    for race, pk, _name, amount, _detail in opp['credit_detail']:
        if race[0] == CURRENT and not pk.startswith('__nonroster__'):
            # Sum across phases: one person can now be credited in two phases
            # of the same race (the race key includes ele_type).
            credit_2026[pk] = round(credit_2026.get(pk, 0.0) + float(amount), 2)
    oc_buckets_e = ['party_committees', 'leadership_pacs', 'labor_pacs', 'trade_pacs',
                    'membership_pacs', 'cooperative_pacs', 'other_unclassified']
    mism = 0
    for r in records:
        expect = {
            'individual_2026': cycle_sum(r['per_cycle'], 'individual'),
            'corp_2026': cycle_sum(r['per_cycle'], 'corporate_pac'),
            'aipac_direct_2026': cycle_sum(r['per_cycle'], 'aipac_pac_direct'),
            'udp_support_2026': cycle_sum(r['udp_per_cycle'], 'udp_ie_support'),
            'udp_opp_credit_2026': credit_2026.get(r['person_key'], 0.0),
        }
        expect['udp_benefit_2026'] = round(expect['udp_support_2026']
                                           + expect['udp_opp_credit_2026'], 2)
        expect['dirty_2026'] = round(expect['corp_2026'] + expect['aipac_direct_2026']
                                     + expect['udp_benefit_2026'], 2)
        denom = expect['individual_2026'] + expect['corp_2026'] + expect['aipac_direct_2026']
        expect['dep_share_2026'] = (round((expect['corp_2026']
                                           + expect['aipac_direct_2026']) / denom, 4)
                                    if denom > 0 else None)
        sf26 = [e for e in r['self_funding_per_cycle'] if e['cycle'] == CURRENT]
        expect['self_funding_2026'] = (
            round(sum(e['candidate_contributions'] + e['candidate_loans'] for e in sf26), 2)
            if sf26 else 0)
        expect['cand_loans_2026'] = cycle_sum(r['self_funding_per_cycle'], 'candidate_loans')
        expect['cand_contrib_2026'] = cycle_sum(r['self_funding_per_cycle'],
                                                'candidate_contributions')
        expect['total_receipts_2026'] = cycle_sum(r['self_funding_per_cycle'], 'total_receipts')
        expect['total_disbursements_2026'] = cycle_sum(r['self_funding_per_cycle'],
                                                       'total_disbursements')
        expect['cash_on_hand_2026'] = (round(sum(e['cash_on_hand'] for e in sf26), 2)
                                       if sf26 else None)
        oc26 = [e for e in r['other_committees_per_cycle'] if e['cycle'] == CURRENT]
        expect['other_committees_total_2026'] = (
            round(sum(sum(e[b] for b in oc_buckets_e) for e in oc26), 2) if oc26 else 0)
        expect['all_ie_support_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_support')
        expect['all_ie_oppose_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_oppose')
        expect['all_ie_total_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_total')
        # Generalized linkage rule (see compute_2026.py): a tracked/UDP
        # 2026 entry, or a self-funding 2026 entry whose coverage end
        # date falls in calendar 2026.
        has_linkage = (any(e['cycle'] == CURRENT for e in r['per_cycle'])
                       or any(e['cycle'] == CURRENT for e in r['udp_per_cycle'])
                       or any(e['cycle'] == CURRENT
                              and str(e.get('coverage_end_date', '')).endswith('/2026')
                              for e in r['self_funding_per_cycle']))
        # Unopposed rule (see compute_2026.py): every 2026 race the
        # person filed in has no OTHER candidate with receipts over $0.
        # False when they filed no 2026 candidacy at all.
        ids = set(r['fec_candidate_ids'] or [])
        races = sorted({by_cid[cid] for cid in ids if cid in by_cid})
        expect['unopposed_2026'] = bool(races) and all(
            not any(cid not in ids and receipts > 0
                    for cid, receipts in race_map.get(race, []))
            for race in races)
        if r['in_120th'] == 'yes' and not has_linkage:
            expect['clean_2026'] = None
        elif (expect['unopposed_2026'] and expect['corp_2026'] == 0
                and expect['aipac_direct_2026'] == 0
                and expect['udp_support_2026'] == 0
                and expect['udp_opp_credit_2026'] == 0):
            expect['clean_2026'] = None
        else:
            expect['clean_2026'] = (expect['corp_2026'] == 0
                                    and expect['aipac_direct_2026'] == 0
                                    and expect['udp_support_2026'] == 0
                                    and expect['udp_opp_credit_2026'] == 0)
        for k, v in expect.items():
            if r[k] != v:
                mism += 1
                if mism <= 5:
                    print(f'  2026 mismatch {r["person_key"]} {k}: {r[k]!r} != {v!r}')
    check('2026 columns + clean rule + dep_share recompute exactly',
          mism == 0, f'{mism} mismatches')

    # (m) clean-rule generalization spot cases.
    const = by_key['anthonyconstantinonyhouse']
    const_sf26 = [e for e in const['self_funding_per_cycle'] if e['cycle'] == CURRENT]
    check('Constantino verified clean=True WITH 2026 linkage evidence',
          const['clean_2026'] is True
          and len(const_sf26) == 1
          and const_sf26[0]['coverage_end_date'] == '10/14/2026'
          and const_sf26[0]['candidate_loans'] == 14400000.00
          and const['all_ie_support_2026'] == 459491.94
          and const['all_ie_oppose_2026'] == 3721257.82,
          f"clean={const['clean_2026']}")
    luria = by_key['L000591']
    luria_sf26 = [e for e in luria['self_funding_per_cycle'] if e['cycle'] == CURRENT]
    check('Luria stays null — linked ID has no 2026-coverage weball row',
          luria['clean_2026'] is None
          and len(luria_sf26) == 1
          and luria_sf26[0]['coverage_end_date'] == '07/15/2025'
          and 'H6VA02198' not in luria['fec_candidate_ids']
          and 'UNVERIFIED' in luria['data_notes'],
          f"clean={luria['clean_2026']}")
    check('Luria stale-ID 2026 money exists but does not verify her',
          luria['other_committees_total_2026'] == 85610.00
          and luria['all_ie_support_2026'] == 685786.28,
          f"OC {luria['other_committees_total_2026']} / AIE {luria['all_ie_support_2026']}")

    # (m) unopposed exclusion spot cases.
    for key, name, race in [('J000305', 'Jacobs', 'CA-51'),
                            ('P000617', 'Pressley', 'MA-07'),
                            ('R000600', 'Radewagen', 'AS-00')]:
        p = by_key[key]
        check(f'{name} unopposed in 2026 ({race}) — null, not clean',
              p['clean_2026'] is None and p['unopposed_2026'] is True
              and 'UNOPPOSED' in p['data_notes']
              and race in p['data_notes'],
              f"clean={p['clean_2026']} unopposed={p['unopposed_2026']}")
    king_hinds = by_key['K000404']
    check('King-Hinds contested, not unopposed — MP race is district 01',
          king_hinds['clean_2026'] is True
          and king_hinds['unopposed_2026'] is False
          and 'UNOPPOSED' not in king_hinds['data_notes'],
          f"clean={king_hinds['clean_2026']} "
          f"unopposed={king_hinds['unopposed_2026']}")
    n_unopposed = sum(1 for r in records if r['unopposed_2026'] is True)
    check('unopposed in 2026 == 9 (3 clean-nulls + 6 dirty)',
          n_unopposed == 9, f'got {n_unopposed}')

    # (f) opposition career columns
    mism = 0
    for r in numeric:
        credit = round(float(opp['credit_by_person'].get(r['person_key'], 0.0)), 2)
        if r['udp_ie_opposing_opponents_career'] != credit:
            mism += 1
        if r['udp_ie_total_benefit_career'] != round(r['udp_ie_support_career'] + credit, 2):
            mism += 1
    check('opposition career columns recompute from opposition-computed.json',
          mism == 0, f'{mism} mismatches')
    arm = by_key.get('A000383')
    check('Armstrong opposition columns are null (money unknown)',
          arm is not None and arm['udp_ie_opposing_opponents_career'] is None
          and arm['udp_ie_total_benefit_career'] is None)

    # (g) dedup audit
    dedup = json.load(open(ROOT / CFG['paths']['dedup_applied']))
    # money_per_cycle.json is a dict keyed by person_key.
    mpc_by_key = json.load(open(ROOT / CFG['paths']['money_per_cycle']))
    mism = 0
    total_corrected = Decimal('0')
    for entry in dedup:
        pk = entry['person_key']
        per_cycle = {(e['cycle'], e['candidate_id']): e
                     for e in mpc_by_key[pk]['per_cycle']}
        for dropped_id in entry['dropped_ids']:
            e = per_cycle.get((entry['cycle'], dropped_id))
            if e is None or Decimal(e['individual']) != Decimal('0.00'):
                mism += 1
        kept = per_cycle.get((entry['cycle'], entry['kept_id']))
        if kept is None or Decimal(kept['individual']) != Decimal(entry['amount']):
            mism += 1
        total_corrected += Decimal(entry['amount'])
    check('dedup applied: dropped copies are 0.00, kept copies match the record',
          mism == 0, f'{mism} mismatches')
    check('dedup total is $451,776,015.34',
          total_corrected == Decimal('451776015.34'), f'got {total_corrected}')
    check('dedup record has 90 groups', len(dedup) == 90, f'got {len(dedup)}')

    # (h) CSV <-> JSON agreement
    df = pd.read_csv(ROOT / args.dataset_csv, dtype=str, keep_default_na=False)
    check('CSV has 664 data rows', len(df) == 664, f'got {len(df)}')
    csv_by_key = {row['person_key']: row for _, row in df.iterrows()}
    check('CSV person_keys match JSON', set(csv_by_key) == set(by_key))
    mism = 0
    json_keys = CFG['dataset']['json_keys']
    for pk, r in by_key.items():
        crow = csv_by_key.get(pk)
        if crow is None:
            continue
        for k in json_keys:
            if k == 'all_ie_top_committees':
                continue  # JSON-only by design; not in the CSV.
            cv, jv = crow[k], r[k]
            if k in ('per_cycle', 'udp_per_cycle', 'self_funding_per_cycle',
                     'other_committees_per_cycle', 'all_ie_per_cycle',
                     'fec_candidate_ids'):
                if cv != repr(jv):
                    mism += 1
            elif k == 'clean_2026':
                want = '' if jv is None else str(jv)
                if cv != want:
                    mism += 1
            elif jv is None:
                if cv != '':
                    mism += 1
            elif isinstance(jv, (int, float)) and not isinstance(jv, bool):
                # Numeric compare: pandas writes a mixed int/float column
                # as floats ('510.0' for JSON int 510) because Armstrong's
                # null forces the column to float dtype. Same value,
                # different string form.
                if cv == '' or float(cv) != float(jv):
                    mism += 1
            else:
                if cv != str(jv):
                    mism += 1
    check('CSV and JSON agree field by field', mism == 0, f'{mism} mismatches')

    print()
    if FAILURES:
        print(f'VERIFY FAILED: {len(FAILURES)} check(s) failed')
        for f in FAILURES:
            print(f'  - {f}')
        sys.exit(1)
    print('VERIFY PASSED: all standing audits clean.')
    print('Note: these audits check the dataset against its own definitions; '
          'they cannot catch a missing money dimension (see module docstring).')


if __name__ == '__main__':
    main()

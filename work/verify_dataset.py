#!/usr/bin/env python3
"""Standing audits for the Congress money tracker dataset.

Usage:
    python3 work/verify_dataset.py [--dataset-csv PATH] [--dataset-json PATH]

Checks (exit non-zero on any mismatch, printing every failure):
  (a) per-cycle sums reproduce every career column (0 mismatches).
  (b) roster totals match config verification.methodology_totals to the
      cent (Armstrong's "unknown" money excluded from every sum).
  (c) all seven rank columns recompute exactly (competition ranking:
      rank = 1 + count of strictly greater values).
  (d) clean counts match config verification.clean_2026 (True 84 /
      False 579 / None 1; 120th House clean 67 — 63 D, 4 R;
      career-clean 120th House 53 — 50 D, 3 R; 2026-clean but not
      career-clean 14).
  (e) the nine 2026 columns, the clean rule, and dep_share recompute
      exactly (including the Luria unverified case and the int/float
      split on empty 2026 sums).
  (f) the opposition career columns recompute from
      opposition-computed.json.
  (g) dedup audit: the dropped per-cycle entries in dedup-applied.json
      are '0.00' in money_per_cycle.json, and the kept entries equal
      the recorded amounts.
  (h) CSV and JSON agree field by field (664 rows, same person_keys,
      same values — CSV floats compare by float value, clean_2026 by
      True/False/empty, dep_share by float value).
  (i) 664 rows, unique person_keys, row order matches roster.json.

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

from config import load_config

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

    # (b) roster totals match methodology.md figures
    for col, expected in CFG['verification']['methodology_totals'].items():
        total = round(sum(r[col] for r in numeric), 2)
        check(f'roster total {col} == {expected:,.2f}', total == expected,
              f'got {total:,.2f}')

    # (c) rank columns recompute exactly
    rank_defs = [('rank_total_accepted', 'total_accepted_career'),
                 ('rank_individual', 'individual_contribution_total_career'),
                 ('rank_corporate_pac', 'corporate_pac_career'),
                 ('rank_aipac_direct', 'aipac_pac_direct_career'),
                 ('rank_udp_support', 'udp_ie_support_career'),
                 ('rank_udp_opposing_opponents', 'udp_ie_opposing_opponents_career'),
                 ('rank_udp_total_benefit', 'udp_ie_total_benefit_career')]
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
    check('120th House clean == 67', len(house_clean) == exp['house_120th_verified_clean'],
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
    check('2026-clean but not career-clean (120th House) == 14',
          not_career == exp['house_120th_clean_2026_not_career_clean'], f'got {not_career}')

    # (e) 2026 columns, clean rule, dep_share
    opp = json.load(open(ROOT / CFG['paths']['opposition_computed']))
    credit_2026 = {}
    for race, pk, _name, amount, _detail in opp['credit_detail']:
        if race[0] == CURRENT and not pk.startswith('__nonroster__'):
            credit_2026[pk] = round(float(amount), 2)
    mism = 0
    for r in records:
        pc26 = [e for e in r['per_cycle'] if e['cycle'] == CURRENT]
        udp26 = [e for e in r['udp_per_cycle'] if e['cycle'] == CURRENT]
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
        has_pre_2026 = any(e['cycle'] < CURRENT for e in r['per_cycle'])
        if r['in_120th'] == 'yes' and not pc26 and not udp26 and has_pre_2026:
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
            cv, jv = crow[k], r[k]
            if k in ('per_cycle', 'udp_per_cycle', 'fec_candidate_ids'):
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

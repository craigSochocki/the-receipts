#!/usr/bin/env python3
"""Standing audits for the Congress money tracker dataset.

Usage:
    python3 receipts/validate/verify_dataset.py [--dataset-csv PATH] [--dataset-json PATH]

Checks (exit non-zero on any mismatch, printing every failure):
  (a) per-cycle sums reproduce every career column (0 mismatches).
  (b) roster totals match config verification.methodology_totals to the
      cent (Armstrong's "unknown" money excluded from every sum).
  (c) all twelve rank columns recompute exactly (competition ranking:
      rank = 1 + count of strictly greater values).
  (d) clean counts match config verification.clean_2026 (True 98 /
      False 562 / None 4; 120th House clean 70 — 67 D, 3 R;
      career-clean 120th House 53 — 50 D, 3 R; 2026-clean but not
      career-clean 17). The True count is post net-negative fix: 17
      members with dirty_2026 < 0 from refunds read clean (see (o)).
  (e) the twenty-three 2026 columns, the clean rule, and dep_share
      recompute exactly (including the Luria unverified case, the
      generalized linkage rule, the unopposed_2026 flag recomputed
      from weball26, the unopposed nulling of would-be-clean verdicts,
      the net-negative clean rule, the AIPAC/UDP flag and both
      tolerance tiers, and the int/float split on empty 2026 sums).
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
  (n) senate_class: re-derived here from the legislators yaml
      (legislators-current.yaml, Senate-term class field) and compared
      to the dataset for every row — None for non-senators, 1/2/3 for
      every senator; 120th class counts C1 33 / C2 32 / C3 34; 16 Class 3
      Democrats in the 120th; named spot cases.
  (o) tiered dirty rule (methodology §14): the AIPAC/UDP flag
      recomputes from aipac_direct_2026 / udp_benefit_2026 (231 in the
      120th, 291 roster-wide); both tolerance tiers recompute from the
      flag + the config thresholds (Balanced 84 / 119 / 328, Lenient
      84 / 173 / 274 over the 120th, null 4); the corp-only splits
      (211 corp-only in the 120th; 93 / 41 stay dirty); the 2028-target
      counts under each preset (Strict 192 / 13, Balanced 133 / 6,
      Lenient 103 / 3); spot cases Ryan (clean on a -$15,000 AIPAC
      refund, corp $0), Randall and Garcia (below_threshold with a
      -$5,000 AIPAC component).

Caveat (methodology §13): this verifies the dataset against its own
definitions. It cannot catch a missing dimension — e.g. the
self-funding blind spot found Nov 12, 2026 (candidate loans and
contributions were never pulled, so no audit here would have flagged
their absence). A new money dimension needs a new audit, not just a
re-run of this one.
"""

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal

import pandas as pd
import yaml

from receipts.common.baseline import expected as baseline_figure
from receipts.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
CURRENT = CFG['cycles']['current']
FAILURES = []


METHODOLOGY_TOTAL_COLS = [
    'individual_contribution_total_career',
    'aipac_pac_direct_career',
    'aipac_earmark_transmitted_career',
    'corporate_pac_career',
    'corporate_earmark_transmitted_career',
    'udp_ie_support_career',
    'udp_ie_opposing_opponents_career',
    'udp_ie_total_benefit_career',
    'dirty_career',
    'cand_contrib_career',
    'cand_loans_career',
    'self_funding_career',
    'loan_repayments_career',
    'total_receipts_career',
    'total_disbursements_career',
    'transfers_from_auth_career',
    'transfers_to_auth_career',
    'cash_on_hand_career',
    'debts_owed_by_career',
    'party_committees_career',
    'leadership_pacs_career',
    'labor_pacs_career',
    'trade_pacs_career',
    'membership_pacs_career',
    'cooperative_pacs_career',
    'other_unclassified_career',
    'other_committees_total_career',
    'party_committees_earmark_transmitted_career',
    'leadership_pacs_earmark_transmitted_career',
    'labor_pacs_earmark_transmitted_career',
    'trade_pacs_earmark_transmitted_career',
    'membership_pacs_earmark_transmitted_career',
    'cooperative_pacs_earmark_transmitted_career',
    'other_unclassified_earmark_transmitted_career',
    'all_ie_support_career',
    'all_ie_oppose_career',
    'all_ie_total_career',
]


def check(label, condition, detail=''):
    status = 'ok ' if condition else 'FAIL'
    print(f'[{status}] {label}' + (f' — {detail}' if detail and not condition else ''))
    if not condition:
        FAILURES.append(f'{label}: {detail}')


def pin(label, key, observed):
    """Check a figure that new FEC data can move against the baseline."""
    want = baseline_figure(key, observed)
    check(f'{label} [{key}]', observed == want, f'got {observed!r}, baseline {want!r}')


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def competition_ranks(records, col):
    values = [r[col] for r in records if is_num(r[col])]
    return {
        r['person_key']: (None if not is_num(r[col]) else 1 + sum(1 for x in values if x > r[col]))
        for r in records
    }


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
    yy = f'{CURRENT % 100:02d}'
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
    numeric = [r for r in records if r['individual_contribution_total_career'] != 'unknown']

    # (i) row count, uniqueness, order
    check('row count is 664', len(records) == 664, f'got {len(records)}')
    check('person_keys unique', len(by_key) == len(records))
    roster_keys = [
        r['person_key']
        for r in json.load(open(ROOT / CFG['paths']['roster']))
        if r['person_key'] != 'kristen-mcdonaldrivetmihouse'
    ]
    check('row order matches roster.json', [r['person_key'] for r in records] == roster_keys)

    # (a) per-cycle sums reproduce every career column
    pc_map = [
        ('individual', 'individual_contribution_total_career'),
        ('aipac_pac_direct', 'aipac_pac_direct_career'),
        ('aipac_earmark_transmitted', 'aipac_earmark_transmitted_career'),
        ('corporate_pac', 'corporate_pac_career'),
        ('corporate_earmark_transmitted', 'corporate_earmark_transmitted_career'),
    ]
    mism = 0
    for r in numeric:
        for src, dst in pc_map:
            if round(sum(e[src] for e in r['per_cycle']), 2) != r[dst]:
                mism += 1
        if (
            round(sum(e['udp_ie_support'] for e in r['udp_per_cycle']), 2)
            != r['udp_ie_support_career']
        ):
            mism += 1
    check(
        'per-cycle sums reproduce every career column (0 mismatches)',
        mism == 0,
        f'{mism} mismatches',
    )

    # (j) self-funding / topline per-cycle sums (flows summed; stocks =
    # latest cycle's value); named spot cases; debts owed to null.
    sf_map = [
        ('candidate_contributions', 'cand_contrib_career'),
        ('candidate_loans', 'cand_loans_career'),
        ('loan_repayments', 'loan_repayments_career'),
        ('total_receipts', 'total_receipts_career'),
        ('total_disbursements', 'total_disbursements_career'),
        ('transfers_from_auth', 'transfers_from_auth_career'),
        ('transfers_to_auth', 'transfers_to_auth_career'),
    ]
    mism = 0
    for r in numeric:
        entries = r['self_funding_per_cycle']
        for src, dst in sf_map:
            if round(sum(e[src] for e in entries), 2) != r[dst]:
                mism += 1
        if (
            round(sum(e['candidate_contributions'] + e['candidate_loans'] for e in entries), 2)
            != r['self_funding_career']
        ):
            mism += 1
        for src, dst in (
            ('cash_on_hand', 'cash_on_hand_career'),
            ('debts_owed_by', 'debts_owed_by_career'),
        ):
            if entries:
                latest = max(e['cycle'] for e in entries)
                want = round(sum(e[src] for e in entries if e['cycle'] == latest), 2)
            else:
                want = None
            if r[dst] != want:
                mism += 1
        if r['debts_owed_to_career'] is not None:
            mism += 1
    check(
        'self-funding/topline per-cycle sums reproduce career columns (0 mismatches)',
        mism == 0,
        f'{mism} mismatches',
    )
    named_sf = {
        'anthonyconstantinonyhouse': 'Constantino',
        'S001217': 'Rick Scott',
        'R000618': 'Pete Ricketts',
        'T000488': 'Shri Thanedar',
        'M001232': 'April McClain Delaney',
        'J000305': 'Sara Jacobs',
        'C001123': 'Gilbert Ray Cisneros, Jr.',
        'S001229': 'Jefferson Shreve',
    }
    for pk, name in named_sf.items():
        pin(
            f'{name} self_funding_career',
            f'spot.self_funding_career.{pk}',
            by_key[pk]['self_funding_career'],
        )
    const = by_key['anthonyconstantinonyhouse']
    for col in (
        'total_receipts_career',
        'total_disbursements_career',
        'cash_on_hand_2026',
        'total_receipts_2026',
    ):
        pin(f'Constantino {col}', f'spot.constantino.{col}', const[col])
    check(
        'debts_owed_to_career is null for every numeric row',
        all(r['debts_owed_to_career'] is None for r in numeric),
    )
    arm = by_key.get('A000383')
    check(
        'Armstrong new money columns are unknown, top committees null',
        arm is not None
        and arm['self_funding_career'] == 'unknown'
        and arm['other_committees_total_career'] == 'unknown'
        and arm['all_ie_total_career'] == 'unknown'
        and arm['all_ie_top_committees'] is None,
    )

    # (k) other-committee per-cycle sums (classes, earmarks, total).
    oc_buckets = [
        'party_committees',
        'leadership_pacs',
        'labor_pacs',
        'trade_pacs',
        'membership_pacs',
        'cooperative_pacs',
        'other_unclassified',
    ]
    mism = 0
    for r in numeric:
        entries = r['other_committees_per_cycle']
        for b in oc_buckets:
            if round(sum(e[b] for e in entries), 2) != r[f'{b}_career']:
                mism += 1
            if (
                round(sum(e['earmark_transmitted'].get(b, 0.0) for e in entries), 2)
                != r[f'{b}_earmark_transmitted_career']
            ):
                mism += 1
        if (
            round(sum(r[f'{b}_career'] for b in oc_buckets), 2)
            != r['other_committees_total_career']
        ):
            mism += 1
    check(
        'other-committee per-cycle sums reproduce career columns (0 mismatches)',
        mism == 0,
        f'{mism} mismatches',
    )
    oc_diag = json.load(open(ROOT / CFG['paths']['other_committees_diagnostics']))
    cc = oc_diag['cross_checks_vs_methodology']
    check(
        'other-committee pull re-derives corporate/AIPAC to the cent',
        all(v['match'] for v in cc.values()),
        f'{[k for k, v in cc.items() if not v["match"]]}',
    )
    lamb = by_key['marklambazhouse']
    lamb_pc26 = [e for e in lamb['other_committees_per_cycle'] if e['cycle'] == CURRENT]
    lamb_total = round(sum(sum(e[b] for b in oc_buckets) for e in lamb_pc26), 2)
    check(
        'Lamb 2026 other-committee column equals its per-cycle pas2 sum',
        lamb_total == lamb['other_committees_total_2026'],
        f'got {lamb_total}',
    )
    pin(
        'Lamb 2026 other-committee pas2-derived total',
        'spot.lamb.other_committees_total_2026',
        lamb_total,
    )
    lamb_v = oc_diag['lamb_validation']
    lamb_residual = lamb_v['weball_minus_pas2_cents'] / 100
    pin('Lamb 2026 weball-minus-pas2 residual', 'spot.lamb.weball_minus_pas2_2026', lamb_residual)
    check(
        'Lamb data_notes states the current pas2 total and residual (or no note at zero)',
        ('PENDING RECONCILIATION' not in lamb['data_notes'])
        if lamb_residual == 0
        else (
            f'${lamb_total:,.2f} by pas2' in lamb['data_notes']
            and f'${lamb_residual:,.2f} residual' in lamb['data_notes']
        ),
        lamb['data_notes'][-260:],
    )

    # (l) all-IE per-cycle sums; UDP 2024 exact; cycle totals; the
    # $21,231.43 blank-direction reconciliation; top committees.
    mism = 0
    for r in numeric:
        entries = r['all_ie_per_cycle']
        for src, dst in (
            ('all_ie_support', 'all_ie_support_career'),
            ('all_ie_oppose', 'all_ie_oppose_career'),
            ('all_ie_total', 'all_ie_total_career'),
        ):
            if round(sum(e[src] for e in entries), 2) != r[dst]:
                mism += 1
    check(
        'all-IE per-cycle sums reproduce career columns (0 mismatches)',
        mism == 0,
        f'{mism} mismatches',
    )
    aie_raw = json.load(open(ROOT / CFG['paths']['all_ie_per_cycle']))
    udp24 = aie_raw['validation']['udp_2024_exact']
    check(
        'all-IE UDP 2024 deduped S+O reproduces the UDP pull exactly',
        udp24['status'] == 'exact',
        f'got {udp24["computed"]} ({udp24["status"]})',
    )
    pin('all-IE UDP 2024 deduped S+O', 'udp_prior_cycle_totals.2024', udp24['computed'])
    for yr in sorted(aie_raw['per_cycle_summaries'], key=int):
        pin(
            f'all-IE roster total {yr}',
            f'all_ie_cycle_totals.{yr}',
            aie_raw['per_cycle_summaries'][yr]['roster_targeted']['total'],
        )
    nodir = round(
        sum(
            r['all_ie_total_career'] - r['all_ie_support_career'] - r['all_ie_oppose_career']
            for r in numeric
        ),
        2,
    )
    pin('all-IE row-sum gap (the blank-direction rows)', 'spot.all_ie_blank_direction_gap', nodir)
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
    check(
        'all-IE top-committee lists sorted, split correctly, max 5', mism == 0, f'{mism} mismatches'
    )
    elsayed = next(r for r in numeric if 'El-Sayed' in r['full_name'])
    for col in ('all_ie_support_career', 'all_ie_oppose_career'):
        pin(f'El-Sayed {col}', f'spot.elsayed.{col}', elsayed[col])

    # (b) roster totals match methodology.md figures
    # (None stocks — cash on hand / debts owed by for people with no
    # weball rows at all — are skipped, exactly as the config totals
    # were computed from the staged CSVs.)
    for col in METHODOLOGY_TOTAL_COLS:
        total = round(sum(r[col] for r in numeric if r[col] is not None), 2)
        pin(f'roster total {col}', f'methodology_totals.{col}', total)

    # (c) rank columns recompute exactly
    rank_defs = [
        ('rank_total_accepted', 'total_accepted_career'),
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
        ('rank_other_committees_total', 'other_committees_total_career'),
    ]
    # total_accepted itself
    ta_mism = sum(
        1
        for r in numeric
        if round(
            r['individual_contribution_total_career']
            + r['corporate_pac_career']
            + r['aipac_pac_direct_career'],
            2,
        )
        != r['total_accepted_career']
    )
    check('total_accepted recomputes exactly', ta_mism == 0, f'{ta_mism} mismatches')
    # (c2) dirty_career recomputes exactly: corporate PAC + AIPAC
    # direct + UDP total benefit, career. Null only for Armstrong
    # (money unknown, not zero).
    dc_mism = 0
    for r in records:
        parts = [
            r['corporate_pac_career'],
            r['aipac_pac_direct_career'],
            r['udp_ie_total_benefit_career'],
        ]
        want = round(sum(parts), 2) if all(is_num(v) for v in parts) else None
        if r['dirty_career'] != want:
            dc_mism += 1
    check(
        'dirty_career recomputes exactly (corp + AIPAC + UDP benefit)',
        dc_mism == 0,
        f'{dc_mism} mismatches',
    )
    check(
        'dirty_career is null only for Armstrong',
        [r['person_key'] for r in records if r['dirty_career'] is None] == ['A000383'],
    )
    top_dirty = max(
        (r for r in records if is_num(r['dirty_career'])), key=lambda r: r['dirty_career']
    )
    pin(
        'career dirty #1 (person, amount)',
        'spot.dirty_career_top',
        [top_dirty['person_key'], top_dirty['dirty_career']],
    )
    for rank_col, val_col in rank_defs:
        ranks = competition_ranks(records, val_col)
        mism = sum(1 for r in records if r[rank_col] != ranks[r['person_key']])
        check(f'{rank_col} recomputes exactly', mism == 0, f'{mism} mismatches')

    # (d) clean counts (baseline clean_2026.*)
    counts = {
        'true_total': sum(1 for r in records if r['clean_2026'] is True),
        'false_total': sum(1 for r in records if r['clean_2026'] is False),
        'null_total': sum(1 for r in records if r['clean_2026'] is None),
    }
    for key in ('true_total', 'false_total', 'null_total'):
        pin(f'clean_2026 {key}', f'clean_2026.{key}', counts[key])
    house120 = [r for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'House']
    house_clean = [r for r in house120 if r['clean_2026'] is True]
    pin('120th House clean', 'clean_2026.house_120th_verified_clean', len(house_clean))
    for party in ('Democrat', 'Republican'):
        pin(
            f'120th House clean {party}',
            f'clean_2026.house_120th_verified_clean_{party.lower()}',
            sum(1 for r in house_clean if r['party_120'] == party),
        )
    career_clean = [
        r
        for r in house120
        if r['corporate_pac_career'] == 0
        and r['aipac_pac_direct_career'] == 0
        and r['udp_ie_support_career'] == 0
    ]
    pin('career-clean 120th House', 'clean_2026.house_120th_career_clean', len(career_clean))
    for party in ('Democrat', 'Republican'):
        pin(
            f'career-clean 120th House {party}',
            f'clean_2026.house_120th_career_clean_{party.lower()}',
            sum(1 for r in career_clean if r['party_120'] == party),
        )
    career_keys = {r['person_key'] for r in career_clean}
    pin(
        '2026-clean but not career-clean (120th House)',
        'clean_2026.house_120th_clean_2026_not_career_clean',
        sum(1 for r in house_clean if r['person_key'] not in career_keys),
    )

    # (o) tiered dirty rule: flag, tiers, corp-only splits, targets.
    # The tier logic is re-derived here from the config thresholds,
    # independently of compute_2026.py (same definitions, separate code).
    def corp_material(corp, total_receipts, preset):
        th = CFG['verification']['tolerance_presets'][preset]
        if corp <= th['corp_amount']:
            return False
        if (
            not isinstance(total_receipts, (int, float))
            or isinstance(total_receipts, bool)
            or total_receipts <= 0
        ):
            return False
        return corp / total_receipts > th['corp_share']

    def tier_for(clean, flag, corp, total_receipts, preset):
        if clean is None:
            return None
        if flag or corp_material(corp, total_receipts, preset):
            return 'dirty'
        if corp > 0:
            return 'below_threshold'
        return 'clean'

    r120 = [r for r in records if r['in_120th'] == 'yes']
    pin(
        'aipac_udp_flag_2026 120th',
        'tiered_2026.aipac_udp_flag_120th',
        sum(1 for r in r120 if r['aipac_udp_flag_2026'] is True),
    )
    pin(
        'aipac_udp_flag_2026 roster-wide',
        'tiered_2026.aipac_udp_flag_all',
        sum(1 for r in records if r['aipac_udp_flag_2026'] is True),
    )
    check(
        'aipac_udp_flag_2026 is a boolean on every row',
        all(r['aipac_udp_flag_2026'] in (True, False) for r in records),
    )
    for preset in ('balanced', 'lenient'):
        got = Counter(r[f'tier_{preset}_2026'] for r in r120)
        for tier_name in ('clean', 'below_threshold', 'dirty'):
            pin(
                f'tier_{preset}_2026 {tier_name}',
                f'tiered_2026.{preset}.{tier_name}',
                got.get(tier_name, 0),
            )
        pin(f'tier_{preset}_2026 null', f'tiered_2026.{preset}.null', got.get(None, 0))
        pin(
            f'tier_{preset}_2026 not-dirty (clean + below_threshold)',
            f'tiered_2026.{preset}.not_dirty',
            got.get('clean', 0) + got.get('below_threshold', 0),
        )
        # Tier nulls coincide exactly with clean_2026 nulls.
        check(
            f'tier_{preset}_2026 is null exactly where clean_2026 is null',
            all((r[f'tier_{preset}_2026'] is None) == (r['clean_2026'] is None) for r in records),
        )
        # Monotonicity: a Strict-clean member is never dirty under a
        # looser preset (a looser preset only relaxes the corp rule).
        check(
            f'no Strict-clean member is dirty under {preset}',
            all(r[f'tier_{preset}_2026'] != 'dirty' for r in records if r['clean_2026'] is True),
        )
        # The flag takes precedence: every flagged member is dirty
        # under every preset.
        check(
            f'every flagged member is dirty under {preset}',
            all(
                r[f'tier_{preset}_2026'] == 'dirty'
                for r in records
                if r['aipac_udp_flag_2026'] is True and r['clean_2026'] is not None
            ),
        )
    # Corp-only members in the 120th (corp > 0, AIPAC == 0, UDP == 0)
    # and how many stay dirty under each preset.
    corp_only = [
        r
        for r in r120
        if r['corp_2026'] > 0 and r['aipac_direct_2026'] == 0 and r['udp_benefit_2026'] == 0
    ]
    pin('corp-only members in the 120th', 'tiered_2026.corp_only_2026_120th', len(corp_only))
    for preset in ('balanced', 'lenient'):
        staying = sum(
            1 for r in corp_only if corp_material(r['corp_2026'], r['total_receipts_2026'], preset)
        )
        pin(
            f'corp-only staying dirty under {preset}',
            f'tiered_2026.corp_only_staying_dirty_{preset}',
            staying,
        )
        pin(
            f'corp-only below threshold under {preset}',
            f'tiered_2026.corp_only_below_{preset}',
            len(corp_only) - staying,
        )
    # 2028 primary targets under each preset: tier dirty among House
    # Democrats / Class 3 Senate Democrats in the 120th; Strict is
    # dirty_2026 > 0.
    house_dem = [r for r in r120 if r['chamber_120'] == 'House' and r['party_120'] == 'Democrat']
    sen3_dem = [
        r
        for r in r120
        if r['chamber_120'] == 'Senate' and r['party_120'] == 'Democrat' and r['senate_class'] == 3
    ]
    pin(
        '2028 targets Strict House',
        'tiered_2026.targets_2028_strict_house',
        sum(1 for r in house_dem if r['dirty_2026'] > 0),
    )
    pin(
        '2028 targets Strict Senate Class 3',
        'tiered_2026.targets_2028_strict_senate_class3',
        sum(1 for r in sen3_dem if r['dirty_2026'] > 0),
    )
    for preset in ('balanced', 'lenient'):
        pin(
            f'2028 targets {preset} House',
            f'tiered_2026.targets_2028_{preset}_house',
            sum(1 for r in house_dem if r[f'tier_{preset}_2026'] == 'dirty'),
        )
        pin(
            f'2028 targets {preset} Senate Class 3',
            f'tiered_2026.targets_2028_{preset}_senate_class3',
            sum(1 for r in sen3_dem if r[f'tier_{preset}_2026'] == 'dirty'),
        )
    # Members whose tier turns on a net-negative AIPAC component (refunds).
    spot_fields = (
        'clean_2026',
        'corp_2026',
        'aipac_direct_2026',
        'dirty_2026',
        'aipac_udp_flag_2026',
        'tier_balanced_2026',
        'tier_lenient_2026',
    )
    for slug, name in (
        ('ryan', 'Patrick Ryan'),
        ('randall', 'Emily Randall'),
        ('garcia', 'Sylvia R. Garcia'),
    ):
        rec = next(r for r in records if r['full_name'] == name)
        pin(f'{name} tier spot case', f'spot.tier.{slug}', {f: rec[f] for f in spot_fields})

    # (e) 2026 columns, clean rule, dep_share
    opp = json.load(open(ROOT / CFG['paths']['opposition_computed']))
    race_map, by_cid = load_weball_2026_races()
    credit_2026 = {}
    for race, pk, _name, amount, _detail in opp['credit_detail']:
        if race[0] == CURRENT and not pk.startswith('__nonroster__'):
            # Sum across phases: one person can now be credited in two phases
            # of the same race (the race key includes ele_type).
            credit_2026[pk] = round(credit_2026.get(pk, 0.0) + float(amount), 2)
    oc_buckets_e = [
        'party_committees',
        'leadership_pacs',
        'labor_pacs',
        'trade_pacs',
        'membership_pacs',
        'cooperative_pacs',
        'other_unclassified',
    ]
    mism = 0
    for r in records:
        expect = {
            'individual_2026': cycle_sum(r['per_cycle'], 'individual'),
            'corp_2026': cycle_sum(r['per_cycle'], 'corporate_pac'),
            'aipac_direct_2026': cycle_sum(r['per_cycle'], 'aipac_pac_direct'),
            'udp_support_2026': cycle_sum(r['udp_per_cycle'], 'udp_ie_support'),
            'udp_opp_credit_2026': credit_2026.get(r['person_key'], 0.0),
        }
        expect['udp_benefit_2026'] = round(
            expect['udp_support_2026'] + expect['udp_opp_credit_2026'], 2
        )
        expect['dirty_2026'] = round(
            expect['corp_2026'] + expect['aipac_direct_2026'] + expect['udp_benefit_2026'], 2
        )
        denom = expect['individual_2026'] + expect['corp_2026'] + expect['aipac_direct_2026']
        expect['dep_share_2026'] = (
            round((expect['corp_2026'] + expect['aipac_direct_2026']) / denom, 4)
            if denom > 0
            else None
        )
        sf26 = [e for e in r['self_funding_per_cycle'] if e['cycle'] == CURRENT]
        expect['self_funding_2026'] = (
            round(sum(e['candidate_contributions'] + e['candidate_loans'] for e in sf26), 2)
            if sf26
            else 0
        )
        expect['cand_loans_2026'] = cycle_sum(r['self_funding_per_cycle'], 'candidate_loans')
        expect['cand_contrib_2026'] = cycle_sum(
            r['self_funding_per_cycle'], 'candidate_contributions'
        )
        expect['total_receipts_2026'] = cycle_sum(r['self_funding_per_cycle'], 'total_receipts')
        expect['total_disbursements_2026'] = cycle_sum(
            r['self_funding_per_cycle'], 'total_disbursements'
        )
        expect['cash_on_hand_2026'] = (
            round(sum(e['cash_on_hand'] for e in sf26), 2) if sf26 else None
        )
        oc26 = [e for e in r['other_committees_per_cycle'] if e['cycle'] == CURRENT]
        expect['other_committees_total_2026'] = (
            round(sum(sum(e[b] for b in oc_buckets_e) for e in oc26), 2) if oc26 else 0
        )
        expect['all_ie_support_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_support')
        expect['all_ie_oppose_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_oppose')
        expect['all_ie_total_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_total')
        # Generalized linkage rule (see compute_2026.py): a tracked/UDP
        # 2026 entry, or a self-funding 2026 entry whose coverage end
        # date falls in calendar 2026.
        has_linkage = (
            any(e['cycle'] == CURRENT for e in r['per_cycle'])
            or any(e['cycle'] == CURRENT for e in r['udp_per_cycle'])
            or any(
                e['cycle'] == CURRENT and str(e.get('coverage_end_date', '')).endswith('/2026')
                for e in r['self_funding_per_cycle']
            )
        )
        # Unopposed rule (see compute_2026.py): every 2026 race the
        # person filed in has no OTHER candidate with receipts over $0.
        # False when they filed no 2026 candidacy at all.
        ids = set(r['fec_candidate_ids'] or [])
        races = sorted({by_cid[cid] for cid in ids if cid in by_cid})
        expect['unopposed_2026'] = bool(races) and all(
            not any(cid not in ids and receipts > 0 for cid, receipts in race_map.get(race, []))
            for race in races
        )
        # AIPAC/UDP flag (always on): any AIPAC direct dollar or UDP
        # benefit dollar flags the member under every preset.
        expect['aipac_udp_flag_2026'] = bool(
            expect['aipac_direct_2026'] > 0 or expect['udp_benefit_2026'] > 0
        )
        # Net-negative clean rule: no NET dirty money (dirty_2026 <= 0)
        # reads clean; the unopposed test is the same net test.
        if r['in_120th'] == 'yes' and not has_linkage or expect['unopposed_2026'] and expect['dirty_2026'] <= 0:
            expect['clean_2026'] = None
        else:
            expect['clean_2026'] = expect['dirty_2026'] <= 0
        # Tolerance tiers (tier_for is defined in check (o) above).
        for preset in ('balanced', 'lenient'):
            expect[f'tier_{preset}_2026'] = tier_for(
                expect['clean_2026'],
                expect['aipac_udp_flag_2026'],
                expect['corp_2026'],
                expect['total_receipts_2026'],
                preset,
            )
        for k, v in expect.items():
            if r[k] != v:
                mism += 1
                if mism <= 5:
                    print(f'  2026 mismatch {r["person_key"]} {k}: {r[k]!r} != {v!r}')
    check(
        '2026 columns + clean rule + dep_share recompute exactly', mism == 0, f'{mism} mismatches'
    )

    # (m) clean-rule spot cases (methodology §14).
    def sf26_view(rec):
        return [
            {'coverage_end_date': e['coverage_end_date'], 'candidate_loans': e['candidate_loans']}
            for e in rec['self_funding_per_cycle']
            if e['cycle'] == CURRENT
        ]

    const = by_key['anthonyconstantinonyhouse']
    pin(
        'Constantino clean-rule spot case',
        'spot.clean.constantino',
        {
            'clean_2026': const['clean_2026'],
            'self_funding_2026_rows': sf26_view(const),
            'all_ie_support_2026': const['all_ie_support_2026'],
            'all_ie_oppose_2026': const['all_ie_oppose_2026'],
        },
    )
    luria = by_key['L000591']
    pin(
        'Luria clean-rule spot case',
        'spot.clean.luria',
        {
            'clean_2026': luria['clean_2026'],
            'self_funding_2026_rows': sf26_view(luria),
            'other_committees_total_2026': luria['other_committees_total_2026'],
            'all_ie_support_2026': luria['all_ie_support_2026'],
        },
    )
    check(
        'Luria: real 2026 campaign ID H6VA02198 is still not linked in the roster',
        'H6VA02198' not in luria['fec_candidate_ids'],
    )

    # (m) unopposed exclusion.
    unopposed = sorted(r['person_key'] for r in records if r['unopposed_2026'] is True)
    pin('members unopposed in 2026', 'spot.unopposed_2026', unopposed)
    pin(
        'members with clean_2026 null (unverified or unopposed-and-not-dirty)',
        'spot.clean_2026_null',
        sorted(r['person_key'] for r in records if r['clean_2026'] is None),
    )
    check(
        'an unopposed member with no net dirty money is null, not clean',
        all(
            r['clean_2026'] is None
            for r in records
            if r['unopposed_2026'] is True and is_num(r['dirty_2026']) and r['dirty_2026'] <= 0
        ),
    )
    check(
        'UNOPPOSED note sits exactly on the unopposed members held null',
        all(
            ('UNOPPOSED' in r['data_notes'])
            == (r['unopposed_2026'] is True and r['clean_2026'] is None)
            for r in records
        ),
    )
    check(
        'UNVERIFIED note sits exactly on the null members who are not unopposed',
        all(
            ('UNVERIFIED' in r['data_notes'])
            == (r['clean_2026'] is None and r['unopposed_2026'] is not True)
            for r in records
        ),
    )
    king_hinds = by_key['K000404']
    check(
        'King-Hinds contested, not unopposed — MP race is district 01',
        king_hinds['unopposed_2026'] is False and 'UNOPPOSED' not in king_hinds['data_notes'],
        f'unopposed={king_hinds["unopposed_2026"]}',
    )

    # (n) senate_class: re-derived from the legislators yaml, independent
    # of build_roster.py — own latest Senate term's class field where
    # the person holds a seat into 2026, else the class of whoever held
    # that seat during 2026 (appointee/outgoing holder, same state).
    leg = yaml.safe_load(open(ROOT / CFG['paths']['source'] / 'legislators-current.yaml'))
    leg_terms = {
        e['id'].get('bioguide'): [t for t in e['terms'] if t.get('type') == 'sen'] for e in leg
    }
    cont_sen = {
        r['person_key'] for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate'
    }

    def rederive_class(r):
        if r['chamber_119'] != 'Senate' and r['chamber_120'] != 'Senate':
            return None
        own = [
            t for t in leg_terms.get(r['person_key'], []) if (t.get('end') or '') >= '2026-01-01'
        ]
        if own:
            return own[-1].get('class')
        holders = set()
        for e in leg:
            for t in e['terms']:
                if (
                    t.get('type') == 'sen'
                    and t.get('state') == r['state']
                    and (t.get('start') or '') <= '2026-12-31'
                    and (t.get('end') or '') >= '2026-01-01'
                    and e['id'].get('bioguide') not in cont_sen
                ):
                    holders.add(t.get('class'))
        return holders.pop() if len(holders) == 1 else None

    mism = sum(1 for r in records if rederive_class(r) != r['senate_class'])
    check(
        'senate_class re-derives from legislators-current.yaml (0 mismatches)',
        mism == 0,
        f'{mism} mismatches',
    )
    senators = [r for r in records if r['chamber_119'] == 'Senate' or r['chamber_120'] == 'Senate']
    sen_keys = {r['person_key'] for r in senators}
    check(
        'senate_class is None for all non-senators, 1/2/3 for all senators',
        all(r['senate_class'] is None for r in records if r['person_key'] not in sen_keys)
        and all(r['senate_class'] in (1, 2, 3) for r in senators),
        f'{len(senators)} senator rows',
    )
    s120 = [r for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate']
    cls = Counter(r['senate_class'] for r in s120)
    check(
        '120th senator class counts: C1 33 / C2 32 / C3 34',
        cls == {1: 33, 2: 32, 3: 34},
        f'got {dict(cls)}',
    )
    c3d = [r for r in s120 if r['party_120'] == 'Democrat' and r['senate_class'] == 3]
    check(
        'Class 3 Democrats in the 120th = 16',
        len(c3d) == 16,
        f'got {len(c3d)}: {[r["full_name"] for r in c3d]}',
    )
    by_name = {r['full_name']: r for r in records}
    spot = [
        ('Charles E. Schumer', 3),
        ('Mark Kelly', 3),
        ('Raphael G. Warnock', 3),
        ('Adam B. Schiff', 1),
        ('Andy Kim', 1),
        ('Jon Ossoff', 2),
        ('Sherrod Brown', 3),
        ('Ashley Moody', 3),
        ('Abdul El-Sayed', 2),
        ('Peggy Flanagan', 2),
        ('Annie Andrews', 2),
    ]
    bad = [
        (n, by_name[n]['senate_class'], want)
        for n, want in spot
        if by_name[n]['senate_class'] != want
    ]
    check(
        'senate_class spot cases (Schumer/Kelly/Warnock 3, Schiff/Kim 1, '
        'Ossoff/Brown/Moody 3/3/3, El-Sayed/Flanagan/Andrews 2)',
        bad == [],
        f'got {bad}',
    )

    # (f) opposition career columns
    mism = 0
    for r in numeric:
        credit = round(float(opp['credit_by_person'].get(r['person_key'], 0.0)), 2)
        if r['udp_ie_opposing_opponents_career'] != credit:
            mism += 1
        if r['udp_ie_total_benefit_career'] != round(r['udp_ie_support_career'] + credit, 2):
            mism += 1
    check(
        'opposition career columns recompute from opposition-computed.json',
        mism == 0,
        f'{mism} mismatches',
    )
    arm = by_key.get('A000383')
    check(
        'Armstrong opposition columns are null (money unknown)',
        arm is not None
        and arm['udp_ie_opposing_opponents_career'] is None
        and arm['udp_ie_total_benefit_career'] is None,
    )

    # (g) dedup audit
    dedup = json.load(open(ROOT / CFG['paths']['dedup_applied']))
    # money_per_cycle.json is a dict keyed by person_key.
    mpc_by_key = json.load(open(ROOT / CFG['paths']['money_per_cycle']))
    mism = 0
    total_corrected = Decimal('0')
    for entry in dedup:
        pk = entry['person_key']
        per_cycle = {(e['cycle'], e['candidate_id']): e for e in mpc_by_key[pk]['per_cycle']}
        for dropped_id in entry['dropped_ids']:
            e = per_cycle.get((entry['cycle'], dropped_id))
            if e is None or Decimal(e['individual']) != Decimal('0.00'):
                mism += 1
        kept = per_cycle.get((entry['cycle'], entry['kept_id']))
        if kept is None or Decimal(kept['individual']) != Decimal(entry['amount']):
            mism += 1
        total_corrected += Decimal(entry['amount'])
    check(
        'dedup applied: dropped copies are 0.00, kept copies match the record',
        mism == 0,
        f'{mism} mismatches',
    )
    check(
        'dedup total is $451,776,015.34',
        total_corrected == Decimal('451776015.34'),
        f'got {total_corrected}',
    )
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
            if k in (
                'per_cycle',
                'udp_per_cycle',
                'self_funding_per_cycle',
                'other_committees_per_cycle',
                'all_ie_per_cycle',
                'fec_candidate_ids',
            ):
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
    print(
        'Note: these audits check the dataset against its own definitions; '
        'they cannot catch a missing money dimension (see module docstring).'
    )


if __name__ == '__main__':
    main()

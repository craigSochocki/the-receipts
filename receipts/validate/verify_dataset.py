#!/usr/bin/env python3
"""Standing audits for the Congress money tracker dataset.

Usage:
    python3 receipts/validate/verify_dataset.py [--dataset-csv PATH] [--dataset-json PATH]

Exits non-zero on any mismatch, printing every failure. Every expected
figure comes from data/source/baseline.json; none is written here.

  (a) per-cycle sums reproduce every career column: dbt tests on the gold
      tables (dbt/tests/*_career_is_its_cycles.sql), run by the marts pass.
  (b) roster totals match the baseline to the cent; a person with no FEC
      candidate ID ("unknown" money) is left out of every sum.
  (c) every rank column recomputes exactly (competition ranking:
      rank = 1 + count of strictly greater values).
  (d) the clean counts match the baseline, including career-clean and the
      clean-in-2026-but-not-career-clean split.
  (e) every 2026 column, the clean rule and dep_share recompute exactly:
      the linkage rule, the unopposed flag recomputed from weball26, the
      unopposed nulling of would-be-clean verdicts, the net-negative rule,
      the AIPAC/UDP flag, both tolerance tiers, and the int/float split on
      empty 2026 sums.
  (f) the opposition career columns recompute from gold.opposition_credits.
  (g) dedup: dbt tests (double_counts_*.sql) on the store's double_counts
      table and gold.accepted_money_per_cycle.
  (h) CSV and JSON agree field by field (CSV floats by float value,
      clean_2026 by True/False/empty, dep_share by float value, the
      per-cycle lists by repr; all_ie_top_committees is JSON-only and
      skipped).
  (i) one row per person, unique person_keys, row order matches roster.json.
  (j) self-funding and topline: named spot cases match the baseline; debts
      owed to is null everywhere; a person with no FEC ID reads unknown,
      not zero.
  (k) other committees: a named case's current-cycle pas2 total, its
      residual against weball, and the note that states them. The
      corporate/AIPAC re-derivation is enforced by the other-committees step.
  (l) all-IE: roster cycle totals (from gold) match the baseline; the
      row-sum gap is exactly the blank-direction rows; top-committee lists
      are sorted, split correctly, and null for a person with no FEC ID.
      The UDP reconciliation is enforced by the all-IE step.
  (m) clean-rule spot cases from the baseline: a member verified clean
      with linkage evidence, a member left null because their real
      campaign is unlinked, and the unopposed members, who are null, not
      clean, while a member with a funded opponent stays verified-clean.
  (n) senate_class: re-derived from the legislators yaml (the Senate-term
      class field) for every row, and the class counts match the baseline.
  (o) tiered dirty rule (methodology §14): the AIPAC/UDP flag and both
      tolerance tiers recompute; the tier counts, corp-only splits and
      2028-target counts under each preset match the baseline.

Caveat (AGENTS.md §5): this verifies the dataset against its own
definitions. It cannot catch a missing dimension — e.g. the
self-funding blind spot (candidate loans and contributions were never
pulled, so no audit here would have flagged their absence). A new money
dimension needs a new audit, not just a re-run of this one.
"""

import argparse
from collections import Counter

import pandas as pd

from receipts.common.files import read_json, read_yaml
from receipts.common.settings import settings
from receipts.fec.weball import candidate_summaries
from receipts.store.read import connect
from receipts.validate.audit import Audit

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


class Published:
    """The published dataset as the audits read it: the JSON records and the CSV beside them."""

    def __init__(self, json_path, csv_path):
        self.records = read_json(json_path)
        self.by_key = {r['person_key']: r for r in self.records}
        self.with_known_money = [
            r for r in self.records if r['individual_contribution_total_career'] != 'unknown'
        ]
        self.csv_path = csv_path


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def competition_ranks(records, col):
    values = [r[col] for r in records if is_num(r[col])]
    return {
        r['person_key']: (None if not is_num(r[col]) else 1 + sum(1 for x in values if x > r[col]))
        for r in records
    }


def cycle_sum(entries, field):
    vals = [e[field] for e in entries if e['cycle'] == settings().cycles.current]
    return round(sum(vals), 2) if vals else 0


def opposition_credit(cycle=None):
    """Dollars of opposition credit per roster person, summed over phases (and cycles)."""
    with connect() as db:
        credits = db.execute(
            'SELECT credited_to, sum(credit) FROM gold.opposition_credits '
            "WHERE credited_to NOT LIKE '__nonroster__%' AND (? IS NULL OR cycle = ?) "
            'GROUP BY credited_to',
            [cycle, cycle],
        ).fetchall()
    return {person_key: cents / 100 for person_key, cents in credits}


def load_weball_2026_races():
    """2026 races from the FEC all-candidates file (weball26).

    Same rule as compute_2026.py, recomputed independently here:
    race_map maps (office, state, district) to [(candidate_id, total
    receipts)]; by_cid maps candidate_id to its race. The race comes from
    the filing's own row, not the roster district (MP delegate race is
    filed under district 01); the ID's H/S/P prefix is the office.
    """
    race_map = {}
    by_cid = {}
    for row in candidate_summaries(settings().paths.bulk, settings().cycles.current):
        try:
            receipts = float(row.total_receipts or 0)
        except ValueError:
            receipts = 0.0
        race = (row.candidate_id[0], row.office_state, row.office_district)
        race_map.setdefault(race, []).append((row.candidate_id, receipts))
        by_cid[row.candidate_id] = race
    return race_map, by_cid


def rows_and_order(audit, dataset):
    """(i) row count, uniqueness, order"""
    audit.check('row count is 664', len(dataset.records) == 664, f'got {len(dataset.records)}')
    audit.check('person_keys unique', len(dataset.by_key) == len(dataset.records))
    roster_keys = [
        r['person_key']
        for r in read_json(settings().paths.roster)
        if r['person_key'] != 'kristen-mcdonaldrivetmihouse'
    ]
    audit.check(
        'row order matches roster.json', [r['person_key'] for r in dataset.records] == roster_keys
    )


def self_funding(audit, dataset):
    """(j) self-funding spot cases; debts owed to is null. The per-cycle sums
    are dbt tests on the gold tables (dbt/tests/*_career_is_its_cycles.sql).
    """
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
        audit.pin(
            f'{name} self_funding_career',
            f'spot.self_funding_career.{pk}',
            dataset.by_key[pk]['self_funding_career'],
        )
    const = dataset.by_key['anthonyconstantinonyhouse']
    for col in (
        'total_receipts_career',
        'total_disbursements_career',
        'cash_on_hand_2026',
        'total_receipts_2026',
    ):
        audit.pin(f'Constantino {col}', f'spot.constantino.{col}', const[col])
    audit.check(
        'debts_owed_to_career is null for every numeric row',
        all(r['debts_owed_to_career'] is None for r in dataset.with_known_money),
    )
    arm = dataset.by_key.get('A000383')
    audit.check(
        'Armstrong new money columns are unknown, top committees null',
        arm is not None
        and arm['self_funding_career'] == 'unknown'
        and arm['other_committees_total_career'] == 'unknown'
        and arm['all_ie_total_career'] == 'unknown'
        and arm['all_ie_top_committees'] is None,
    )


def other_committees(audit, dataset):
    """(k) other committees: Lamb's 2026 pas2 total and its residual against weball."""
    oc_buckets = [
        'party_committees',
        'leadership_pacs',
        'labor_pacs',
        'trade_pacs',
        'membership_pacs',
        'cooperative_pacs',
        'other_unclassified',
    ]
    lamb = dataset.by_key['marklambazhouse']
    lamb_pc26 = [
        e for e in lamb['other_committees_per_cycle'] if e['cycle'] == settings().cycles.current
    ]
    lamb_total = round(sum(sum(e[b] for b in oc_buckets) for e in lamb_pc26), 2)
    audit.check(
        'Lamb 2026 other-committee column equals its per-cycle pas2 sum',
        lamb_total == lamb['other_committees_total_2026'],
        f'got {lamb_total}',
    )
    audit.pin(
        'Lamb 2026 other-committee pas2-derived total',
        'spot.lamb.other_committees_total_2026',
        lamb_total,
    )
    with connect() as db:
        lamb_weball, *_ = db.execute(
            'SELECT other_committee_contributions_cents FROM candidate_summaries '
            "WHERE candidate_id = 'H6AZ05265' AND cycle = ?",
            [settings().cycles.current],
        ).fetchone()
    lamb_residual = round(lamb_weball / 100 - lamb_total, 2)
    audit.pin(
        'Lamb 2026 weball-minus-pas2 residual', 'spot.lamb.weball_minus_pas2_2026', lamb_residual
    )
    audit.check(
        'Lamb data_notes states the current pas2 total and residual (or no note at zero)',
        ('PENDING RECONCILIATION' not in lamb['data_notes'])
        if lamb_residual == 0
        else (
            f'${lamb_total:,.2f} by pas2' in lamb['data_notes']
            and f'${lamb_residual:,.2f} residual' in lamb['data_notes']
        ),
        lamb['data_notes'][-260:],
    )


def all_ie(audit, dataset):
    """(l) all-IE: roster cycle totals; the blank-direction gap; top committees.
    The UDP 2024 reconciliation is enforced by the all-IE step itself.
    """
    with connect() as db:
        roster_ie_totals = db.execute(
            'SELECT cycle, sum(all_ie_total) FROM gold.all_ie_per_candidate_cycle '
            'WHERE is_roster GROUP BY cycle ORDER BY cycle'
        ).fetchall()
    for cycle, cents in roster_ie_totals:
        audit.pin(f'all-IE roster total {cycle}', f'all_ie_cycle_totals.{cycle}', cents / 100)
    nodir = round(
        sum(
            r['all_ie_total_career'] - r['all_ie_support_career'] - r['all_ie_oppose_career']
            for r in dataset.with_known_money
        ),
        2,
    )
    audit.pin(
        'all-IE row-sum gap (the blank-direction rows)', 'spot.all_ie_blank_direction_gap', nodir
    )
    mism = 0
    for r in dataset.with_known_money:
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
    audit.check(
        'all-IE top-committee lists sorted, split correctly, max 5', mism == 0, f'{mism} mismatches'
    )
    elsayed = next(r for r in dataset.with_known_money if 'El-Sayed' in r['full_name'])
    for col in ('all_ie_support_career', 'all_ie_oppose_career'):
        audit.pin(f'El-Sayed {col}', f'spot.elsayed.{col}', elsayed[col])


def roster_totals(audit, dataset):
    """(b) roster totals match methodology.md figures
    (None stocks — cash on hand / debts owed by for people with no
    weball rows at all — are skipped, exactly as the config totals
    were computed from the staged CSVs.)
    """
    for col in METHODOLOGY_TOTAL_COLS:
        total = round(sum(r[col] for r in dataset.with_known_money if r[col] is not None), 2)
        audit.pin(f'roster total {col}', f'methodology_totals.{col}', total)


def ranks_and_dirty(audit, dataset):
    """(c) rank columns recompute exactly"""
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
        for r in dataset.with_known_money
        if round(
            r['individual_contribution_total_career']
            + r['corporate_pac_career']
            + r['aipac_pac_direct_career'],
            2,
        )
        != r['total_accepted_career']
    )
    audit.check('total_accepted recomputes exactly', ta_mism == 0, f'{ta_mism} mismatches')
    # (c2) dirty_career recomputes exactly: corporate PAC + AIPAC
    # direct + UDP total benefit, career. Null only for Armstrong
    # (money unknown, not zero).
    dc_mism = 0
    for r in dataset.records:
        parts = [
            r['corporate_pac_career'],
            r['aipac_pac_direct_career'],
            r['udp_ie_total_benefit_career'],
        ]
        want = round(sum(parts), 2) if all(is_num(v) for v in parts) else None
        if r['dirty_career'] != want:
            dc_mism += 1
    audit.check(
        'dirty_career recomputes exactly (corp + AIPAC + UDP benefit)',
        dc_mism == 0,
        f'{dc_mism} mismatches',
    )
    audit.check(
        'dirty_career is null only for Armstrong',
        [r['person_key'] for r in dataset.records if r['dirty_career'] is None] == ['A000383'],
    )
    top_dirty = max(
        (r for r in dataset.records if is_num(r['dirty_career'])), key=lambda r: r['dirty_career']
    )
    audit.pin(
        'career dirty #1 (person, amount)',
        'spot.dirty_career_top',
        [top_dirty['person_key'], top_dirty['dirty_career']],
    )
    for rank_col, val_col in rank_defs:
        ranks = competition_ranks(dataset.records, val_col)
        mism = sum(1 for r in dataset.records if r[rank_col] != ranks[r['person_key']])
        audit.check(f'{rank_col} recomputes exactly', mism == 0, f'{mism} mismatches')


def clean_counts(audit, dataset):
    """(d) clean counts (baseline clean_2026.*)"""
    counts = {
        'true_total': sum(1 for r in dataset.records if r['clean_2026'] is True),
        'false_total': sum(1 for r in dataset.records if r['clean_2026'] is False),
        'null_total': sum(1 for r in dataset.records if r['clean_2026'] is None),
    }
    for key in ('true_total', 'false_total', 'null_total'):
        audit.pin(f'clean_2026 {key}', f'clean_2026.{key}', counts[key])
    house120 = [
        r for r in dataset.records if r['in_120th'] == 'yes' and r['chamber_120'] == 'House'
    ]
    house_clean = [r for r in house120 if r['clean_2026'] is True]
    audit.pin('120th House clean', 'clean_2026.house_120th_verified_clean', len(house_clean))
    for party in ('Democrat', 'Republican'):
        audit.pin(
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
    audit.pin('career-clean 120th House', 'clean_2026.house_120th_career_clean', len(career_clean))
    for party in ('Democrat', 'Republican'):
        audit.pin(
            f'career-clean 120th House {party}',
            f'clean_2026.house_120th_career_clean_{party.lower()}',
            sum(1 for r in career_clean if r['party_120'] == party),
        )
    career_keys = {r['person_key'] for r in career_clean}
    audit.pin(
        '2026-clean but not career-clean (120th House)',
        'clean_2026.house_120th_clean_2026_not_career_clean',
        sum(1 for r in house_clean if r['person_key'] not in career_keys),
    )


# The tier logic is re-derived from the config thresholds, independently of
# compute_2026.py (same definitions, separate code).
def corp_material(corp, total_receipts, preset):
    th = settings().verification.tolerance_presets[preset]
    if corp <= th.corp_amount:
        return False
    if (
        not isinstance(total_receipts, (int, float))
        or isinstance(total_receipts, bool)
        or total_receipts <= 0
    ):
        return False
    return corp / total_receipts > th.corp_share


def flag_for(aipac_direct, udp_benefit):
    """Any AIPAC direct dollar or UDP benefit dollar flags the member under every preset."""
    return bool(aipac_direct > 0 or udp_benefit > 0)


def tier_for(clean, flag, corp, total_receipts, preset):
    if clean is None:
        return None
    if flag or corp_material(corp, total_receipts, preset):
        return 'dirty'
    if corp > 0:
        return 'below_threshold'
    return 'clean'


def tiered_rule(audit, dataset):
    """(o) tiered dirty rule: flag, tiers, corp-only splits, targets."""
    r120 = [r for r in dataset.records if r['in_120th'] == 'yes']
    audit.pin(
        'aipac_udp_flag_2026 120th',
        'tiered_2026.aipac_udp_flag_120th',
        sum(1 for r in r120 if r['aipac_udp_flag_2026'] is True),
    )
    audit.pin(
        'aipac_udp_flag_2026 roster-wide',
        'tiered_2026.aipac_udp_flag_all',
        sum(1 for r in dataset.records if r['aipac_udp_flag_2026'] is True),
    )
    audit.check(
        'aipac_udp_flag_2026 is a boolean on every row',
        all(r['aipac_udp_flag_2026'] in (True, False) for r in dataset.records),
    )
    for preset in ('balanced', 'lenient'):
        got = Counter(r[f'tier_{preset}_2026'] for r in r120)
        for tier_name in ('clean', 'below_threshold', 'dirty'):
            audit.pin(
                f'tier_{preset}_2026 {tier_name}',
                f'tiered_2026.{preset}.{tier_name}',
                got.get(tier_name, 0),
            )
        audit.pin(f'tier_{preset}_2026 null', f'tiered_2026.{preset}.null', got.get(None, 0))
        audit.pin(
            f'tier_{preset}_2026 not-dirty (clean + below_threshold)',
            f'tiered_2026.{preset}.not_dirty',
            got.get('clean', 0) + got.get('below_threshold', 0),
        )
        # Tier nulls coincide exactly with clean_2026 nulls.
        audit.check(
            f'tier_{preset}_2026 is null exactly where clean_2026 is null',
            all(
                (r[f'tier_{preset}_2026'] is None) == (r['clean_2026'] is None)
                for r in dataset.records
            ),
        )
        # Monotonicity: a Strict-clean member is never dirty under a
        # looser preset (a looser preset only relaxes the corp rule).
        audit.check(
            f'no Strict-clean member is dirty under {preset}',
            all(
                r[f'tier_{preset}_2026'] != 'dirty'
                for r in dataset.records
                if r['clean_2026'] is True
            ),
        )
        # The flag takes precedence: every flagged member is dirty
        # under every preset.
        audit.check(
            f'every flagged member is dirty under {preset}',
            all(
                r[f'tier_{preset}_2026'] == 'dirty'
                for r in dataset.records
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
    audit.pin('corp-only members in the 120th', 'tiered_2026.corp_only_2026_120th', len(corp_only))
    for preset in ('balanced', 'lenient'):
        staying = sum(
            1 for r in corp_only if corp_material(r['corp_2026'], r['total_receipts_2026'], preset)
        )
        audit.pin(
            f'corp-only staying dirty under {preset}',
            f'tiered_2026.corp_only_staying_dirty_{preset}',
            staying,
        )
        audit.pin(
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
    audit.pin(
        '2028 targets Strict House',
        'tiered_2026.targets_2028_strict_house',
        sum(1 for r in house_dem if r['dirty_2026'] > 0),
    )
    audit.pin(
        '2028 targets Strict Senate Class 3',
        'tiered_2026.targets_2028_strict_senate_class3',
        sum(1 for r in sen3_dem if r['dirty_2026'] > 0),
    )
    for preset in ('balanced', 'lenient'):
        audit.pin(
            f'2028 targets {preset} House',
            f'tiered_2026.targets_2028_{preset}_house',
            sum(1 for r in house_dem if r[f'tier_{preset}_2026'] == 'dirty'),
        )
        audit.pin(
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
        rec = next(r for r in dataset.records if r['full_name'] == name)
        audit.pin(f'{name} tier spot case', f'spot.tier.{slug}', {f: rec[f] for f in spot_fields})


def columns_2026(audit, dataset):
    """(e) 2026 columns, clean rule, dep_share"""
    race_map, by_cid = load_weball_2026_races()
    credit_2026 = opposition_credit(cycle=settings().cycles.current)
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
    for r in dataset.records:
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
        sf26 = [e for e in r['self_funding_per_cycle'] if e['cycle'] == settings().cycles.current]
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
        oc26 = [
            e for e in r['other_committees_per_cycle'] if e['cycle'] == settings().cycles.current
        ]
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
            any(e['cycle'] == settings().cycles.current for e in r['per_cycle'])
            or any(e['cycle'] == settings().cycles.current for e in r['udp_per_cycle'])
            or any(
                e['cycle'] == settings().cycles.current
                and str(e.get('coverage_end_date', '')).endswith('/2026')
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
        expect['aipac_udp_flag_2026'] = flag_for(
            expect['aipac_direct_2026'], expect['udp_benefit_2026']
        )
        # Net-negative clean rule: no NET dirty money (dirty_2026 <= 0)
        # reads clean; the unopposed test is the same net test.
        if (
            r['in_120th'] == 'yes'
            and not has_linkage
            or expect['unopposed_2026']
            and expect['dirty_2026'] <= 0
        ):
            expect['clean_2026'] = None
        else:
            expect['clean_2026'] = expect['dirty_2026'] <= 0
        # Tolerance tiers.
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
    audit.check(
        '2026 columns + clean rule + dep_share recompute exactly', mism == 0, f'{mism} mismatches'
    )


def clean_spot_cases(audit, dataset):
    """(m) clean-rule spot cases (methodology §14)."""

    def sf26_view(rec):
        return [
            {'coverage_end_date': e['coverage_end_date'], 'candidate_loans': e['candidate_loans']}
            for e in rec['self_funding_per_cycle']
            if e['cycle'] == settings().cycles.current
        ]

    const = dataset.by_key['anthonyconstantinonyhouse']
    audit.pin(
        'Constantino clean-rule spot case',
        'spot.clean.constantino',
        {
            'clean_2026': const['clean_2026'],
            'self_funding_2026_rows': sf26_view(const),
            'all_ie_support_2026': const['all_ie_support_2026'],
            'all_ie_oppose_2026': const['all_ie_oppose_2026'],
        },
    )
    luria = dataset.by_key['L000591']
    audit.pin(
        'Luria clean-rule spot case',
        'spot.clean.luria',
        {
            'clean_2026': luria['clean_2026'],
            'self_funding_2026_rows': sf26_view(luria),
            'other_committees_total_2026': luria['other_committees_total_2026'],
            'all_ie_support_2026': luria['all_ie_support_2026'],
        },
    )
    audit.check(
        'Luria: real 2026 campaign ID H6VA02198 is still not linked in the roster',
        'H6VA02198' not in luria['fec_candidate_ids'],
    )


def unopposed(audit, dataset):
    """(m) unopposed exclusion."""
    unopposed = sorted(r['person_key'] for r in dataset.records if r['unopposed_2026'] is True)
    audit.pin('members unopposed in 2026', 'spot.unopposed_2026', unopposed)
    audit.pin(
        'members with clean_2026 null (unverified or unopposed-and-not-dirty)',
        'spot.clean_2026_null',
        sorted(r['person_key'] for r in dataset.records if r['clean_2026'] is None),
    )
    audit.check(
        'an unopposed member with no net dirty money is null, not clean',
        all(
            r['clean_2026'] is None
            for r in dataset.records
            if r['unopposed_2026'] is True and is_num(r['dirty_2026']) and r['dirty_2026'] <= 0
        ),
    )
    audit.check(
        'UNOPPOSED note sits exactly on the unopposed members held null',
        all(
            ('UNOPPOSED' in r['data_notes'])
            == (r['unopposed_2026'] is True and r['clean_2026'] is None)
            for r in dataset.records
        ),
    )
    audit.check(
        'UNVERIFIED note sits exactly on the null members who are not unopposed',
        all(
            ('UNVERIFIED' in r['data_notes'])
            == (r['clean_2026'] is None and r['unopposed_2026'] is not True)
            for r in dataset.records
        ),
    )
    king_hinds = dataset.by_key['K000404']
    audit.check(
        'King-Hinds contested, not unopposed — MP race is district 01',
        king_hinds['unopposed_2026'] is False and 'UNOPPOSED' not in king_hinds['data_notes'],
        f'unopposed={king_hinds["unopposed_2026"]}',
    )


def senate_class(audit, dataset):
    """(n) senate_class: re-derived from the legislators yaml, independent
    of build_roster.py — own latest Senate term's class field where
    the person holds a seat into 2026, else the class of whoever held
    that seat during 2026 (appointee/outgoing holder, same state).
    """
    leg = read_yaml(settings().paths.source / 'legislators-current.yaml')
    leg_terms = {
        e['id'].get('bioguide'): [t for t in e['terms'] if t.get('type') == 'sen'] for e in leg
    }
    cont_sen = {
        r['person_key']
        for r in dataset.records
        if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate'
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

    mism = sum(1 for r in dataset.records if rederive_class(r) != r['senate_class'])
    audit.check(
        'senate_class re-derives from legislators-current.yaml (0 mismatches)',
        mism == 0,
        f'{mism} mismatches',
    )
    senators = [
        r for r in dataset.records if r['chamber_119'] == 'Senate' or r['chamber_120'] == 'Senate'
    ]
    sen_keys = {r['person_key'] for r in senators}
    audit.check(
        'senate_class is None for all non-senators, 1/2/3 for all senators',
        all(r['senate_class'] is None for r in dataset.records if r['person_key'] not in sen_keys)
        and all(r['senate_class'] in (1, 2, 3) for r in senators),
        f'{len(senators)} senator rows',
    )
    s120 = [r for r in dataset.records if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate']
    cls = Counter(r['senate_class'] for r in s120)
    audit.check(
        '120th senator class counts: C1 33 / C2 32 / C3 34',
        cls == {1: 33, 2: 32, 3: 34},
        f'got {dict(cls)}',
    )
    c3d = [r for r in s120 if r['party_120'] == 'Democrat' and r['senate_class'] == 3]
    audit.check(
        'Class 3 Democrats in the 120th = 16',
        len(c3d) == 16,
        f'got {len(c3d)}: {[r["full_name"] for r in c3d]}',
    )
    by_name = {r['full_name']: r for r in dataset.records}
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
    audit.check(
        'senate_class spot cases (Schumer/Kelly/Warnock 3, Schiff/Kim 1, '
        'Ossoff/Brown/Moody 3/3/3, El-Sayed/Flanagan/Andrews 2)',
        bad == [],
        f'got {bad}',
    )


def opposition(audit, dataset):
    """(f) opposition career columns"""
    career_credit = opposition_credit()
    mism = 0
    for r in dataset.with_known_money:
        credit = career_credit.get(r['person_key'], 0.0)
        if r['udp_ie_opposing_opponents_career'] != credit:
            mism += 1
        if r['udp_ie_total_benefit_career'] != round(r['udp_ie_support_career'] + credit, 2):
            mism += 1
    audit.check(
        'opposition career columns recompute from gold.opposition_credits',
        mism == 0,
        f'{mism} mismatches',
    )
    arm = dataset.by_key.get('A000383')
    audit.check(
        'Armstrong opposition columns are null (money unknown)',
        arm is not None
        and arm['udp_ie_opposing_opponents_career'] is None
        and arm['udp_ie_total_benefit_career'] is None,
    )


def csv_matches_json(audit, dataset):
    """(h) CSV <-> JSON agreement"""
    df = pd.read_csv(dataset.csv_path, dtype=str, keep_default_na=False)
    audit.check('CSV has 664 data rows', len(df) == 664, f'got {len(df)}')
    csv_by_key = {row['person_key']: row for _, row in df.iterrows()}
    audit.check('CSV person_keys match JSON', set(csv_by_key) == set(dataset.by_key))
    mism = 0
    json_keys = settings().dataset.json_keys
    for pk, r in dataset.by_key.items():
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
    audit.check('CSV and JSON agree field by field', mism == 0, f'{mism} mismatches')


SECTIONS = [
    rows_and_order,
    self_funding,
    other_committees,
    all_ie,
    roster_totals,
    ranks_and_dirty,
    clean_counts,
    tiered_rule,
    columns_2026,
    clean_spot_cases,
    unopposed,
    senate_class,
    opposition,
    csv_matches_json,
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dataset-csv', default=settings().paths.dataset_csv)
    ap.add_argument('--dataset-json', default=settings().paths.dataset_json)
    args = ap.parse_args()

    audit = Audit()
    dataset = Published(settings().root / args.dataset_json, settings().root / args.dataset_csv)
    for section in SECTIONS:
        section(audit, dataset)
    audit.finish(
        'VERIFY PASSED: all standing audits clean.\n'
        'Note: these audits check the dataset against its own definitions; '
        'they cannot catch a missing money dimension (see module docstring).'
    )


if __name__ == '__main__':
    main()

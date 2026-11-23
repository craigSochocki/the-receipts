#!/usr/bin/env python3
"""2026-cycle columns, the clean verdict and tiers, and the primary-target list.

Adds the 2026 columns to the base rows from assemble.py, applies the rules in
domain/clean_2026.py, checks the counts against data/source/baseline.json, and
writes data/intermediate/primary-targets.md. Every column and rule, with its
history and named cases, is defined in methodology.md §14.
"""

from collections import Counter

from receipts.common.baseline import expected
from receipts.common.settings import settings
from receipts.domain.clean_2026 import (
    NO_INDIVIDUAL_MONEY_NOTE,
    UNLINKED_NOTE,
    UNOPPOSED,
    UNOPPOSED_NOTE,
    aipac_udp_flagged,
    is_primary_target_2026,
    race_label,
    races_and_unopposed,
    tier,
    verdict,
)
from receipts.domain.committee_classes import OTHER_COMMITTEE_CLASSES
from receipts.store.races import races_in
from receipts.store.read import connect

BUCKETS = [c.value for c in OTHER_COMMITTEE_CLASSES]
CREDITS = (
    'SELECT credited_to, SUM(credit) FROM gold.opposition_credits '
    "WHERE cycle = ? AND credited_to NOT LIKE '__nonroster__%' GROUP BY credited_to"
)


def current(entries):
    return [e for e in entries if e['cycle'] == settings().cycles.current]


def current_sum(entries, field):
    """The 2026 total of a per-cycle field: int 0 when there is no 2026 entry at all."""
    found = current(entries)
    return round(sum(e[field] for e in found), 2) if found else 0


def has_2026_linkage(r):
    """2026 data in any money source: committee money, UDP, or a 2026 weball summary."""
    return (
        bool(current(r['per_cycle']))
        or bool(current(r['udp_per_cycle']))
        or any(
            str(e.get('coverage_end_date', '')).endswith(f'/{settings().cycles.current}')
            for e in current(r['self_funding_per_cycle'])
        )
    )


def money_2026(r, credit):
    pc, sf, oc, ie = (r[k] for k in ('per_cycle', 'self_funding_per_cycle',
                                     'other_committees_per_cycle', 'all_ie_per_cycle'))  # fmt: skip
    m = {
        'individual_2026': current_sum(pc, 'individual'),
        'corp_2026': current_sum(pc, 'corporate_pac'),
        'aipac_direct_2026': current_sum(pc, 'aipac_pac_direct'),
        'udp_support_2026': current_sum(r['udp_per_cycle'], 'udp_ie_support'),
        'udp_opp_credit_2026': credit,
    }
    m['udp_benefit_2026'] = round(m['udp_support_2026'] + credit, 2)
    m['dirty_2026'] = round(m['corp_2026'] + m['aipac_direct_2026'] + m['udp_benefit_2026'], 2)
    m['aipac_udp_flag_2026'] = aipac_udp_flagged(m['aipac_direct_2026'], m['udp_benefit_2026'])
    accepted = m['individual_2026'] + m['corp_2026'] + m['aipac_direct_2026']
    dirty_accepted = m['corp_2026'] + m['aipac_direct_2026']
    m['dep_share_2026'] = round(dirty_accepted / accepted, 4) if accepted > 0 else None
    sf26, oc26 = current(sf), current(oc)
    m['self_funding_2026'] = (
        round(sum(e['candidate_contributions'] + e['candidate_loans'] for e in sf26), 2)
        if sf26 else 0
    )  # fmt: skip
    for column, field in [('cand_loans_2026', 'candidate_loans'),
                          ('cand_contrib_2026', 'candidate_contributions'),
                          ('total_receipts_2026', 'total_receipts'),
                          ('total_disbursements_2026', 'total_disbursements')]:  # fmt: skip
        m[column] = current_sum(sf, field)
    m['cash_on_hand_2026'] = round(sum(e['cash_on_hand'] for e in sf26), 2) if sf26 else None
    m['other_committees_total_2026'] = (
        round(sum(sum(e[b] for b in BUCKETS) for e in oc26), 2) if oc26 else 0
    )
    for column, field in [('all_ie_support_2026', 'all_ie_support'),
                          ('all_ie_oppose_2026', 'all_ie_oppose'),
                          ('all_ie_total_2026', 'all_ie_total')]:  # fmt: skip
        m[column] = current_sum(ie, field)
    return m


def verdict_and_notes(r, race_map, race_of):
    races, unopposed = races_and_unopposed(r['fec_candidate_ids'] or [], race_map, race_of)
    r['unopposed_2026'] = bool(races) and len(unopposed) == len(races)
    linked = has_2026_linkage(r)
    r['clean_2026'], unknown_because = verdict(
        r['in_120th'] == 'yes', linked, r['unopposed_2026'], r['dirty_2026']
    )
    if r['clean_2026'] is None:
        note = (UNOPPOSED_NOTE.format(race=', '.join(race_label(x) for x in unopposed))
                if unknown_because == UNOPPOSED else UNLINKED_NOTE)  # fmt: skip
        r['data_notes'] += note
    for preset in ('balanced', 'lenient'):
        r[f'tier_{preset}_2026'] = tier(r['clean_2026'], r['aipac_udp_flag_2026'], r['corp_2026'],
                                        r['total_receipts_2026'], settings().verification.tolerance_presets[preset])  # fmt: skip
    if r['corp_2026'] > 0 and r['individual_2026'] == 0:
        r['data_notes'] += NO_INDIVIDUAL_MONEY_NOTE.format(corp=f'{r["corp_2026"]:,.0f}')


def credits_2026():
    with connect() as db:
        return {
            key: cents / 100
            for key, cents in db.execute(CREDITS, [settings().cycles.current]).fetchall()
        }


def observed_counts(records):
    r120 = [r for r in records if r['in_120th'] == 'yes']
    house = [r for r in r120 if r['chamber_120'] == 'House']
    house_clean = [r for r in house if r['clean_2026'] is True]
    career_clean = [r for r in house if r['corporate_pac_career'] == 0
                    and r['aipac_pac_direct_career'] == 0 and r['udp_ie_support_career'] == 0]  # fmt: skip
    career_keys = {r['person_key'] for r in career_clean}
    found = {
        'clean_2026.true_total': sum(r['clean_2026'] is True for r in records),
        'clean_2026.false_total': sum(r['clean_2026'] is False for r in records),
        'clean_2026.null_total': sum(r['clean_2026'] is None for r in records),
        'clean_2026.house_120th_verified_clean': len(house_clean),
        'clean_2026.house_120th_career_clean': len(career_clean),
    }
    for party in ('Democrat', 'Republican'):
        found[f'clean_2026.house_120th_verified_clean_{party.lower()}'] = sum(
            r['party_120'] == party for r in house_clean)  # fmt: skip
        found[f'clean_2026.house_120th_career_clean_{party.lower()}'] = sum(
            r['party_120'] == party for r in career_clean)  # fmt: skip
    found['clean_2026.house_120th_clean_2026_not_career_clean'] = sum(
        r['person_key'] not in career_keys for r in house_clean)  # fmt: skip
    found['tiered_2026.aipac_udp_flag_all'] = sum(r['aipac_udp_flag_2026'] for r in records)
    found['tiered_2026.aipac_udp_flag_120th'] = sum(r['aipac_udp_flag_2026'] for r in r120)
    for preset in ('balanced', 'lenient'):
        tiers = Counter(r[f'tier_{preset}_2026'] for r in r120)
        for name in ('clean', 'below_threshold', 'dirty'):
            found[f'tiered_2026.{preset}.{name}'] = tiers.get(name, 0)
        found[f'tiered_2026.{preset}.null'] = tiers.get(None, 0)
        found[f'tiered_2026.{preset}.not_dirty'] = tiers.get('clean', 0) + tiers.get(
            'below_threshold', 0
        )
    return found


def check_against_baseline(records):
    for key, got in observed_counts(records).items():
        want = expected(key, got)
        if got != want:
            raise SystemExit(f'{key}: computed {got} != baseline {want}')


def write_primary_targets(records):
    targets = sorted(filter(is_primary_target_2026, records), key=lambda r: -r['dirty_2026'])
    lines = [
        '# Primary targets — House Democrats in the 120th Congress, by dirty money in 2026',
        '',
        f'Generated from the tracker dataset (data as of {settings().data_as_of}). '
        f'{len(targets)} House Democrats in the incoming 120th took dirty money in 2026 '
        f'(corporate PAC + AIPAC direct + UDP benefit). Dirty money is money from sources '
        f'other than individual contributors; individual contributions are not dirty money.',
        '',
        "A public-facing version of this list needs Craig's explicit go-ahead.",
        '',
        '| # | Name | District | Dirty 2026 | Corp PAC 2026 | AIPAC 2026 | UDP benefit 2026 | Individual 2026 |',
        '|---|------|----------|-----------:|--------------:|-----------:|-----------------:|---------------:|',
    ]
    lines += [
        f'| {i} | {r["full_name"]} | {r["state"]}-{r["district_120"]} | '
        f'${r["dirty_2026"]:,.2f} | ${r["corp_2026"]:,.2f} | '
        f'${r["aipac_direct_2026"]:,.2f} | ${r["udp_benefit_2026"]:,.2f} | '
        f'${r["individual_2026"]:,.2f} |'
        for i, r in enumerate(targets, 1)
    ]
    settings().paths.primary_targets.write_text('\n'.join(lines) + '\n')


def with_2026(records):
    """Add the 2026 columns, clean flags and tiers; check the counts; write the target list."""
    credits = credits_2026()
    race_map, race_of = races_in(settings().cycles.current)
    for r in records:
        r.update(money_2026(r, credits.get(r['person_key'], 0.0)))
        verdict_and_notes(r, race_map, race_of)
    check_against_baseline(records)
    write_primary_targets(records)
    return [{k: r[k] for k in settings().dataset.json_keys} for r in records]

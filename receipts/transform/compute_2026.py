#!/usr/bin/env python3
"""Per-cycle records, the current cycle's columns, verdicts and tiers, and the target list."""

from collections import Counter
from functools import cache

from receipts.common.baseline import expected
from receipts.common.settings import settings
from receipts.domain.clean_2026 import (
    NO_INDIVIDUAL_MONEY_NOTE,
    UNLINKED_NOTE,
    UNOPPOSED,
    UNOPPOSED_NOTE,
    aipac_udp_flagged,
    is_career_clean,
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
    'SELECT cycle, credited_to, SUM(credit) FROM gold.opposition_credits '
    "WHERE credited_to NOT LIKE '__nonroster__%' GROUP BY cycle, credited_to"
)
MONEY_LISTS = ('per_cycle', 'udp_per_cycle', 'self_funding_per_cycle',
               'other_committees_per_cycle', 'all_ie_per_cycle')  # fmt: skip


def in_cycle(entries, cycle):
    return [e for e in entries if e['cycle'] == cycle]


def cycle_sum(entries, field, cycle):
    """A per-cycle field's total in `cycle`: int 0 when the cycle has no entry at all."""
    found = in_cycle(entries, cycle)
    return round(sum(e[field] for e in found), 2) if found else 0


def has_linkage(r, cycle):
    """Data in `cycle` in any money source: committee money, UDP, or that cycle's weball summary."""
    return (
        bool(in_cycle(r['per_cycle'], cycle))
        or bool(in_cycle(r['udp_per_cycle'], cycle))
        or any(
            str(e.get('coverage_end_date', '')).endswith(f'/{cycle}')
            for e in in_cycle(r['self_funding_per_cycle'], cycle)
        )
    )


def has_2026_linkage(r):
    return has_linkage(r, settings().cycles.current)


def money_in(r, cycle, credit):
    """Every money field of one cycle, from the person's per-cycle lists."""
    pc, sf, oc, ie = (r[k] for k in MONEY_LISTS if k != 'udp_per_cycle')
    m = {
        'individual': cycle_sum(pc, 'individual', cycle),
        'corp': cycle_sum(pc, 'corporate_pac', cycle),
        'aipac_direct': cycle_sum(pc, 'aipac_pac_direct', cycle),
        'udp_support': cycle_sum(r['udp_per_cycle'], 'udp_ie_support', cycle),
        'udp_opp_credit': credit,
    }
    m['udp_benefit'] = round(m['udp_support'] + credit, 2)
    m['dirty'] = round(m['corp'] + m['aipac_direct'] + m['udp_benefit'], 2)
    m['aipac_udp_flag'] = aipac_udp_flagged(m['aipac_direct'], m['udp_benefit'])
    accepted = m['individual'] + m['corp'] + m['aipac_direct']
    m['dep_share'] = round((m['corp'] + m['aipac_direct']) / accepted, 4) if accepted > 0 else None
    sf_cycle, oc_cycle = in_cycle(sf, cycle), in_cycle(oc, cycle)
    m['self_funding'] = (
        round(sum(e['candidate_contributions'] + e['candidate_loans'] for e in sf_cycle), 2)
        if sf_cycle else 0
    )  # fmt: skip
    for key, field in [('cand_loans', 'candidate_loans'), ('cand_contrib', 'candidate_contributions'),
                       ('total_receipts', 'total_receipts'),
                       ('total_disbursements', 'total_disbursements')]:  # fmt: skip
        m[key] = cycle_sum(sf, field, cycle)
    m['cash_on_hand'] = round(sum(e['cash_on_hand'] for e in sf_cycle), 2) if sf_cycle else None
    m['other_committees_total'] = (
        round(sum(sum(e[b] for b in BUCKETS) for e in oc_cycle), 2) if oc_cycle else 0
    )
    for direction in ('support', 'oppose', 'total'):
        m[f'all_ie_{direction}'] = cycle_sum(ie, f'all_ie_{direction}', cycle)
    return m


def judged(r, cycle, money, races):
    """The cycle's unopposed flag, clean verdict and tiers, with why a verdict is unknown."""
    race_map, race_of = races
    in_races, unopposed = races_and_unopposed(r['fec_candidate_ids'] or [], race_map, race_of)
    is_unopposed = bool(in_races) and len(unopposed) == len(in_races)
    incoming = r['in_120th'] == 'yes' and cycle == settings().cycles.current
    clean, unknown_because = verdict(incoming, has_linkage(r, cycle), is_unopposed, money['dirty'])
    presets = settings().verification.tolerance_presets
    tiers = {
        f'tier_{p}': tier(clean, money['aipac_udp_flag'], money['corp'],
                          money['total_receipts'], presets[p])
        for p in ('balanced', 'lenient')
    }  # fmt: skip
    return {'clean': clean, 'unopposed': is_unopposed, **tiers}, unknown_because, unopposed


def cycle_fields():
    """The per-cycle field names, in the order of the current cycle's dataset columns."""
    suffix = f'_{settings().cycles.current}'
    return [k.removesuffix(suffix) for k in settings().dataset.json_keys if k.endswith(suffix)]


def cycles_of(r):
    """Every cycle with an entry in any money list, and always the current cycle."""
    found = {e['cycle'] for k in MONEY_LISTS for e in r[k]}
    return sorted(found | {settings().cycles.current})


def cycle_record(r, cycle, credit, races):
    money = money_in(r, cycle, credit)
    verdict_fields, unknown_because, unopposed = judged(r, cycle, money, races)
    fields = {**money, **verdict_fields}
    return {'cycle': cycle, **{k: fields[k] for k in cycle_fields()}}, unknown_because, unopposed


def add_notes(r, unknown_because, unopposed):
    current = settings().cycles.current
    if r[f'clean_{current}'] is None:
        note = (UNOPPOSED_NOTE.format(race=', '.join(race_label(x) for x in unopposed))
                if unknown_because == UNOPPOSED else UNLINKED_NOTE)  # fmt: skip
        r['data_notes'] += note
    if r[f'corp_{current}'] > 0 and r[f'individual_{current}'] == 0:
        r['data_notes'] += NO_INDIVIDUAL_MONEY_NOTE.format(corp=f'{r[f"corp_{current}"]:,.0f}')


def opposition_credits():
    """{(cycle, person_key): dollars} of UDP opposition credit."""
    with connect() as db:
        return {(cycle, key): cents / 100 for cycle, key, cents in db.execute(CREDITS).fetchall()}


def by_party(house_clean, career_clean):
    found = {}
    for party in ('Democrat', 'Republican'):
        found[f'clean_2026.house_120th_verified_clean_{party.lower()}'] = sum(
            r['party_120'] == party for r in house_clean
        )
        found[f'clean_2026.house_120th_career_clean_{party.lower()}'] = sum(
            r['party_120'] == party for r in career_clean
        )
    return found


def clean_counts(records):
    house = [r for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'House']
    house_clean = [r for r in house if r['clean_2026'] is True]
    career_clean = [r for r in house if is_career_clean(r)]
    career_keys = {r['person_key'] for r in career_clean}
    found = {
        'clean_2026.true_total': sum(r['clean_2026'] is True for r in records),
        'clean_2026.false_total': sum(r['clean_2026'] is False for r in records),
        'clean_2026.null_total': sum(r['clean_2026'] is None for r in records),
        'clean_2026.house_120th_verified_clean': len(house_clean),
        'clean_2026.house_120th_career_clean': len(career_clean),
        **by_party(house_clean, career_clean),
    }
    found['clean_2026.house_120th_clean_2026_not_career_clean'] = sum(
        r['person_key'] not in career_keys for r in house_clean
    )
    return found


def tier_counts(records):
    r120 = [r for r in records if r['in_120th'] == 'yes']
    found = {
        'tiered_2026.aipac_udp_flag_all': sum(r['aipac_udp_flag_2026'] for r in records),
        'tiered_2026.aipac_udp_flag_120th': sum(r['aipac_udp_flag_2026'] for r in r120),
    }
    for preset in ('balanced', 'lenient'):
        tiers = Counter(r[f'tier_{preset}_2026'] for r in r120)
        for name in ('clean', 'below_threshold', 'dirty'):
            found[f'tiered_2026.{preset}.{name}'] = tiers.get(name, 0)
        found[f'tiered_2026.{preset}.null'] = tiers.get(None, 0)
        found[f'tiered_2026.{preset}.not_dirty'] = tiers.get('clean', 0) + tiers.get(
            'below_threshold', 0
        )
    return found


def observed_counts(records):
    return {**clean_counts(records), **tier_counts(records)}


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


def add_cycle_records(records, credits, races_for):
    """Each record's per-cycle records, and the current cycle's as its dataset columns."""
    current = settings().cycles.current
    for r in records:
        r['cycles'] = []
        for cycle in cycles_of(r):
            record, unknown_because, unopposed = cycle_record(
                r, cycle, credits.get((cycle, r['person_key']), 0.0), races_for(cycle)
            )
            r['cycles'].append(record)
            if cycle == current:
                r.update({f'{k}_{current}': v for k, v in record.items() if k != 'cycle'})
                add_notes(r, unknown_because, unopposed)
    return records


def with_cycles(records):
    """Add the cycle records and columns; check the counts; write the target list."""
    races = cache(races_in)
    add_cycle_records(records, opposition_credits(), races)
    check_against_baseline(records)
    write_primary_targets(records)
    return [{k: r[k] for k in settings().dataset.json_keys} for r in records]

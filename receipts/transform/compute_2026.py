#!/usr/bin/env python3
"""Per-cycle records, the current cycle's columns, verdicts and tiers, and the target list."""

from functools import cache

from receipts.common.baseline import expected
from receipts.common.settings import settings
from receipts.domain.clean_2026 import (
    NO_INDIVIDUAL_MONEY_NOTE,
    UNLINKED_NOTE,
    UNOPPOSED,
    UNOPPOSED_NOTE,
    aipac_udp_flagged,
    race_label,
    races_and_unopposed,
    tier,
    verdict,
)
from receipts.domain.committee_classes import OTHER_COMMITTEE_CLASSES
from receipts.domain.seats import regular_senate_class
from receipts.domain.targets import latest_record, primary_targets
from receipts.domain.term import term_record
from receipts.store.races import races_in
from receipts.store.read import connect
from receipts.validate.audits.clean import clean_count_values
from receipts.validate.audits.tiers import tier_count_values

BUCKETS = [c.value for c in OTHER_COMMITTEE_CLASSES]
CANDIDACIES = 'SELECT DISTINCT candidate_id, cycle, election_year FROM candidacies'
HEADLINE = ('clean', 'dirty', 'tier_balanced', 'tier_lenient')
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
    clean, unknown_because = verdict(
        incoming, has_linkage(r, cycle), is_unopposed, money['dirty'], money['aipac_udp_flag']
    )
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


def cycle_record(r, cycle, credit, races, up):
    money = money_in(r, cycle, credit)
    verdict_fields, unknown_because, unopposed = judged(r, cycle, money, races)
    fields = {**money, **verdict_fields}
    record = {'cycle': cycle, **{k: fields[k] for k in cycle_fields()}}
    record['up_for_election'] = any(
        cycle in up.get((cid, cycle), ()) for cid in r['fec_candidate_ids'] or []
    )
    return record, unknown_because, unopposed


def seat_up_now(r, filed):
    """An incoming member's seat is up this cycle unless their filing is for a later election."""
    current = settings().cycles.current
    if r['in_120th'] != 'yes':
        return False
    ids = r['fec_candidate_ids'] or []
    if any(year > current for cid in ids for year in filed.get((cid, current), ())):
        return False
    if r['chamber_120'] == 'Senate':
        return r['senate_class'] == regular_senate_class(current)
    return True


def headline_record(r, filed):
    """The current cycle's record if the person or their seat is up in it, else the latest up."""
    current = settings().cycles.current
    up = [c for c in r['cycles'] if c['up_for_election']]
    now = [c for c in r['cycles'] if c['cycle'] == current]
    if now and (now[0]['up_for_election'] or seat_up_now(r, filed)):
        return now[0]
    return (up[-1:] or [None])[0]


def headline(r, filed):
    """The verdict on the latest election's cycle and every cycle since (methodology §14b)."""
    record = headline_record(r, filed)
    if record is None:
        return {'verdict_cycle': None, **dict.fromkeys(HEADLINE)}
    term = term_record(r['cycles'], record['cycle'])
    unlinked = record['clean'] is None and not record['unopposed']
    clean = (
        None
        if unlinked
        else verdict(False, True, term['unopposed'], term['dirty'], term['aipac_udp_flag'])[0]
    )
    presets = settings().verification.tolerance_presets
    return {
        'verdict_cycle': record['cycle'],
        'clean': clean,
        'dirty': term['dirty'],
        **{
            f'tier_{p}': tier(
                clean, term['aipac_udp_flag'], term['corp'], term['total_receipts'], presets[p]
            )
            for p in ('balanced', 'lenient')
        },
    }


def add_notes(r, unknown_because, unopposed):
    current = settings().cycles.current
    if r[f'clean_{current}'] is None:
        note = (UNOPPOSED_NOTE.format(race=', '.join(race_label(x) for x in unopposed))
                if unknown_because == UNOPPOSED else UNLINKED_NOTE)  # fmt: skip
        r['data_notes'] += note
    if r[f'corp_{current}'] > 0 and r[f'individual_{current}'] == 0:
        r['data_notes'] += NO_INDIVIDUAL_MONEY_NOTE.format(corp=f'{r[f"corp_{current}"]:,.0f}')


def filed_elections():
    """{(candidate ID, cycle): the election years the cycle's candidacies are filed for}."""
    filed = {}
    with connect() as db:
        for cid, cycle, year in db.execute(CANDIDACIES).fetchall():
            filed.setdefault((cid, cycle), set()).add(year)
    return filed


def opposition_credits():
    """{(cycle, person_key): dollars} of UDP opposition credit."""
    with connect() as db:
        return {(cycle, key): cents / 100 for cycle, key, cents in db.execute(CREDITS).fetchall()}


def check_against_baseline(records):
    """The build-time check, over the same counts the verify audits pin."""
    for key, got in {**clean_count_values(records), **tier_count_values(records)}.items():
        want = expected(key, got)
        if got != want:
            raise SystemExit(f'{key}: computed {got} != baseline {want}')


def write_primary_targets(records):
    """The next cycle's primary targets under the default (Balanced) preset."""
    cycle = settings().cycles.next
    targets = primary_targets(records, 'balanced', cycle)
    lines = [
        f'# Primary targets — {cycle}: incoming members, any party, by dirty money',
        '',
        f'Generated from the tracker dataset (data as of {settings().data_as_of}). '
        f'{len(targets)} incoming members whose seat is up in {cycle} took dirty money in '
        f'their latest election under the Balanced preset (corporate PAC + AIPAC direct + '
        f'UDP benefit). Individual contributions are not dirty money.',
        '',
        "A public-facing version of this list needs Craig's explicit go-ahead.",
        '',
        '| # | Name | Party | Seat | Election | Dirty | Corp PAC | AIPAC | UDP benefit | Individual |',
        '|---|------|-------|------|---------:|------:|---------:|------:|------------:|-----------:|',
    ]
    for i, r in enumerate(targets, 1):
        record = latest_record(r)
        lines.append(
            f'| {i} | {r["full_name"]} | {r["party_120"]} | {seat_label(r)} | {record["cycle"]} | '
            + ' | '.join(
                f'${record[k]:,.2f}'
                for k in ('dirty', 'corp', 'aipac_direct', 'udp_benefit', 'individual')
            )
            + ' |'
        )
    settings().paths.primary_targets.write_text('\n'.join(lines) + '\n')


def seat_label(r):
    return (
        f'{r["state"]}-{r["district_120"]}'
        if r['chamber_120'] == 'House'
        else f'{r["state"]} Senate'
    )


def add_cycle_records(records, credits, races_for, filed=None):
    """Per-cycle records, the current cycle's as dataset columns, and the headline verdict."""
    current = settings().cycles.current
    for r in records:
        r['cycles'] = []
        for cycle in cycles_of(r):
            record, unknown_because, unopposed = cycle_record(
                r, cycle, credits.get((cycle, r['person_key']), 0.0), races_for(cycle), filed or {}
            )
            r['cycles'].append(record)
            if cycle == current:
                r.update({f'{k}_{current}': record[k] for k in cycle_fields()})
                add_notes(r, unknown_because, unopposed)
        r.update(headline(r, filed or {}))
    return records


def with_cycles(records):
    """Add the cycle records and columns; check the counts; write the target list."""
    races = cache(races_in)
    add_cycle_records(records, opposition_credits(), races, filed_elections())
    check_against_baseline(records)
    write_primary_targets(records)
    return [{k: r[k] for k in settings().dataset.json_keys} for r in records]

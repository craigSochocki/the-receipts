#!/usr/bin/env python3
"""Contributions from every committee other than AIPAC and corporate PACs."""

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

from receipts.common.baseline import expected
from receipts.common.log import log, run
from receipts.common.settings import load_double_count_records, load_roster, settings
from receipts.domain.ledger import Ledger
from receipts.domain.money import Money
from receipts.domain.roster import Roster, candidate_ids
from receipts.square_one.corrected import API_CYCLES
from receipts.square_one.corrected import load as load_corrected
from receipts.store.gold import per_cycle_rows, write_gold
from receipts.store.other_committees_report import (
    AIPAC,
    BUCKETS,
    CORPORATE,
    WINRED_COLUMN,
    cycle_diagnostics,
    earmark,
    reconcile_cycle,
    roster_total,
    weball_other_committee_money,
    write_diagnostics,
)
from receipts.store.read import connect, for_candidates

LAMB_CANDIDATE, LAMB_CYCLE = 'H6AZ05265', 2026
WINRED_KIND = 'winred_conduit'


TRACKED_COLUMNS = BUCKETS + [AIPAC, CORPORATE]
LEDGER_COLUMNS = TRACKED_COLUMNS + [earmark(c) for c in TRACKED_COLUMNS] + [WINRED_COLUMN]


def money_by_class(db, roster_ids):
    return for_candidates(
        db,
        'SELECT candidate_id, cycle, committee_class, kind, amount_cents, '
        'earmark_cents FROM committee_money_by_class WHERE TRUE',
        roster_ids,
    )


def fill_ledger(rows):
    ledger = Ledger(LEDGER_COLUMNS)
    for candidate_id, cycle, column, kind, amount, earmarked in rows:
        ledger.add(candidate_id, cycle, column, Money(amount))
        ledger.add(candidate_id, cycle, earmark(column), Money(earmarked))
        if kind == WINRED_KIND and column not in (AIPAC, CORPORATE):
            ledger.add(candidate_id, cycle, WINRED_COLUMN, Money(amount))
    return ledger


def corrected_aipac_career(ledger, roster, corrected):
    """The AIPAC career total with 2022-2026 replaced by the corrected figures.

    Mirrors accepted_money's person rollup: each person's pas2 career
    total, minus their 2022-2026 pas2, plus their corrected Variant A
    figures for those cycles.
    """
    total = 0
    for person in roster.people:
        ids = candidate_ids(person)
        total += ledger.total(ids, settings().cycles.career, AIPAC).cents
        for cycle in API_CYCLES:
            total -= ledger.total(ids, [cycle], AIPAC).cents
            total += corrected.aipac_cents(person['person_key'], cycle) or 0
    return Money(total)


def cross_checks(ledger, roster, corrected):
    """Corporate and AIPAC re-derived here must match the store's accepted money to the cent."""

    def baseline_cents(column, recomputed):
        recorded = expected(f'methodology_totals.{column}', recomputed.cents / 100)
        return int(Decimal(str(recorded)) * 100)

    checked = {
        'corporate_pac_career': ledger.column_total(CORPORATE),
        'corporate_earmark_transmitted_career': ledger.column_total(earmark(CORPORATE)),
        'aipac_pac_direct_career': corrected_aipac_career(ledger, roster, corrected),
        'aipac_earmark_transmitted_career': ledger.column_total(earmark(AIPAC)),
    }
    return {
        column: (recomputed.cents, baseline_cents(column, recomputed))
        for column, recomputed in checked.items()
    }


def lamb_validation(db, ledger):
    by_bucket = {b: ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, b) for b in BUCKETS}
    pas2_total = Money.total(by_bucket.values())
    weball = weball_other_committee_money(db, LAMB_CYCLE, {LAMB_CANDIDATE}).get(LAMB_CANDIDATE)
    earmarked = {b: ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, earmark(b)) for b in BUCKETS}
    return {
        'candidate_id': LAMB_CANDIDATE,
        'cycle': LAMB_CYCLE,
        'pas2_breakdown_cents': {b: amount.cents for b, amount in by_bucket.items()},
        'pas2_earmark_transmitted_cents': {b: a.cents for b, a in earmarked.items() if a},
        'pas2_total_cents': pas2_total.cents,
        'pas2_corporate_cents': ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, CORPORATE).cents,
        'pas2_aipac_cents': ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, AIPAC).cents,
        'weball_other_pol_cmte_contrib_cents': weball.cents if weball is not None else None,
        'weball_minus_pas2_cents': (
            weball.cents - pas2_total.cents if weball is not None else None
        ),
    }


def notes_for(person, ledger, roster, other_total, winred):
    ids = candidate_ids(person)
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster')
    else:
        any_money = any(
            ledger.amount(candidate_id, cycle, column)
            for candidate_id in ids
            for cycle in settings().cycles.career
            for column in BUCKETS + [CORPORATE, AIPAC]
        )
        if not any_money:
            notes.append('no FEC activity found')
        elif not other_total:
            notes.append('FEC activity found; all other-committee totals zero')
    if roster.shared_id_note(person):
        notes.append(roster.shared_id_note(person))
    if winred:
        notes.append(f'other_unclassified includes WinRed conduit net {winred} (see diagnostics)')
    return ' | '.join(notes)


def career_row(person, ledger, roster):
    ids = candidate_ids(person)
    totals = {b: ledger.total(ids, settings().cycles.career, b) for b in BUCKETS}
    earmarks = {b: ledger.total(ids, settings().cycles.career, earmark(b)) for b in BUCKETS}
    other_total = Money.total(totals.values())
    winred = ledger.total(ids, settings().cycles.career, WINRED_COLUMN)

    def shown(amount):
        return str(amount) if ids else ''

    return {
        'person_key': person['person_key'],
        'full_name': person['full_name'],
        'fec_candidate_ids': ';'.join(ids),
        **{f'{b}_career': shown(totals[b]) for b in BUCKETS},
        'other_committees_total_career': shown(other_total),
        **{f'{b}_earmark_transmitted_career': shown(earmarks[b]) for b in BUCKETS},
        'data_notes': notes_for(person, ledger, roster, other_total, winred),
    }


def per_cycle_record(person, ledger):
    entries = []
    for cycle in settings().cycles.career:
        for candidate_id in candidate_ids(person):
            amounts = {b: ledger.amount(candidate_id, cycle, b) for b in BUCKETS}
            earmarks = {b: ledger.amount(candidate_id, cycle, earmark(b)) for b in BUCKETS}
            earmarks = {b: amount for b, amount in earmarks.items() if amount}
            if any(amounts.values()) or earmarks:
                entries.append(
                    {
                        'cycle': cycle,
                        'candidate_id': candidate_id,
                        **{b: str(amount) for b, amount in amounts.items()},
                        'earmark_transmitted': {b: str(amount) for b, amount in earmarks.items()},
                        'winred_included': str(ledger.amount(candidate_id, cycle, WINRED_COLUMN)),
                    }
                )
    return {
        'person_key': person['person_key'],
        'full_name': person['full_name'],
        'per_cycle': entries,
    }


def note_label(bucket):
    return bucket.removesuffix('_committees').removesuffix('_pacs').replace('_', '-')


def reconciliation_note(validation, coverage):
    residual = validation['weball_minus_pas2_cents']
    if residual == 0:
        return ''

    def usd(cents):
        return f'${cents / 100:,.2f}'

    def month_day(iso_date):
        date = datetime.strptime(str(iso_date), '%Y-%m-%d')
        return f'{date:%b} {date.day}'

    by_class = '; '.join(
        f'{note_label(bucket)} {usd(validation["pas2_breakdown_cents"][bucket])}'
        for bucket in BUCKETS
        if validation['pas2_breakdown_cents'][bucket]
    )
    cycle = validation['cycle']
    return (
        f'{cycle} PENDING RECONCILIATION: other-committee money in {cycle} is '
        f'{usd(validation["pas2_total_cents"])} by pas2 ({by_class}) '
        f'but weball col 26 (OTHER_POL_CMTE_CONTRIB) reports '
        f'{usd(validation["weball_other_pol_cmte_contrib_cents"])} — {usd(residual)} residual, '
        f'not reproducible from the staged bulk files (pas2 judged complete through '
        f'{month_day(coverage["committee_money_pas2"])}, weball through '
        f'{month_day(coverage["weball"])}). Do not adjust either figure.'
    )


def flat_entry(row):
    earmarks = row.pop('earmark_transmitted')
    return {**row, **{f'earmark_{b}': earmarks.get(b) for b in BUCKETS}}


def read_store(roster_ids, dedup_records):
    """(rows, ledger, per-cycle diagnostics, weball reconciliation, named-case validation)."""
    with connect() as db:
        rows = money_by_class(db, roster_ids)
        ledger = fill_ledger(rows)
        diagnostics = [
            cycle_diagnostics(db, c, roster_ids, ledger, rows) for c in settings().cycles.career
        ]
        reconciliation = [
            reconcile_cycle(db, c, roster_ids, ledger, dedup_records)
            for c in settings().cycles.career
        ]
        lamb = lamb_validation(db, ledger)
    return rows, ledger, diagnostics, reconciliation, lamb


def check_cross_checks(checks):
    for column, (recomputed, recorded) in checks.items():
        log.info(f'CHECK {column}: {"MATCH" if recomputed == recorded else "MISMATCH"}')
    if mismatched := [column for column, (got, want) in checks.items() if got != want]:
        raise SystemExit(f'other committees re-derive {mismatched} differently from the baseline')


def committees_by_person(roster, ledger, reconciliation_note_text):
    """(people rows, {person_key: per_cycle record}) for every roster person."""
    people = [
        {
            **row,
            'reconciliation_note': (
                reconciliation_note_text if LAMB_CANDIDATE in row['fec_candidate_ids'] else ''
            ),
        }
        for row in (career_row(person, ledger, roster) for person in roster.people)
    ]
    cycles = {p['person_key']: per_cycle_record(p, ledger) for p in roster.people}
    return people, cycles


def write(people, cycles):
    write_gold('other_committees_people', people, {c for c in people[0] if c.endswith('_career')})
    write_gold(
        'other_committees_per_cycle',
        [flat_entry(r) for r in per_cycle_rows(cycles)],
        {*BUCKETS, *(f'earmark_{b}' for b in BUCKETS), 'winred_included'},
    )


def main():
    roster = Roster(load_roster())
    roster_ids = {i for p in roster.people for i in candidate_ids(p)}
    rows, ledger, diagnostics, reconciliation, lamb = read_store(
        roster_ids, load_double_count_records()
    )
    checks = cross_checks(ledger, roster, load_corrected())
    check_cross_checks(checks)
    note = reconciliation_note(lamb, asdict(settings().verification.coverage_end))
    write(*committees_by_person(roster, ledger, note))
    write_diagnostics(roster, ledger, rows, diagnostics, reconciliation, lamb, checks)
    for bucket in BUCKETS:
        log.info(f'{f"TOTAL {bucket} career $:"} {roster_total(roster, ledger, bucket)}')


if __name__ == '__main__':
    run(main)

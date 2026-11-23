#!/usr/bin/env python3
"""Contributions from every committee other than AIPAC and corporate PACs.

Read from the store's committee_money_by_class view; classes are in
src/domain/committee_classes.py. Each class gets its own columns, never
blended into total_accepted. Also re-derives the corporate and AIPAC
totals as a cross-check, and reconciles against weball col 26.
Evidence and findings: research/other-committees-notes.md.
"""
import sys
from decimal import Decimal

import duckdb

from src.common.baseline import expected
from src.common.files import write_csv, write_json
from src.common.settings import (CAREER_CYCLES as CYCLES, PATHS,
                                 load_double_count_records, load_roster)
from src.domain.committee_classes import OTHER_COMMITTEE_CLASSES, CommitteeClass
from src.domain.ledger import Ledger
from src.domain.money import ZERO, Money
from src.domain.roster import Roster, candidate_ids

LAMB_CANDIDATE, LAMB_CYCLE = 'H6AZ05265', 2026
WINRED_KIND = 'winred_conduit'

BUCKETS = [c.value for c in OTHER_COMMITTEE_CLASSES]
AIPAC = CommitteeClass.AIPAC.value
CORPORATE = CommitteeClass.CORPORATE.value
WINRED_COLUMN = 'winred'
DEDUP_FINDING = (
    'dedup-applied.json corrects the WEBALL double-count (identical '
    'TTL_INDIV_CONTRIB repeated under a chamber-switcher\'s House and '
    'Senate IDs). It does NOT change any pas2-derived column in this '
    'script: pas2 is transaction-level, so per-ID amounts differ and '
    'there is no duplicate copy to drop — the same finding '
    'the double-count record notes for AIPAC/corporate. It DOES affect the '
    'weball side of the reconciliation: col 26 (OTHER_POL_CMTE_CONTRIB) '
    'is duplicated under both IDs the same way, so the reconciliation '
    'zeroes the dropped IDs\' col-26 copies (guarded by the same '
    'equality check the weball correction uses) and reports raw vs corrected '
    'residuals separately. No correction was invented for these columns.')


def earmark(column):
    return f'{column}_earmark'


TRACKED_COLUMNS = BUCKETS + [AIPAC, CORPORATE]
LEDGER_COLUMNS = TRACKED_COLUMNS + [earmark(c) for c in TRACKED_COLUMNS] + [WINRED_COLUMN]


def roster_rows(db, query, roster_ids, *params):
    return db.execute(query + ' AND list_contains(?, candidate_id)',
                      [*params, sorted(roster_ids)]).fetchall()


def money_by_class(db, roster_ids):
    return roster_rows(db, 'SELECT candidate_id, cycle, committee_class, kind, amount_cents, '
                           'earmark_cents FROM committee_money_by_class WHERE TRUE', roster_ids)


def fill_ledger(rows):
    ledger = Ledger(LEDGER_COLUMNS)
    for candidate_id, cycle, column, kind, amount, earmarked in rows:
        ledger.add(candidate_id, cycle, column, Money(amount))
        ledger.add(candidate_id, cycle, earmark(column), Money(earmarked))
        if kind == WINRED_KIND and column not in (AIPAC, CORPORATE):
            ledger.add(candidate_id, cycle, WINRED_COLUMN, Money(amount))
    return ledger


def unclassified_composition(rows, cycle=None):
    composition = {}
    for candidate_id, row_cycle, column, kind, amount, _ in rows:
        if column == CommitteeClass.UNCLASSIFIED.value and cycle in (None, row_cycle):
            composition[kind] = composition.get(kind, 0) + amount
    return dict(sorted(composition.items()))


FILE_READS = 'SELECT rows_read, malformed_rows FROM files_read WHERE file = ? AND cycle = ?'
EXCLUDED = """
    SELECT count(*), COALESCE(SUM(amount_cents), 0), count(DISTINCT committee_id)
    FROM committee_contributions AS money
    WHERE cycle = ? AND {condition}"""
REGISTERED = ('EXISTS (SELECT 1 FROM committees AS registry '
              'WHERE registry.committee_id = money.committee_id AND registry.cycle = money.cycle)')


def cycle_diagnostics(db, cycle, roster_ids, ledger, rows):
    def excluded(condition):
        return roster_rows(db, EXCLUDED.format(condition=condition), roster_ids, cycle)[0]

    cm_rows, cm_bad = db.execute(FILE_READS, ['cm', cycle]).fetchone()
    pas2_rows, pas2_bad = db.execute(FILE_READS, ['pas2', cycle]).fetchone()
    matched = excluded('TRUE')[0]
    voided_rows, voided_cents, _ = excluded("excluded_because = 'voided_earmark'")
    unregistered_rows, _, unregistered_committees = excluded(
        f"excluded_because IS DISTINCT FROM 'voided_earmark' AND NOT {REGISTERED}")
    dropped_rows, dropped_cents, _ = excluded(f"excluded_because = 'reported_again' AND {REGISTERED}")

    def kept(column):
        return Money.total(ledger.amount(c, cycle, column) for c in ledger.candidates_in(cycle))

    return {
        'cycle': cycle, 'cm_rows': cm_rows, 'cm_bad_fields': cm_bad,
        'pas2_rows': pas2_rows, 'pas2_bad_fields': pas2_bad,
        'pas2_matched_roster': matched,
        'cm_missing_committees': unregistered_committees,
        'cm_missing_rows': unregistered_rows,
        'dedup_dropped_rows': dropped_rows, 'dedup_dropped_cents': dropped_cents,
        'void_earmark_rows': voided_rows, 'void_earmark_cents': voided_cents,
        'kept_cents': {bucket: kept(bucket).cents for bucket in BUCKETS},
        'kept_earmark_cents': {bucket: kept(earmark(bucket)).cents for bucket in BUCKETS
                               if kept(earmark(bucket))},
        'kept_winred_cents': kept(WINRED_COLUMN).cents,
        'kept_corporate_cents': kept(CORPORATE).cents,
        'kept_corporate_earmark_cents': kept(earmark(CORPORATE)).cents,
        'kept_aipac_cents': kept(AIPAC).cents,
        'kept_aipac_earmark_cents': kept(earmark(AIPAC)).cents,
        'unclassified_composition_cents': unclassified_composition(rows, cycle),
    }


def cross_checks(ledger):
    """Corporate and AIPAC re-derived here must match the store's accepted money to the cent."""
    def baseline_cents(column, recomputed):
        recorded = expected(f'methodology_totals.{column}', recomputed.cents / 100)
        return int(Decimal(str(recorded)) * 100)

    checked = {
        'corporate_pac_career': ledger.column_total(CORPORATE),
        'corporate_earmark_transmitted_career': ledger.column_total(earmark(CORPORATE)),
        'aipac_pac_direct_career': ledger.column_total(AIPAC),
        'aipac_earmark_transmitted_career': ledger.column_total(earmark(AIPAC)),
    }
    return {column: (recomputed.cents, baseline_cents(column, recomputed))
            for column, recomputed in checked.items()}


def weball_other_committee_money(db, cycle, roster_ids):
    return {candidate_id: Money(cents) for candidate_id, cents in roster_rows(
        db, 'SELECT candidate_id, other_committee_contributions_cents FROM candidate_summaries '
            'WHERE cycle = ?', roster_ids, cycle)}


def without_double_counted_summaries(reported, dedup_records, cycle):
    """Zero the copies weball repeats under a chamber-switcher's second ID."""
    corrected, zeroed, mismatched = dict(reported), 0, 0
    for record in dedup_records:
        if record['cycle'] != cycle:
            continue
        for dropped_id in record['dropped_ids']:
            if dropped_id in corrected and record['kept_id'] in corrected:
                if corrected[dropped_id] == corrected[record['kept_id']]:
                    corrected[dropped_id] = ZERO
                    zeroed += 1
                else:
                    mismatched += 1
    return corrected, zeroed, mismatched


PARTY = CommitteeClass.PARTY.value
COL_26_COLUMNS = [b for b in BUCKETS if b != PARTY] + [CORPORATE, AIPAC]


def pas2_comparable(ledger, candidate_id, cycle):
    """What weball col 26 covers: committee money other than party (Form 3 line 11(c))."""
    columns = COL_26_COLUMNS
    gross = Money.total(ledger.amount(candidate_id, cycle, c) for c in columns)
    earmarked = Money.total(ledger.amount(candidate_id, cycle, earmark(c)) for c in columns)
    return gross, earmarked


def reconcile_cycle(db, cycle, roster_ids, ledger, dedup_records):
    raw = weball_other_committee_money(db, cycle, roster_ids)
    corrected, zeroed, mismatched = without_double_counted_summaries(raw, dedup_records, cycle)
    gross_total = earmark_total = party_total = ZERO
    residual_raw = residual_corrected = residual_net = 0
    exact_raw = exact_corrected = exact_net = considered = 0
    residuals = []
    for candidate_id in set(raw) | ledger.candidates_in(cycle):
        weball_raw = raw.get(candidate_id, ZERO).cents
        weball_corrected = corrected.get(candidate_id, ZERO).cents
        gross, earmarked = pas2_comparable(ledger, candidate_id, cycle)
        gross_total += gross
        earmark_total += earmarked
        party_total += ledger.amount(candidate_id, cycle, PARTY)
        net = gross.cents - earmarked.cents
        if not (weball_raw or gross):
            continue
        considered += 1
        residual_raw += weball_raw - gross.cents
        residual_corrected += weball_corrected - gross.cents
        residual_net += weball_corrected - net
        exact_raw += weball_raw == gross.cents
        exact_corrected += weball_corrected == gross.cents
        exact_net += weball_corrected == net
        residuals.append((weball_corrected - net, candidate_id, weball_corrected, net))

    def described(entries):
        return [{'candidate_id': c, 'residual_cents': r, 'weball_corrected_cents': w,
                 'pas2_net_cents': p} for r, c, w, p in entries[:5]]

    return {
        'cycle': cycle, 'candidates_with_weball_or_pas2': considered,
        'weball_other_pol_total_cents': Money.total(raw.values()).cents,
        'weball_corrected_total_cents': Money.total(corrected.values()).cents,
        'pas2_nonparty_gross_cents': gross_total.cents,
        'pas2_nonparty_net_of_earmarks_cents': gross_total.cents - earmark_total.cents,
        'pas2_earmark_transmitted_cents': earmark_total.cents,
        'pas2_party_committees_cents': party_total.cents,
        'residual_weball_raw_minus_pas2_gross_cents': residual_raw,
        'residual_weball_corrected_minus_pas2_gross_cents': residual_corrected,
        'residual_weball_corrected_minus_pas2_net_cents': residual_net,
        'exact_matches_raw': exact_raw, 'exact_matches_corrected': exact_corrected,
        'exact_matches_corrected_net': exact_net,
        'dedup_dropped_ids_zeroed': zeroed, 'dedup_dropped_ids_col26_mismatch': mismatched,
        'largest_positive_residuals': described(sorted(residuals, reverse=True)),
        'largest_negative_residuals': described(sorted(residuals)),
    }


def lamb_validation(db, ledger):
    by_bucket = {b: ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, b) for b in BUCKETS}
    pas2_total = Money.total(by_bucket.values())
    weball = weball_other_committee_money(db, LAMB_CYCLE, {LAMB_CANDIDATE}).get(LAMB_CANDIDATE)
    earmarked = {b: ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, earmark(b)) for b in BUCKETS}
    return {
        'candidate_id': LAMB_CANDIDATE, 'cycle': LAMB_CYCLE,
        'pas2_breakdown_cents': {b: amount.cents for b, amount in by_bucket.items()},
        'pas2_earmark_transmitted_cents': {b: a.cents for b, a in earmarked.items() if a},
        'pas2_total_cents': pas2_total.cents,
        'pas2_corporate_cents': ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, CORPORATE).cents,
        'pas2_aipac_cents': ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, AIPAC).cents,
        'weball_other_pol_cmte_contrib_cents': weball.cents if weball is not None else None,
        'weball_minus_pas2_cents': (weball.cents - pas2_total.cents
                                    if weball is not None else None),
    }


def notes_for(person, ledger, roster, other_total, winred):
    ids = candidate_ids(person)
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster')
    else:
        any_money = any(ledger.amount(candidate_id, cycle, column)
                        for candidate_id in ids for cycle in CYCLES
                        for column in BUCKETS + [CORPORATE, AIPAC])
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
    totals = {b: ledger.total(ids, CYCLES, b) for b in BUCKETS}
    earmarks = {b: ledger.total(ids, CYCLES, earmark(b)) for b in BUCKETS}
    other_total = Money.total(totals.values())
    winred = ledger.total(ids, CYCLES, WINRED_COLUMN)

    def shown(amount):
        return str(amount) if ids else ''

    return {'person_key': person['person_key'], 'full_name': person['full_name'],
            'fec_candidate_ids': ';'.join(ids),
            **{f'{b}_career': shown(totals[b]) for b in BUCKETS},
            'other_committees_total_career': shown(other_total),
            **{f'{b}_earmark_transmitted_career': shown(earmarks[b]) for b in BUCKETS},
            'data_notes': notes_for(person, ledger, roster, other_total, winred)}


def per_cycle_record(person, ledger):
    entries = []
    for cycle in CYCLES:
        for candidate_id in candidate_ids(person):
            amounts = {b: ledger.amount(candidate_id, cycle, b) for b in BUCKETS}
            earmarks = {b: ledger.amount(candidate_id, cycle, earmark(b)) for b in BUCKETS}
            earmarks = {b: amount for b, amount in earmarks.items() if amount}
            if any(amounts.values()) or earmarks:
                entries.append({
                    'cycle': cycle, 'candidate_id': candidate_id,
                    **{b: str(amount) for b, amount in amounts.items()},
                    'earmark_transmitted': {b: str(amount) for b, amount in earmarks.items()},
                    'winred_included': str(ledger.amount(candidate_id, cycle, WINRED_COLUMN))})
    return {'person_key': person['person_key'], 'full_name': person['full_name'],
            'per_cycle': entries}


def roster_total(roster, ledger, column):
    return Money.total(ledger.total(candidate_ids(p), CYCLES, column) for p in roster.people)


def main():
    roster = Roster(load_roster())
    roster_ids = {i for p in roster.people for i in candidate_ids(p)}
    dedup_records = load_double_count_records()
    with duckdb.connect(str(PATHS.store), read_only=True) as db:
        rows = money_by_class(db, roster_ids)
        ledger = fill_ledger(rows)
        diagnostics = [cycle_diagnostics(db, c, roster_ids, ledger, rows) for c in CYCLES]
        reconciliation = [reconcile_cycle(db, c, roster_ids, ledger, dedup_records)
                          for c in CYCLES]
        lamb = lamb_validation(db, ledger)
    checks = cross_checks(ledger)

    write_csv(PATHS.other_committees_csv,
              [career_row(person, ledger, roster) for person in roster.people])
    write_json(PATHS.other_committees_per_cycle,
               {p['person_key']: per_cycle_record(p, ledger) for p in roster.people})
    write_json(PATHS.other_committees_diagnostics, {
        'per_cycle': diagnostics,
        'unclassified_composition_career_cents': unclassified_composition(rows),
        'roster_totals_cents': {b: roster_total(roster, ledger, b).cents for b in BUCKETS},
        'roster_earmark_transmitted_cents': {
            b: roster_total(roster, ledger, earmark(b)).cents for b in BUCKETS},
        'roster_winred_included_cents': ledger.column_total(WINRED_COLUMN).cents,
        'cross_checks_vs_methodology': {
            column: {'recomputed_cents': a, 'methodology_cents': b, 'match': a == b}
            for column, (a, b) in checks.items()},
        'reconciliation_vs_weball_col26': reconciliation,
        'lamb_validation': lamb,
        'dedup_applied_finding': DEDUP_FINDING,
    })

    for bucket in BUCKETS:
        print(f'TOTAL {bucket} career $:', roster_total(roster, ledger, bucket))
    for column, (recomputed, recorded) in checks.items():
        print(f"CHECK {column}: {'MATCH' if recomputed == recorded else 'MISMATCH'}")
    if any(recomputed != recorded for recomputed, recorded in checks.values()):
        sys.exit('CROSS-CHECK FAILED: recomputed corporate/AIPAC totals do not match methodology totals')


if __name__ == '__main__':
    main()

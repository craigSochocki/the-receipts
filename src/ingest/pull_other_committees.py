#!/usr/bin/env python3
"""Contributions from every committee other than AIPAC and corporate PACs.

Reads pas2 + cm; classes are in src/domain/committee_classes.py. Each
class gets its own columns, never blended into total_accepted. Also
re-derives the corporate and AIPAC totals as a cross-check on
pull_money, and reconciles against weball col 26.
Evidence and findings: research/other-committees-notes.md.
"""
import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.baseline import expected
from src.common.config import load_config
from src.domain.committee_classes import (OTHER_COMMITTEE_CLASSES, CommitteeClass,
                                          committee_class, unclassified_kind)
from src.domain.committee_money import ReportedOnce, Tally, is_voided_earmark
from src.domain.ledger import Ledger
from src.domain.money import ZERO, Money
from src.domain.roster import Roster, candidate_ids
from src.fec.committee_contributions import committee_contributions
from src.fec.committees import committees
from src.fec.weball import candidate_summaries

CFG = load_config()
ROOT = CFG['_root']
INTERMEDIATE = ROOT / CFG['paths']['intermediate']
SOURCE = ROOT / CFG['paths']['source']
BULK = ROOT / CFG['paths']['bulk']
CYCLES = range(CFG['cycles']['career_start'], CFG['cycles']['career_end'] + 1, 2)
AIPAC_PAC = CFG['committees']['aipac_pac']
WINRED = CFG['committees']['winred']
LAMB_CANDIDATE, LAMB_CYCLE = 'H6AZ05265', 2026

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
    'apply_dedup.py records for AIPAC/corporate. It DOES affect the '
    'weball side of the reconciliation: col 26 (OTHER_POL_CMTE_CONTRIB) '
    'is duplicated under both IDs the same way, so the reconciliation '
    'zeroes the dropped IDs\' col-26 copies (guarded by the same '
    'equality check apply_dedup.py uses) and reports raw vs corrected '
    'residuals separately. No correction was invented for these columns.')


def earmark(column):
    return f'{column}_earmark'


TRACKED_COLUMNS = BUCKETS + [AIPAC, CORPORATE]
LEDGER_COLUMNS = TRACKED_COLUMNS + [earmark(c) for c in TRACKED_COLUMNS] + [WINRED_COLUMN]


def read_registry(cycle):
    registry = committees(BULK, cycle)
    by_id = {committee.committee_id: committee for committee in registry}
    return by_id, {'cm_rows': registry.rows_read, 'cm_bad_fields': registry.malformed_rows}


def read_cycle(cycle, roster, ledger, composition):
    registry, registry_counts = read_registry(cycle)
    filed = committee_contributions(BULK, cycle)
    reported_once = ReportedOnce()
    matched, voided, unregistered = 0, Tally(), Tally()
    unregistered_committees = set()

    for contribution in filed:
        if not contribution.is_to_candidate or contribution.candidate_id not in roster:
            continue
        matched += 1
        if is_voided_earmark(contribution):
            voided.add(contribution.amount)
            continue
        if contribution.committee_id not in registry:
            unregistered.add(ZERO)
            unregistered_committees.add(contribution.committee_id)
            continue
        reported_once.add(contribution)

    kept = {column: ZERO for column in BUCKETS + [AIPAC, CORPORATE, WINRED_COLUMN]}
    kept_earmarks = {column: ZERO for column in kept}
    cycle_composition = {}
    for contribution in reported_once:
        committee = registry[contribution.committee_id]
        column = committee_class(committee, AIPAC_PAC).value
        amount = contribution.amount
        ledger.add(contribution.candidate_id, cycle, column, amount)
        kept[column] += amount
        if contribution.is_earmark:
            ledger.add(contribution.candidate_id, cycle, earmark(column), amount)
            kept_earmarks[column] += amount
        if column in (AIPAC, CORPORATE):
            continue
        if committee.committee_id == WINRED:
            ledger.add(contribution.candidate_id, cycle, WINRED_COLUMN, amount)
            kept[WINRED_COLUMN] += amount
        if column == CommitteeClass.UNCLASSIFIED.value:
            kind = unclassified_kind(committee, WINRED)
            cycle_composition[kind] = cycle_composition.get(kind, ZERO) + amount

    for kind, amount in cycle_composition.items():
        composition[kind] = composition.get(kind, ZERO) + amount
    return {
        'cycle': cycle, **registry_counts,
        'pas2_rows': filed.rows_read, 'pas2_bad_fields': filed.malformed_rows,
        'pas2_matched_roster': matched,
        'cm_missing_committees': len(unregistered_committees),
        'cm_missing_rows': unregistered.rows,
        'dedup_dropped_rows': reported_once.dropped.rows,
        'dedup_dropped_cents': reported_once.dropped.amount.cents,
        'void_earmark_rows': voided.rows, 'void_earmark_cents': voided.amount.cents,
        'kept_cents': {bucket: kept[bucket].cents for bucket in BUCKETS},
        'kept_earmark_cents': {bucket: kept_earmarks[bucket].cents for bucket in BUCKETS
                               if kept_earmarks[bucket]},
        'kept_winred_cents': kept[WINRED_COLUMN].cents,
        'kept_corporate_cents': kept[CORPORATE].cents,
        'kept_corporate_earmark_cents': kept_earmarks[CORPORATE].cents,
        'kept_aipac_cents': kept[AIPAC].cents,
        'kept_aipac_earmark_cents': kept_earmarks[AIPAC].cents,
        'unclassified_composition_cents': {kind: amount.cents
                                           for kind, amount in cycle_composition.items()},
    }


def cross_checks(ledger):
    """Corporate and AIPAC re-derived here must match pull_money to the cent."""
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


def weball_other_committee_money(cycle, roster):
    return {summary.candidate_id: summary.amount('other_committee_contributions')
            for summary in candidate_summaries(BULK, cycle) if summary.candidate_id in roster}


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


def reconcile_cycle(cycle, roster, ledger, dedup_records):
    raw = weball_other_committee_money(cycle, roster)
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


def lamb_validation(ledger):
    by_bucket = {b: ledger.amount(LAMB_CANDIDATE, LAMB_CYCLE, b) for b in BUCKETS}
    pas2_total = Money.total(by_bucket.values())
    weball = next((summary.amount('other_committee_contributions')
                   for summary in candidate_summaries(BULK, LAMB_CYCLE)
                   if summary.candidate_id == LAMB_CANDIDATE), None)
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
    shared_with = roster.others_sharing_an_id_with(person)
    if shared_with:
        notes.append('duplicate roster entry: FEC ID shared with ' + ', '.join(shared_with))
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


def write_csv(name, rows):
    with open(INTERMEDIATE / name, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(name, content):
    with open(INTERMEDIATE / name, 'w') as f:
        json.dump(content, f, indent=1)


def main():
    with open(INTERMEDIATE / 'roster.json') as f:
        roster = Roster(json.load(f))
    with open(SOURCE / 'dedup-applied.json') as f:
        dedup_records = json.load(f)
    ledger = Ledger(LEDGER_COLUMNS)
    composition = {}

    diagnostics = [read_cycle(cycle, roster, ledger, composition) for cycle in CYCLES]
    checks = cross_checks(ledger)
    reconciliation = [reconcile_cycle(c, roster, ledger, dedup_records) for c in CYCLES]

    rows = [career_row(person, ledger, roster) for person in roster.people]
    write_csv('other_committees.csv', rows)
    write_json('other_committees_per_cycle.json',
               {p['person_key']: per_cycle_record(p, ledger) for p in roster.people})
    write_json('other_committees_diagnostics.json', {
        'per_cycle': diagnostics,
        'unclassified_composition_career_cents': {k: a.cents for k, a in composition.items()},
        'roster_totals_cents': {b: roster_total(roster, ledger, b).cents for b in BUCKETS},
        'roster_earmark_transmitted_cents': {
            b: roster_total(roster, ledger, earmark(b)).cents for b in BUCKETS},
        'roster_winred_included_cents': ledger.column_total(WINRED_COLUMN).cents,
        'cross_checks_vs_methodology': {
            column: {'recomputed_cents': a, 'methodology_cents': b, 'match': a == b}
            for column, (a, b) in checks.items()},
        'reconciliation_vs_weball_col26': reconciliation,
        'lamb_validation': lamb_validation(ledger),
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

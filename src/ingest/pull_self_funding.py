#!/usr/bin/env python3
"""Self-funding, topline and transfer columns from weball.

Separate columns, never blended into total_accepted. Flows are summed
across cycles; cash on hand and debts are stocks, taken from the latest
cycle. A person with no FEC IDs is unknown (null), never zero.
Column map, verification and the dedup decisions:
research/self-funding-notes.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.files import text_or_blank, text_or_none, write_csv, write_json
from src.common.settings import (CAREER_CYCLES as CYCLES, CURRENT_CYCLE, DATA_AS_OF, PATHS,
                                 load_double_count_records, load_roster)
from src.domain.campaign_finances import FLOWS, STOCKS, CampaignFinances
from src.domain.money import Money
from src.domain.roster import Roster, candidate_ids
from src.domain.weball_double_counts import FINANCIAL_FIELDS, remove_double_counts
from src.fec.weball import CandidateSummary, candidate_summaries

PER_CYCLE_FIELDS = ['candidate_contributions', 'candidate_loans', 'loan_repayments',
                    'debts_owed_by', 'debts_owed_to', 'total_receipts', 'total_disbursements',
                    'cash_on_hand', 'transfers_from_auth', 'transfers_to_auth']
SUMMARY_FIELDS = PER_CYCLE_FIELDS + ['self_funding']
CSV_FIELDS = (['person_key', 'full_name', 'fec_candidate_ids']
              + [f'{field}_career' for field in SUMMARY_FIELDS]
              + ['cash_on_hand_cycle', 'debts_owed_by_cycle']
              + [f'{field}_2026' for field in SUMMARY_FIELDS]
              + ['data_notes'])
META_TEXT = {
    'source': 'staged bulk weball files data/raw/weball/weballYY.txt, cycles 1980-2026',
    'data_as_of': DATA_AS_OF,
    'column_map_1indexed': {
        'total_receipts': 6, 'transfers_from_auth': 7, 'total_disbursements': 8,
        'transfers_to_auth': 9, 'cash_on_hand_coh_cop': 11,
        'candidate_contributions': 12, 'candidate_loans': 13,
        'loan_repayments_cand_loan_repay_plus_other_loan_repay': '15+16',
        'debts_owed_by': 17, 'coverage_end_date': 28,
        'debts_owed_to': None,
    },
    'debts_owed_to_note': 'No weball column exists for debts owed TO the committee; '
                          'output as null everywhere, never zero. FEC API spot-check '
                          '(Constantino, cycles 2024 and 2026): '
                          'last_debts_owed_to_committee $0.00.',
    'weball_vs_api': 'FEC API candidate-totals endpoint (DEMO_KEY, Nov 12, 2026) '
                     'returns values identical to weball to the cent for Constantino '
                     'H6NY21157 in both cycles 2024 and 2026. The $17,000,000 loan / '
                     '$17,064,951 receipts figures are CAREER sums (2024 $2.6M + 2026 '
                     '$14.4M), not 2026-only values; there is no weball-vs-API '
                     'discrepancy at matched coverage. Caveat is timeliness only: '
                     'staged 2026 weball covers through 10/14/2026 (pre-general).',
    'aggregation': 'Flows summed across cycles; cash_on_hand and debts_owed_by '
                   'are stocks = latest cycle value (see cash_on_hand_cycle / '
                   'debts_owed_by_cycle).',
}


def weball_column(field):
    return CandidateSummary._fields.index(field) + 1


def read_weball(roster):
    amounts, coverage_end = {}, {}
    counts = {'weball_rows_scanned': 0, 'weball_rows_matched_roster': 0,
              'weball_bad_field_count_rows': 0}
    for cycle in CYCLES:
        summaries = candidate_summaries(PATHS.bulk, cycle)
        for summary in summaries:
            if summary.candidate_id in roster:
                counts['weball_rows_matched_roster'] += 1
                amounts[summary.candidate_id, cycle] = {
                    field: summary.amount(field) for field in FINANCIAL_FIELDS}
                coverage_end[summary.candidate_id, cycle] = summary.coverage_end
        counts['weball_rows_scanned'] += summaries.rows_read
        counts['weball_bad_field_count_rows'] += summaries.malformed_rows
    return amounts, coverage_end, counts


def per_cycle_entries(person, finances, coverage_end):
    entries = []
    for cycle in CYCLES:
        for candidate_id in candidate_ids(person):
            cycle_finances = finances.get((candidate_id, cycle))
            if not cycle_finances:
                continue
            amounts = {field: text_or_none(getattr(cycle_finances, field, None))
                       for field in PER_CYCLE_FIELDS}
            entries.append({'cycle': cycle, 'candidate_id': candidate_id, **amounts,
                            'coverage_end_date': coverage_end.get((candidate_id, cycle), '')})
    return entries


def summed(finances_list, field):
    return Money.total(getattr(f, field) for f in finances_list)


def flows_and_self_funding(finances_list):
    totals = {field: summed(finances_list, field) for field in FLOWS}
    totals['self_funding'] = totals['candidate_contributions'] + totals['candidate_loans']
    return totals


def stocks(finances_list):
    if not finances_list:
        return dict.fromkeys(STOCKS)
    return {field: summed(finances_list, field) for field in STOCKS}


def person_summary(person, finances):
    """Career and current-cycle figures, and the latest cycle with a weball row."""
    ids = candidate_ids(person)
    if not ids:
        unknown = dict.fromkeys(FLOWS + STOCKS + ['self_funding'])
        return unknown, dict(unknown), ''
    by_cycle = {cycle: [finances[cid, cycle] for cid in ids if (cid, cycle) in finances]
                for cycle in CYCLES}
    cycles_with_rows = [cycle for cycle, found in by_cycle.items() if found]
    every_cycle = [f for found in by_cycle.values() for f in found]
    latest = cycles_with_rows[-1] if cycles_with_rows else None
    career = {**flows_and_self_funding(every_cycle), **stocks(by_cycle.get(latest, []))}
    current = {**flows_and_self_funding(by_cycle[CURRENT_CYCLE]),
               **stocks(by_cycle[CURRENT_CYCLE])}
    return career, current, str(latest) if latest else ''


def notes_for(person, finances, roster, differing):
    ids = candidate_ids(person)
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster — self-funding unknown (null, not zero)')
    elif not any((cid, cycle) in finances for cid in ids for cycle in CYCLES):
        notes.append('no weball rows found')
    if roster.shared_id_note(person):
        notes.append(roster.shared_id_note(person))
    for flag in differing:
        if flag['person_key'] == person['person_key']:
            notes.append(
                f"dedup partial {flag['cycle']}: weball col {flag['column_1indexed']} differs "
                f"between kept {flag['kept_id']} (${flag['kept_value']}) and dropped "
                f"{flag['dropped_id']} (${flag['dropped_value']}); both copies counted "
                f"for that column (recorded dedup covers TTL_INDIV_CONTRIB only)")
    return ' | '.join(notes)


def csv_row(person, finances, roster, differing):
    career, current, latest_cycle = person_summary(person, finances)
    return {'person_key': person['person_key'], 'full_name': person['full_name'],
            'fec_candidate_ids': ';'.join(candidate_ids(person)),
            **{f'{field}_career': text_or_blank(career.get(field)) for field in SUMMARY_FIELDS},
            'cash_on_hand_cycle': latest_cycle, 'debts_owed_by_cycle': latest_cycle,
            **{f'{field}_2026': text_or_blank(current.get(field)) for field in SUMMARY_FIELDS},
            'data_notes': notes_for(person, finances, roster, differing)}


def describe(differing):
    return [{'person_key': record['person_key'], 'name': record['name'],
             'cycle': record['cycle'], 'kept_id': record['kept_id'],
             'dropped_id': dropped_id, 'column_1indexed': weball_column(field),
             'kept_value': str(kept), 'dropped_value': str(dropped)}
            for record, dropped_id, field, kept, dropped in differing]


def main():
    roster = Roster(load_roster())
    dedup_records = load_double_count_records()

    amounts, coverage_end, counts = read_weball(roster)
    report = remove_double_counts(amounts, dedup_records,
                                  {p['person_key'] for p in roster.people})
    differing = describe(report.differing)
    finances = {key: CampaignFinances.from_weball(found) for key, found in amounts.items()}

    rows = [csv_row(person, finances, roster, differing) for person in roster.people]
    write_csv(PATHS.self_funding_csv, rows, CSV_FIELDS)

    persons = {p['person_key']: {'person_key': p['person_key'], 'full_name': p['full_name'],
                                 'fec_candidate_ids': candidate_ids(p),
                                 'per_cycle': per_cycle_entries(p, finances, coverage_end)}
               for p in roster.people}
    meta = {**META_TEXT,
            'dedup': {'groups_in_record': len(dedup_records),
                      'groups_applied': report.groups_applied,
                      'identical_cells_zeroed': report.cells_zeroed,
                      'differing_columns_flagged_not_corrected': differing},
            **counts}
    write_json(PATHS.self_funding_per_cycle, {'meta': meta, 'persons': persons})

    print('persons:', len(rows))
    print('dedup groups applied:', report.groups_applied,
          'identical cells zeroed:', report.cells_zeroed, 'differing columns flagged:', len(differing))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Self-funding, topline and transfer columns from weball, read from the store."""

from receipts.common.files import text_or_blank, text_or_none
from receipts.common.log import log, run
from receipts.common.settings import load_double_count_records, load_roster, settings
from receipts.domain.campaign_finances import FLOWS, STOCKS, CampaignFinances
from receipts.domain.money import Money
from receipts.domain.roster import Roster, candidate_ids
from receipts.domain.weball_double_counts import FINANCIAL_FIELDS
from receipts.fec.weball import CandidateSummary
from receipts.square_one.corrected import load as load_corrected
from receipts.square_one.corrected import substitute_transfers
from receipts.store.gold import per_cycle_rows, write_gold
from receipts.store.read import connect, for_candidates

PER_CYCLE_FIELDS = [
    'candidate_contributions',
    'candidate_loans',
    'loan_repayments',
    'debts_owed_by',
    'debts_owed_to',
    'total_receipts',
    'total_disbursements',
    'cash_on_hand',
    'transfers_from_auth',
    'transfers_to_auth',
]
SUMMARY_FIELDS = PER_CYCLE_FIELDS + ['self_funding']
CSV_FIELDS = (
    ['person_key', 'full_name', 'fec_candidate_ids']
    + [f'{field}_career' for field in SUMMARY_FIELDS]
    + ['cash_on_hand_cycle', 'debts_owed_by_cycle']
    + [f'{field}_2026' for field in SUMMARY_FIELDS]
    + ['data_notes']
)


def weball_column(field):
    return CandidateSummary._fields.index(field) + 1


COUNTED = (
    'SELECT candidate_id, cycle, coverage_end, '
    + ', '.join(f'{field}_cents' for field in FINANCIAL_FIELDS)
    + ' FROM counted_summaries WHERE TRUE'
)
DIFFERING = (
    'SELECT person_key, cycle, kept_id, candidate_id, field, kept_cents, dropped_cents '
    'FROM summary_differences ORDER BY position'
)


def read_store(roster_ids):
    with connect() as db:
        counted = for_candidates(db, COUNTED, roster_ids)
        differing = db.execute(DIFFERING).fetchall()
    finances = {
        (candidate_id, cycle): CampaignFinances.from_weball(
            {field: Money(cents) for field, cents in zip(FINANCIAL_FIELDS, amounts, strict=True)}
        )
        for candidate_id, cycle, _, *amounts in counted
    }
    coverage_end = {(candidate_id, cycle): end for candidate_id, cycle, end, *_ in counted}
    return finances, coverage_end, differing


def per_cycle_entries(person, finances, coverage_end):
    entries = []
    for cycle in settings().cycles.career:
        for candidate_id in candidate_ids(person):
            cycle_finances = finances.get((candidate_id, cycle))
            if not cycle_finances:
                continue
            amounts = {
                field: text_or_none(getattr(cycle_finances, field, None))
                for field in PER_CYCLE_FIELDS
            }
            entries.append(
                {
                    'cycle': cycle,
                    'candidate_id': candidate_id,
                    **amounts,
                    'coverage_end_date': coverage_end.get((candidate_id, cycle), ''),
                }
            )
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
    by_cycle = {
        cycle: [finances[cid, cycle] for cid in ids if (cid, cycle) in finances]
        for cycle in settings().cycles.career
    }
    cycles_with_rows = [cycle for cycle, found in by_cycle.items() if found]
    every_cycle = [f for found in by_cycle.values() for f in found]
    latest = cycles_with_rows[-1] if cycles_with_rows else None
    career = {**flows_and_self_funding(every_cycle), **stocks(by_cycle[latest] if latest else [])}
    current = {
        **flows_and_self_funding(by_cycle[settings().cycles.current]),
        **stocks(by_cycle[settings().cycles.current]),
    }
    return career, current, str(latest) if latest else ''


def notes_for(person, finances, roster, differing):
    ids = candidate_ids(person)
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster — self-funding unknown (null, not zero)')
    elif not any((cid, cycle) in finances for cid in ids for cycle in settings().cycles.career):
        notes.append('no weball rows found')
    if roster.shared_id_note(person):
        notes.append(roster.shared_id_note(person))
    for flag in differing:
        if flag['person_key'] == person['person_key']:
            notes.append(
                f'dedup partial {flag["cycle"]}: weball col {flag["column_1indexed"]} differs '
                f'between kept {flag["kept_id"]} (${flag["kept_value"]}) and dropped '
                f'{flag["dropped_id"]} (${flag["dropped_value"]}); both copies counted '
                f'for that column (recorded dedup covers TTL_INDIV_CONTRIB only)'
            )
    return ' | '.join(notes)


def csv_row(person, finances, roster, differing):
    career, current, latest_cycle = person_summary(person, finances)
    return {
        'person_key': person['person_key'],
        'full_name': person['full_name'],
        'fec_candidate_ids': ';'.join(candidate_ids(person)),
        **{f'{field}_career': text_or_blank(career.get(field)) for field in SUMMARY_FIELDS},
        'cash_on_hand_cycle': latest_cycle,
        'debts_owed_by_cycle': latest_cycle,
        **{f'{field}_2026': text_or_blank(current.get(field)) for field in SUMMARY_FIELDS},
        'data_notes': notes_for(person, finances, roster, differing),
    }


def describe(differing, dedup_records):
    names = {record['person_key']: record['name'] for record in dedup_records}
    return [
        {
            'person_key': person_key,
            'name': names[person_key],
            'cycle': cycle,
            'kept_id': kept_id,
            'dropped_id': dropped_id,
            'column_1indexed': weball_column(field),
            'kept_value': str(Money(kept)),
            'dropped_value': str(Money(dropped)),
        }
        for person_key, cycle, kept_id, dropped_id, field, kept, dropped in differing
    ]


def self_funding_by_person(roster, finances, coverage_end, differing):
    """(people rows, {person_key: per_cycle entry}) for every roster person."""
    rows = [csv_row(person, finances, roster, differing) for person in roster.people]
    persons = {
        p['person_key']: {'per_cycle': per_cycle_entries(p, finances, coverage_end)}
        for p in roster.people
    }
    return rows, persons


def write(rows, persons):
    write_gold(
        'self_funding_people', rows, {c for c in CSV_FIELDS if c.endswith(('_career', '_2026'))}
    )
    write_gold('self_funding_per_cycle', per_cycle_rows(persons), set(PER_CYCLE_FIELDS))


def main():
    roster = Roster(load_roster())
    roster_ids = {i for p in roster.people for i in candidate_ids(p)}
    finances, coverage_end, found_differing = read_store(roster_ids)
    differing = describe(found_differing, load_double_count_records())
    finances = substitute_transfers(
        finances, roster.people, load_double_count_records(), load_corrected()
    )
    rows, persons = self_funding_by_person(roster, finances, coverage_end, differing)
    write(rows, persons)
    log.info(f'persons: {len(rows)}; differing columns flagged, not corrected: {len(differing)}')


if __name__ == '__main__':
    run(main)

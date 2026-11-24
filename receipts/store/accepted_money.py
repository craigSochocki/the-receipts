#!/usr/bin/env python3
"""Write the accepted-money gold tables from the silver store."""

from receipts.common.settings import settings
from receipts.domain.money import Money
from receipts.domain.roster import Roster
from receipts.store.gold import per_cycle_rows, write_gold
from receipts.store.read import connect

COLUMNS = [
    'individual',
    'aipac_pac_direct',
    'aipac_earmark_transmitted',
    'corporate_pac',
    'corporate_earmark_transmitted',
]
CAREER = {
    column: (
        'individual_contribution_total_career' if column == 'individual' else f'{column}_career'
    )
    for column in COLUMNS
}


def tracked_people(db):
    people = [
        {'person_key': key, 'full_name': name, 'fec_candidate_ids': []}
        for key, name in db.execute(
            'SELECT person_key, full_name FROM people '
            'WHERE roster_position IS NOT NULL ORDER BY roster_position'
        ).fetchall()
    ]
    by_key = {p['person_key']: p for p in people}
    for person_key, candidate_id in db.execute(
        'SELECT person_key, candidate_id FROM person_candidate_ids ORDER BY person_key, position'
    ).fetchall():
        by_key[person_key]['fec_candidate_ids'].append(candidate_id)
    return people


def money_by_candidate_cycle(db, candidate_ids):
    """Counted amounts per (candidate, cycle), and which of those had anything filed."""
    counted, filed = {}, set()
    for candidate_id, cycle, individual_filed, *amounts in db.execute(
        f'SELECT candidate_id, cycle, individual_filed, {", ".join(COLUMNS)} FROM accepted_money'
    ).fetchall():
        if candidate_id not in candidate_ids:
            continue
        counted[candidate_id, cycle] = dict(zip(COLUMNS, map(Money, amounts), strict=True))
        # A cycle appears if anything was filed for it, even when the
        # double-count correction leaves it at zero.
        if individual_filed or any(amounts[1:]):
            filed.add((candidate_id, cycle))
    return counted, filed


def notes_for(person, career, roster, on_file):
    ids = person['fec_candidate_ids']
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster')
    elif not on_file.intersection(ids):
        notes.append('no FEC activity found')
    elif not (career['individual'] or career['aipac_pac_direct'] or career['corporate_pac']):
        notes.append('FEC activity found; all totals zero')
    if roster.shared_id_note(person):
        notes.append(roster.shared_id_note(person))
    if career['aipac_pac_direct'].is_negative:
        notes.append('net-negative AIPAC total (voids exceed direct contributions)')
    return ' | '.join(notes)


def read_store():
    """(people, counted money, filed (candidate, cycle)s, candidate IDs on file) from the store."""
    with connect() as db:
        people = tracked_people(db)
        roster_ids = {i for p in people for i in p['fec_candidate_ids']}
        counted, filed = money_by_candidate_cycle(db, roster_ids)
        on_file = {
            row[0] for row in db.execute('SELECT candidate_id FROM candidates_on_file').fetchall()
        }
    return people, counted, filed, on_file


def accepted_by_person(people, counted, filed, on_file, cycles):
    """(people rows, {person_key: per_cycle entry}): each person's money across IDs and cycles."""
    roster = Roster(people)
    rows, per_cycle = [], {}
    for person in people:
        ids = person['fec_candidate_ids']
        entries = [
            (cycle, candidate_id, counted[candidate_id, cycle])
            for cycle in cycles
            for candidate_id in ids
            if (candidate_id, cycle) in filed
        ]
        career = {c: Money.total(amounts[c] for _, _, amounts in entries) for c in COLUMNS}
        rows.append(
            {
                'person_key': person['person_key'],
                'full_name': person['full_name'],
                'fec_candidate_ids': ';'.join(ids),
                **{CAREER[c]: str(career[c]) for c in COLUMNS},
                'data_notes': notes_for(person, career, roster, on_file),
            }
        )
        per_cycle[person['person_key']] = {
            'person_key': person['person_key'],
            'full_name': person['full_name'],
            'per_cycle': [
                {
                    'cycle': cycle,
                    'candidate_id': candidate_id,
                    **{c: str(amounts[c]) for c in COLUMNS},
                }
                for cycle, candidate_id, amounts in entries
            ],
        }
    return rows, per_cycle


def write(rows, per_cycle):
    write_gold('accepted_money_people', rows, set(CAREER.values()))
    write_gold('accepted_money_per_cycle', per_cycle_rows(per_cycle), set(COLUMNS))


def main():
    people, counted, filed, on_file = read_store()
    write(*accepted_by_person(people, counted, filed, on_file, settings().cycles.career))


if __name__ == '__main__':
    main()

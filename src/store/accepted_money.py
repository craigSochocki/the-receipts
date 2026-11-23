#!/usr/bin/env python3
"""Write money_pas2_weball.csv and money_per_cycle.json from the silver store."""
import csv
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.config import load_config
from src.domain.money import Money

CFG = load_config()
ROOT = CFG['_root']
STORE = ROOT / CFG['paths']['store']
CYCLES = range(CFG['cycles']['career_start'], CFG['cycles']['career_end'] + 1, 2)
COLUMNS = ['individual', 'aipac_pac_direct', 'aipac_earmark_transmitted',
           'corporate_pac', 'corporate_earmark_transmitted']
CAREER = {column: ('individual_contribution_total_career' if column == 'individual'
                   else f'{column}_career') for column in COLUMNS}


def load(db):
    people = db.execute('SELECT person_key, full_name FROM people').fetchall()
    ids = {}
    for person_key, candidate_id in db.execute(
            'SELECT person_key, candidate_id FROM person_candidate_ids ORDER BY person_key, position'
    ).fetchall():
        ids.setdefault(person_key, []).append(candidate_id)
    roster_ids = {candidate_id for found in ids.values() for candidate_id in found}
    money = {}
    for candidate_id, cycle, individual_filed, *amounts in db.execute(
            f'SELECT candidate_id, cycle, individual_filed, {", ".join(COLUMNS)} FROM accepted_money'
    ).fetchall():
        if candidate_id in roster_ids:
            filed = dict(zip(COLUMNS, map(Money, amounts)), individual=Money(individual_filed))
            money[candidate_id, cycle] = (filed, dict(zip(COLUMNS, map(Money, amounts))))
    on_file = {row[0] for row in db.execute('SELECT candidate_id FROM candidates_on_file').fetchall()}
    return people, ids, money, on_file


def notes_for(person_key, ids, career, others, on_file):
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster')
    elif not on_file.intersection(ids):
        notes.append('no FEC activity found')
    elif not (career['individual'] or career['aipac_pac_direct'] or career['corporate_pac']):
        notes.append('FEC activity found; all totals zero')
    if others:
        notes.append('duplicate roster entry: FEC ID shared with ' + ', '.join(others))
    if career['aipac_pac_direct'].is_negative:
        notes.append('net-negative AIPAC total (voids exceed direct contributions)')
    return ' | '.join(notes)


def write(out_dir):
    with duckdb.connect(str(STORE), read_only=True) as db:
        people, ids_by_person, money, on_file = load(db)
    holders = {}
    for person_key, ids in ids_by_person.items():
        for candidate_id in ids:
            holders.setdefault(candidate_id, []).append(person_key)

    rows, per_cycle = [], {}
    for person_key, full_name in people:
        ids = ids_by_person.get(person_key, [])
        # A cycle appears if anything was filed for it, even when the
        # double-count correction leaves it at zero.
        entries = [(cycle, candidate_id, money[candidate_id, cycle][1])
                   for cycle in CYCLES for candidate_id in ids
                   if any(money.get((candidate_id, cycle), ({}, {}))[0].values())]
        career = {c: Money.total(amounts[c] for _, _, amounts in entries) for c in COLUMNS}
        others = sorted({k for i in ids for k in holders[i] if k != person_key})
        rows.append({'person_key': person_key, 'full_name': full_name,
                     'fec_candidate_ids': ';'.join(ids),
                     **{CAREER[c]: str(career[c]) for c in COLUMNS},
                     'data_notes': notes_for(person_key, ids, career, others, on_file)})
        per_cycle[person_key] = {
            'person_key': person_key, 'full_name': full_name,
            'per_cycle': [{'cycle': cycle, 'candidate_id': candidate_id,
                           **{c: str(amounts[c]) for c in COLUMNS}}
                          for cycle, candidate_id, amounts in entries]}

    with open(out_dir / 'money_pas2_weball.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with open(out_dir / 'money_per_cycle.json', 'w') as f:
        json.dump(per_cycle, f, indent=1)


if __name__ == '__main__':
    write(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / CFG['paths']['intermediate'])

#!/usr/bin/env python3
"""Pro-Israel PAC money per person: direct contributions and supporting IEs from a reviewed list."""

import csv
from collections import defaultdict

from receipts.common.log import log, run
from receipts.common.settings import load_roster, settings
from receipts.store.gold import write_gold
from receipts.store.ie_rows import Roster
from receipts.store.read import connect

DIRECT = (
    'SELECT candidate_id, cycle, SUM(amount_cents) FROM counted_committee_money '
    'WHERE committee_id IN (SELECT UNNEST(?)) GROUP BY candidate_id, cycle'
)
IE_SUPPORT = (
    'SELECT candidate_id, cycle, SUM(amount_cents) FROM outside_spending '
    "WHERE excluded_because IS NULL AND direction = 'S' AND spender_id IN (SELECT UNNEST(?)) "
    'GROUP BY candidate_id, cycle'
)
COLUMNS = ('pro_israel_pac', 'pro_israel_ie_support')


def listed_committees():
    with open(settings().paths.pro_israel_pacs, newline='') as f:
        return sorted({row['committee_id'] for row in csv.DictReader(f)})


def candidate_cycles(committees):
    """{(candidate_id, cycle): {column: cents}} for both kinds of money."""
    amounts = defaultdict(lambda: dict.fromkeys(COLUMNS, 0))
    with connect() as db:
        for column, sql in zip(COLUMNS, (DIRECT, IE_SUPPORT), strict=True):
            for candidate_id, cycle, cents in db.execute(sql, [committees]).fetchall():
                amounts[candidate_id, cycle][column] += cents
    return amounts


def per_cycle(person, amounts):
    ids = Roster.ids(person)
    cycles = defaultdict(lambda: dict.fromkeys(COLUMNS, 0))
    for (candidate_id, cycle), money in amounts.items():
        if candidate_id in ids:
            for column in COLUMNS:
                cycles[cycle][column] += money[column]
    return [{'cycle': c, **cycles[c]} for c in sorted(cycles) if any(cycles[c].values())]


def person_row(person, cycles):
    if not Roster.ids(person):
        return {'person_key': person['person_key'], **{f'{c}_career': None for c in COLUMNS}}
    return {
        'person_key': person['person_key'],
        **{f'{c}_career': sum(e[c] for e in cycles) for c in COLUMNS},
    }


def main():
    committees = listed_committees()
    amounts = candidate_cycles(committees)
    people = load_roster()
    cycles = {p['person_key']: per_cycle(p, amounts) for p in people}
    rows = [person_row(p, cycles[p['person_key']]) for p in people]
    write_gold('pro_israel_people', rows, set())
    write_gold(
        'pro_israel_per_cycle',
        [
            {'person_key': k, 'entry': n, **e}
            for k, entries in cycles.items()
            for n, e in enumerate(entries)
        ],
        set(),
    )
    log.info(f'{len(committees)} listed committees')


if __name__ == '__main__':
    run(main)

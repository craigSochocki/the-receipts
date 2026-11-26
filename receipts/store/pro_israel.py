#!/usr/bin/env python3
"""Pro-Israel PAC money per person from a published list: direct, supporting IE, opposition credit."""

import csv
from collections import defaultdict

from receipts.common.log import log, run
from receipts.common.settings import load_roster, settings
from receipts.square_one.corrected import API_CYCLES
from receipts.square_one.corrected import load as load_corrected
from receipts.store.gold import write_gold
from receipts.store.ie_rows import Roster
from receipts.store.opposition import credits, person_of, races_of
from receipts.store.read import connect
from receipts.store.udp_rows import UdpRows

DIRECT = (
    'SELECT candidate_id, cycle, SUM(amount_cents) FROM counted_committee_money '
    'WHERE committee_id IN (SELECT UNNEST(?)) GROUP BY candidate_id, cycle'
)
COLUMNS = ('pro_israel_pac', 'pro_israel_ie_support', 'pro_israel_opp_credit')


def listed_committees():
    with open(settings().paths.pro_israel_pacs, newline='') as f:
        return sorted({row['committee_id'] for row in csv.DictReader(f)})


def direct(committees, amounts):
    with connect() as db:
        for candidate_id, cycle, cents in db.execute(DIRECT, [committees]).fetchall():
            amounts[candidate_id, cycle]['pro_israel_pac'] += cents


def outside_spending(committees, roster, amounts, credit):
    """Each listed spender's support, and its opposition credited by the UDP race rule."""
    person_keys = person_of(roster)
    for spender_id in committees:
        rows = UdpRows.from_store(roster, spender_id).rows
        for row in rows:
            if row.direction == 'S' and row.candidate_id:
                amounts[row.candidate_id, row.cycle]['pro_israel_ie_support'] += row.cents
        for race, person_key, _, dollars, _ in credits(races_of(rows), person_keys)[2]:
            if not person_key.startswith('__nonroster__'):
                credit[person_key][race[0]] += round(dollars * 100)


def per_cycle(person, amounts, credit=None, corrected=None):
    ids = Roster.ids(person)
    cycles = defaultdict(lambda: dict.fromkeys(COLUMNS, 0))
    for (candidate_id, cycle), money in amounts.items():
        if candidate_id in ids:
            for column in ('pro_israel_pac', 'pro_israel_ie_support'):
                cycles[cycle][column] += money[column]
    for cycle, cents in (credit or {}).get(person['person_key'], {}).items():
        cycles[cycle]['pro_israel_opp_credit'] += cents
    if corrected is not None:
        for cycle in API_CYCLES:
            cents = corrected.pro_israel_cents(person['person_key'], cycle)
            if cents is None or (cents == 0 and cycle not in cycles):
                continue
            cycles[cycle]['pro_israel_pac'] = cents
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
    people = load_roster()
    amounts = defaultdict(lambda: dict.fromkeys(COLUMNS, 0))
    credit = defaultdict(lambda: defaultdict(int))
    direct(committees, amounts)
    outside_spending(committees, people, amounts, credit)
    corrected = load_corrected()
    cycles = {p['person_key']: per_cycle(p, amounts, credit, corrected) for p in people}
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

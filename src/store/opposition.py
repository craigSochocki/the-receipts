#!/usr/bin/env python3
"""Opposition credit: UDP's spending against a backed candidate's opponents.

For each race phase (cycle, office, state, district, election type), if UDP
supported exactly one candidate, its spending opposing others in that phase
is credited to that candidate; zero or two-plus backed candidates credit
nothing. Spending against the backed candidate themself is never credited.
The phase is the filing's election type because UDP's expenditure dates are
blank on every row. AIPAC PAC files no Schedule E rows, so it has no column.
"""
import csv
from collections import Counter, defaultdict

from src.common.baseline import expected
from src.common.files import write_json
from src.common.settings import AIPAC_PAC, IE_CYCLES as CYCLES, PATHS, load_roster
from src.store.read import connect
from src.store.udp_rows import UdpRows


def dollars(cents):
    return cents / 100


class Race:
    def __init__(self):
        self.backed, self.backed_names = set(), {}
        self.oppose_total = 0
        self.opposed_names = Counter()
        self.oppose_rows = []

    def add(self, row):
        if row.direction == 'S' and row.candidate_id:
            self.backed.add(row.candidate_id)
            self.backed_names[row.candidate_id] = row.candidate_name
        elif row.direction == 'O':
            self.oppose_total += row.cents
            self.opposed_names[row.candidate_name] += row.cents
            self.oppose_rows.append(row)

    def against_backed(self, backed_id):
        backed_name = self.backed_names[backed_id].upper()
        return sum(row.cents for row in self.oppose_rows
                   if row.candidate_id == backed_id
                   or (not row.candidate_id and row.candidate_name.upper() == backed_name))

    def opposed(self):
        return {name: dollars(cents) for name, cents in self.opposed_names.items()}


def races_of(rows):
    races = defaultdict(Race)
    for row in rows:
        races[row.cycle, row.office, row.state, row.district, row.election_type].add(row)
    return races


def person_of(roster):
    found = {}
    for p in roster:
        for candidate_id in p.get('fec_candidate_ids') or []:
            found.setdefault(candidate_id, p['person_key'])
    return found


def credits(races, person_keys):
    by_person, nonroster = defaultdict(int), defaultdict(int)
    credited, uncredited = [], []
    for key, race in sorted(races.items()):
        if race.oppose_total <= 0:
            continue
        if len(race.backed) != 1:
            uncredited.append([list(key), len(race.backed),
                               [race.backed_names.get(b, b) for b in sorted(race.backed)],
                               dollars(race.oppose_total), race.opposed()])
            continue
        backed_id = next(iter(race.backed))
        creditable = race.oppose_total - race.against_backed(backed_id)
        person_key = person_keys.get(backed_id)
        if person_key:
            by_person[person_key] += creditable
        else:
            nonroster[backed_id] += creditable
        credited.append([list(key), person_key or f'__nonroster__{backed_id}',
                         race.backed_names[backed_id], dollars(creditable), race.opposed()])
    return by_person, nonroster, credited, uncredited


def support_mismatches(rows, person_keys):
    """Each roster person's UDP support, recomputed, against the committed dataset."""
    support = defaultdict(int)
    for row in rows:
        if row.direction == 'S' and row.candidate_id in person_keys:
            support[person_keys[row.candidate_id]] += row.cents
    with open(PATHS.dataset_csv, newline='') as f:
        published = {r['person_key']: r['udp_ie_support_career'] for r in csv.DictReader(f)}
    return [(key, float(value), dollars(support.get(key, 0)))
            for key, value in published.items()
            if value not in ('unknown', '') and abs(dollars(support.get(key, 0)) - float(value)) > 0.005]


def aipac_rows():
    with connect() as db:
        return db.execute("SELECT count(*) FROM outside_spending WHERE spender_id = ? "
                          "AND excluded_because IS DISTINCT FROM 'reported_again'",
                          [AIPAC_PAC]).fetchone()[0]


def main():
    roster = load_roster()
    udp = UdpRows(roster)
    for cycle in CYCLES:
        expected(f'udp_prior_cycle_totals.{cycle}', dollars(udp.cycle_total(cycle)))
    person_keys = person_of(roster)
    by_person, nonroster, credited, uncredited = credits(races_of(udp.rows), person_keys)
    write_json(PATHS.opposition_computed, {
        'credit_by_person': {k: dollars(v) for k, v in by_person.items()},
        'credit_detail': credited,
        'no_credit': uncredited,
        'nonroster_credit': {k: dollars(v) for k, v in nonroster.items()},
        'support_mismatches': support_mismatches(udp.rows, person_keys),
        'unresolved_blank_rows': len(udp.unresolved),
        'aipac_schedule_e_rows': aipac_rows(),
    })
    print(f'races credited: {len(credited)}; not credited: {len(uncredited)}; '
          f'credited to roster: ${dollars(sum(by_person.values())):,.2f}')


if __name__ == '__main__':
    main()

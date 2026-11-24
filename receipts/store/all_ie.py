#!/usr/bin/env python3
"""All independent expenditures by identified candidate, read from the store."""

from collections import defaultdict
from typing import NamedTuple

from receipts.common.baseline import expected
from receipts.common.settings import load_roster, settings
from receipts.store.all_ie_report import blank_attribution_by_cycle, file_exclusions, write_report
from receipts.store.gold import write_gold
from receipts.store.ie_rows import (
    REPLACED,
    Expenditure,
    Roster,
    by_direction,
    dollars,
    total,
)
from receipts.store.read import connect

ROWS = (
    'SELECT spender_id, spender_name, candidate_id, candidate_name, cycle, direction, '
    'amount_cents, office, office_state, office_district, expenditure_date, transaction_id, '
    'excluded_because FROM outside_spending ORDER BY cycle, file_order NULLS LAST'
)


class CandidateTotals:
    def __init__(self, included):
        self.amounts = defaultdict(lambda: {'S': 0, 'O': 0, '': 0, 'rows': 0})
        self.by_committee = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
        self.label = {}
        for x in included:
            key = x.candidate_id, x.cycle
            amounts = self.amounts[key]
            amounts[x.direction if x.direction in ('S', 'O') else ''] += x.cents
            amounts['rows'] += 1
            committee = self.by_committee[key][x.spender_id, x.spender_name]
            if x.direction == 'S':
                committee[0] += x.cents
            elif x.direction == 'O':
                committee[1] += x.cents
            committee[2] += 1
            largest = self.label.get(key)
            if largest is None or abs(x.cents) > abs(largest.cents):
                self.label[key] = x

    def of(self, candidate_ids, cycles):
        found = [
            a for (c, cycle), a in self.amounts.items() if c in candidate_ids and cycle in cycles
        ]
        support, oppose = sum(a['S'] for a in found), sum(a['O'] for a in found)
        return support, oppose, support + oppose + sum(a[''] for a in found)


def top_by_total(committees, n):
    return sorted(committees.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:n]


def per_candidate_entries(totals, roster):
    entries = []
    for (candidate_id, cycle), amounts in sorted(totals.amounts.items()):
        label = totals.label[candidate_id, cycle]
        entries.append(
            {
                'candidate_id': candidate_id,
                'candidate_name': label.candidate_name,
                'office': label.office,
                'state': label.state,
                'district': label.district,
                'cycle': cycle,
                'all_ie_support': dollars(amounts['S']),
                'all_ie_oppose': dollars(amounts['O']),
                'all_ie_total': dollars(amounts['S'] + amounts['O'] + amounts['']),
                'no_direction_amount': dollars(amounts['']),
                'rows': amounts['rows'],
                'is_roster': candidate_id in roster.person_of,
                'person_key': roster.person_of.get(candidate_id),
                'top_committees': [
                    {
                        'committee_id': committee_id,
                        'committee_name': name,
                        'support': dollars(s),
                        'oppose': dollars(o),
                        'total': dollars(s + o),
                        'rows': n,
                    }
                    for (committee_id, name), (s, o, n) in top_by_total(
                        totals.by_committee[candidate_id, cycle], 5
                    )
                ],
            }
        )
    return sorted(entries, key=lambda e: (e['cycle'], -e['all_ie_total']))


def top_committees(rows, n=10):
    committees = defaultdict(lambda: [0, 0, ''])
    for x in rows:
        committee = committees[x.spender_id]
        committee[2] = x.spender_name
        if x.direction == 'S':
            committee[0] += x.cents
        elif x.direction == 'O':
            committee[1] += x.cents
    return [
        {
            'committee_id': committee_id,
            'committee_name': name,
            'support': dollars(s),
            'oppose': dollars(o),
            'total': dollars(s + o),
        }
        for committee_id, (s, o, name) in top_by_total(committees, n)
    ]


def cycle_summary(included, roster):
    on_roster = [x for x in included if x.candidate_id in roster.person_of]
    s_all, o_all, t_all = by_direction(included)
    s_roster, o_roster, t_roster = by_direction(on_roster)
    senate = total(x for x in on_roster if x.office == 'S')
    house = total(x for x in on_roster if x.office == 'H')
    return {
        'all_candidates': {
            'support': s_all,
            'oppose': o_all,
            'total': t_all,
            'n_candidates': len({x.candidate_id for x in included}),
            'n_rows': len(included),
        },
        'roster_targeted': {
            'support': s_roster,
            'oppose': o_roster,
            'total': t_roster,
            'n_persons_with_spending': len({roster.person_of[x.candidate_id] for x in on_roster}),
            'senate': dollars(senate),
            'house': dollars(house),
            'other_or_blank_office': dollars(total(on_roster) - senate - house),
        },
        'top_committees_roster_targeted': top_committees(on_roster),
        'top_committees_all_candidates': top_committees(included),
    }


def person_totals(person, totals):
    """{support, oppose, total, by_cycle} in cents, or None for a person with no FEC IDs."""
    ids = Roster.ids(person)
    if not ids:
        return None
    by_cycle = {cycle: totals.of(ids, {cycle}) for cycle in settings().cycles.ie}
    career = [sum(amounts[i] for amounts in by_cycle.values()) for i in range(3)]
    return {'support': career[0], 'oppose': career[1], 'total': career[2], 'by_cycle': by_cycle}


def csv_row(person, found):
    row = {'person_key': person['person_key'], 'full_name': person['full_name']}
    if found is None:
        return {
            **row,
            'fec_candidate_ids': '',
            **dict.fromkeys(
                [
                    'all_ie_support_career',
                    'all_ie_oppose_career',
                    'all_ie_total_career',
                    'all_ie_support_2026',
                    'all_ie_oppose_2026',
                    'all_ie_total_2026',
                ],
                '',
            ),
            'data_notes': 'No FEC candidate ID on file; not searchable in IE data.',
        }
    support, oppose, current_total = found['by_cycle'][settings().cycles.current]
    return {
        **row,
        'fec_candidate_ids': ';'.join(Roster.ids(person)),
        'all_ie_support_career': f'{dollars(found["support"]):.2f}',
        'all_ie_oppose_career': f'{dollars(found["oppose"]):.2f}',
        'all_ie_total_career': f'{dollars(found["total"]):.2f}',
        'all_ie_support_2026': f'{dollars(support):.2f}',
        'all_ie_oppose_2026': f'{dollars(oppose):.2f}',
        'all_ie_total_2026': f'{dollars(current_total):.2f}',
        'data_notes': (
            '' if found['total'] else 'No all-IE spending found in 2022/2024/2026 IE files.'
        ),
    }


def top_committees_for(person, totals):
    """A person's top five spenders; a committee keeps the name from its largest total."""
    ids = Roster.ids(person)
    if not ids:
        return None
    combined = defaultdict(lambda: [0, 0, 0, '', 0])
    for (candidate_id, _), committees in totals.by_committee.items():
        if candidate_id not in ids:
            continue
        for (committee_id, name), (s, o, n) in committees.items():
            entry = combined[committee_id]
            entry[0] += s
            entry[1] += o
            entry[2] += n
            if s + o > entry[4]:
                entry[3], entry[4] = name, s + o
    return [
        {
            'committee_id': committee_id,
            'committee_name': entry[3],
            'support': dollars(entry[0]),
            'oppose': dollars(entry[1]),
            'total': dollars(entry[0] + entry[1]),
            'rows': entry[2],
        }
        for committee_id, entry in top_by_total(combined, 5)
    ]


TOP_SPENDERS_PINNED = 5


def pin_dollars(key, observed):
    recorded = expected(key, observed)
    if abs(observed - recorded) >= 0.005:
        raise SystemExit(f'all-IE {key} is {observed:,.2f}; the baseline says {recorded:,.2f}')


def pin_text(key, observed):
    recorded = expected(key, observed)
    if observed != recorded:
        raise SystemExit(f'all-IE {key} is {observed}; the baseline says {recorded}')


def check_current_cycle(summary):
    """The current cycle's roster split and top spenders must match the baseline."""
    roster_targeted = summary['roster_targeted']
    for field in ('senate', 'house', 'support', 'oppose'):
        pin_dollars(f'all_ie_roster_{settings().cycles.current}.{field}', roster_targeted[field])
    top = summary['top_committees_roster_targeted'][:TOP_SPENDERS_PINNED]
    for rank, committee in enumerate(top, 1):
        key = f'all_ie_top_spenders_{settings().cycles.current}.{rank}'
        pin_text(f'{key}.committee_id', committee['committee_id'])
        pin_dollars(f'{key}.total', committee['total'])


def read_store():
    with connect() as db:
        rows = [Expenditure(*row) for row in db.execute(ROWS).fetchall()]
        columns = dict(
            db.execute("SELECT cycle, columns FROM files_read WHERE file = 'ie'").fetchall()
        )
    return rows, {cycle: (text or '').split(',') for cycle, text in columns.items()}


def check_udp_totals(of_cycle):
    """UDP's support + oppose total per cycle must match the UDP pull's, in the baseline."""
    for cycle in settings().cycles.ie:
        udp_total = dollars(
            total(
                x
                for x in of_cycle[cycle]
                if x.excluded_because != REPLACED and x.spender_id == settings().committees.udp
            )
        )
        if abs(udp_total - expected(f'udp_prior_cycle_totals.{cycle}', udp_total)) >= 0.005:
            raise SystemExit(f'UDP S+O total for {cycle} does not reconcile with the prior pull')


class OutsideSpending(NamedTuple):
    totals: CandidateTotals
    summaries: dict
    per_person: dict
    top: dict
    people: list
    by_candidate: list


def outside_spending(included, roster):
    """Every counted expenditure, summed per candidate, per person and per cycle."""
    totals = CandidateTotals(included)
    per_person = {p['person_key']: person_totals(p, totals) for p in roster.people}
    return OutsideSpending(
        totals=totals,
        summaries={
            cycle: cycle_summary([x for x in included if x.cycle == cycle], roster)
            for cycle in settings().cycles.ie
        },
        per_person=per_person,
        top={p['person_key']: top_committees_for(p, totals) for p in roster.people},
        people=[csv_row(p, per_person[p['person_key']]) for p in roster.people],
        by_candidate=per_candidate_entries(totals, roster),
    )


def write(spending):
    people = spending.people
    write_gold('all_ie_people', people, {c for c in people[0] if c.startswith('all_ie_')})
    write_gold(
        'all_ie_per_candidate_cycle',
        [{k: v for k, v in e.items() if k != 'top_committees'} for e in spending.by_candidate],
        {'all_ie_support', 'all_ie_oppose', 'all_ie_total', 'no_direction_amount'},
    )
    write_gold(
        'all_ie_top_committees',
        [
            {'person_key': person_key, 'entry': n, **committee}
            for person_key, committees in spending.top.items()
            for n, committee in enumerate(committees or [])
        ],
        {'support', 'oppose', 'total'},
    )


def main():
    rows, columns = read_store()
    roster = Roster(load_roster())
    of_cycle = {cycle: [x for x in rows if x.cycle == cycle] for cycle in settings().cycles.ie}
    kept = [x for x in rows if x.excluded_because != REPLACED]
    included = [x for x in kept if x.counted]
    exclusions = {
        cycle: file_exclusions(of_cycle[cycle], columns[cycle]) for cycle in settings().cycles.ie
    }
    check_udp_totals(of_cycle)
    blank_diagnostic, collisions = blank_attribution_by_cycle(included, kept, roster)
    spending = outside_spending(included, roster)
    check_current_cycle(spending.summaries[settings().cycles.current])
    write(spending)
    write_report(spending, roster, kept, exclusions, blank_diagnostic, collisions)
    for cycle in settings().cycles.ie:
        roster_targeted = spending.summaries[cycle]['roster_targeted']
        print(
            f'{cycle} roster: S ${roster_targeted["support"]:,.2f} / '
            f'O ${roster_targeted["oppose"]:,.2f} / total ${roster_targeted["total"]:,.2f}'
        )


if __name__ == '__main__':
    main()

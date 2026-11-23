#!/usr/bin/env python3
"""UDP independent-expenditure support per roster person, read from the store.

Only support rows count toward a person's total; UDP's spending against
a person is recorded in the note, never added. Rules and the exact note
wording: research/udp-notes.md.
"""

from collections import defaultdict

from receipts.common.baseline import expected
from receipts.common.settings import CURRENT_CYCLE, load_roster
from receipts.common.settings import IE_CYCLES as CYCLES
from receipts.store.gold import per_cycle_rows, write_gold
from receipts.store.udp_rows import UdpRows

ATTRIBUTION = 'name_state_district_office_match; cand_id blank in FEC file'
NAME_ATTRIBUTED = ('name_index', 'roster')


def dollars(cents):
    return cents / 100


class UdpMoney:
    def __init__(self, rows):
        self.support, self.attributed, self.oppose = (defaultdict(int) for _ in range(3))
        for row in rows:
            if not row.candidate_id:
                continue
            if row.direction == 'S':
                self.support[row.candidate_id, row.cycle] += row.cents
                if row.resolved_via in NAME_ATTRIBUTED:
                    self.attributed[row.candidate_id, row.cycle] += row.cents
            elif row.direction == 'O':
                self.oppose[row.candidate_id] += row.cents


def support_entries(ids, money):
    entries = []
    for (candidate_id, cycle), cents in sorted(money.support.items()):
        if candidate_id in ids and cents:
            entry = {'cycle': cycle, 'candidate_id': candidate_id, 'udp_ie_support': dollars(cents)}
            if money.attributed.get((candidate_id, cycle)):
                entry['attribution'] = ATTRIBUTION
            entries.append(entry)
    return sorted(entries, key=lambda e: (e['cycle'], e['candidate_id']))


def note_for(ids, entries, total, opposed, money):
    if not ids:
        return 'No FEC candidate ID on file; not searchable in IE data.'
    if total:
        by_cycle = '; '.join(f'{e["cycle"]}: ${e["udp_ie_support"]:,.2f}' for e in entries)
        note = f'UDP support by cycle ({CURRENT_CYCLE} partial) — {by_cycle}.'
    else:
        note = f'No UDP support spending found in {"/".join(map(str, CYCLES))} IE files.'
    if len(ids) > 1:
        note += f' Summed across {len(ids)} candidate IDs.'
    for e in entries:
        attributed = money.attributed.get((e['candidate_id'], e['cycle']), 0)
        if attributed:
            note += (
                f' Includes ${dollars(attributed):,.2f} of {e["cycle"]} support identified by '
                f'candidate name/state/district; the FEC file left cand_id blank '
                f'for those rows.'
            )
    if opposed:
        note += (
            f' UDP also spent ${dollars(opposed):,.2f} opposing this person '
            f'(excluded from support total).'
        )
    return note


def person_outputs(person, money):
    ids = person.get('fec_candidate_ids') or []
    entries = support_entries(ids, money)
    total = sum(money.support[e['candidate_id'], e['cycle']] for e in entries)
    opposed = sum(money.oppose.get(candidate_id, 0) for candidate_id in ids)
    row = {
        'person_key': person['person_key'],
        'full_name': person['full_name'],
        'fec_candidate_ids': ';'.join(ids),
        'udp_ie_support_career': f'{dollars(total):.2f}',
        'data_notes': note_for(ids, entries, total, opposed, money),
    }
    return row, {
        'person_key': person['person_key'],
        'full_name': person['full_name'],
        'udp_per_cycle': entries,
    }


def main():
    roster = load_roster()
    udp = UdpRows(roster)
    for cycle in CYCLES:
        prior = expected(f'udp_prior_cycle_totals.{cycle}', dollars(udp.cycle_total(cycle)))
        if abs(dollars(udp.cycle_total(cycle)) - prior) >= 0.005:
            raise SystemExit(f'UDP S+O total for {cycle} does not reconcile with the prior pull')
    money = UdpMoney(udp.rows)
    outputs = [person_outputs(p, money) for p in roster]
    people = [row for row, _ in outputs]
    cycles = {entry['person_key']: entry for _, entry in outputs}
    write_gold('udp_people', people, {'udp_ie_support_career'})
    write_gold(
        'udp_per_cycle',
        [
            {**r, 'attribution': r.get('attribution')}
            for r in per_cycle_rows(cycles, 'udp_per_cycle')
        ],
        {'udp_ie_support'},
    )
    print(
        f'blank candidate IDs left unresolved: {len(udp.unresolved)}; '
        f'name-index collisions: {len(udp.collisions)}'
    )


if __name__ == '__main__':
    main()

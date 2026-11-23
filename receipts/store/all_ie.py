#!/usr/bin/env python3
"""All independent expenditures, for every identified candidate, read from the store.

Counted: the latest filing of each expenditure, by a registered committee,
naming an identified candidate. Support and oppose are summed separately,
never netted; blank-direction rows count in the total only. These columns
are separate from total_accepted. Career means the staged IE cycles only.
Rules, validation targets and findings: research/all-ie-notes.md.
"""

from collections import defaultdict
from typing import NamedTuple

from receipts.common.baseline import expected
from receipts.common.files import write_json
from receipts.common.settings import (
    CURRENT_CYCLE,
    DATA_AS_OF,
    PATHS,
    UDP,
    load_roster,
)
from receipts.common.settings import (
    IE_CYCLES as CYCLES,
)
from receipts.domain.blank_candidates import name_key, roster_matches
from receipts.store.gold import write_gold
from receipts.store.read import connect

REPLACED = 'reported_again'
UNREGISTERED, BLANK, NOT_IDENTIFIED = (
    'unregistered_committee',
    'blank_candidate',
    'candidate_not_identified',
)

# Validation targets from the task brief (the coordinator's prior figures).
EXPECTED_ROSTER_TOTAL = {2022: 635.2e6, 2024: 959.1e6, 2026: 2264.3e6}
EXPECTED_TOP_2026 = [  # (committee name, direction, $)
    ('NO GOING BACK PAC INC.', 'O', 202.5e6),
    ('HOUSE MAJORITY PAC', 'O', 146.7e6),  # filed as HMP; name matched loosely
    ('WINSENATE', 'O', 131.1e6),
    ('TEXAS PAC', 'O', 112.2e6),
    ('DEFEND AMERICAN JOBS', 'S', 70.7e6),
]
EXPECTED_SENATE_HOUSE_2026 = (1376.4e6, 887.9e6)
EXPECTED_SO_2026 = (785e6, 1479e6)  # (support, oppose)
BOGUS_FILINGS = [
    (2022, 'C00800508', 'H2NY05118', 'Committee of 300 / Akhlaghy 2022'),
    (2024, 'C00874586', 'P40007304', 'Committee of 300 / Akhlaghy 2024'),
    (2024, 'C00785352', 'P40019226', 'Nader Akhlaghy committee 2024'),
    (2026, 'C00946087', '', 'Warren Buffet / Bettis 2026 (blank cand)'),
    (2026, 'C00944025', '', 'TANKING / APPLE INC DJIA / Bettis 2026 (blank cand)'),
]
FORM_TYPE_COLUMNS = ('form_type', 'form_tp', 'filing_form')


class Expenditure(NamedTuple):
    spender_id: str
    spender_name: str
    candidate_id: str
    candidate_name: str
    cycle: int
    direction: str
    cents: int
    office: str
    state: str
    district: str
    date: str
    transaction_id: str
    excluded_because: str

    @property
    def counted(self):
        return self.excluded_because is None


ROWS = (
    'SELECT spender_id, spender_name, candidate_id, candidate_name, cycle, direction, '
    'amount_cents, office, office_state, office_district, expenditure_date, transaction_id, '
    'excluded_because FROM outside_spending ORDER BY cycle, file_order NULLS LAST'
)


def dollars(cents):
    return cents / 100


def rounded(difference):
    return round(difference + 0.0, 2)  # + 0.0 turns -0.0 into 0.0


def total(rows):
    return sum(x.cents for x in rows)


def tally(rows):
    rows = list(rows)
    return {'rows': len(rows), 'amount': dollars(total(rows))}


def by_direction(rows):
    rows = list(rows)
    return (
        dollars(total(x for x in rows if x.direction == 'S')),
        dollars(total(x for x in rows if x.direction == 'O')),
        dollars(total(rows)),
    )


class Roster:
    def __init__(self, people):
        self.people = people
        self.person_of = {}
        for p in people:
            for candidate_id in p.get('fec_candidate_ids') or []:
                self.person_of.setdefault(candidate_id, p['person_key'])

    @staticmethod
    def ids(person):
        return list(dict.fromkeys(person.get('fec_candidate_ids') or []))


# ---------- what each cycle's file held, and why rows were left out ----------


def near_duplicates(kept):
    """Same committee, candidate, date, amount and direction under different transaction IDs."""
    groups = defaultdict(set)
    for x in kept:
        if x.candidate_id:
            groups[x.spender_id, x.candidate_id, x.date, x.cents, x.direction].add(x.transaction_id)
    repeated = {key: ids for key, ids in groups.items() if len(ids) > 1}
    return {
        'groups': len(repeated),
        'extra_amount_if_collapsed': dollars(
            sum((len(ids) - 1) * key[3] for key, ids in repeated.items())
        ),
    }


def file_exclusions(rows, columns):
    kept = [x for x in rows if x.excluded_because != REPLACED]
    included = [x for x in kept if x.counted]
    return {
        'raw_rows': len(rows),
        'raw_amount': dollars(total(rows)),
        'deduped_rows': len(kept),
        'deduped_amount': dollars(total(kept)),
        'dedup_removed': tally(x for x in rows if x.excluded_because == REPLACED),
        'unregistered_committee': tally(x for x in kept if x.excluded_because == UNREGISTERED),
        'blank_candidate': tally(x for x in kept if x.excluded_because == BLANK),
        'candidate_not_identified': tally(x for x in kept if x.excluded_because == NOT_IDENTIFIED),
        'included': tally(included),
        'has_form_type_column': any(c in FORM_TYPE_COLUMNS for c in columns),
        'near_duplicates_distinct_tran_id': near_duplicates(kept),
        'blank_sup_opp_included': tally(x for x in included if not x.direction),
        'negative_amount_included': tally(x for x in included if x.cents < 0),
    }


# ---------- blank candidate IDs: reported, never added to a total ----------


def name_index(included):
    index, collisions = {}, 0
    for x in included:
        key = name_key(x.candidate_name, x.state, x.district, x.office)
        if key in index and index[key] != x.candidate_id:
            collisions += 1
        index.setdefault(key, x.candidate_id)
    return index, collisions


def blank_attribution(blank_rows, index, roster):
    resolved_all = resolved_roster = fallback_roster = unresolved = 0
    by_committee = defaultdict(int)
    for x in blank_rows:
        candidate_id = index.get(name_key(x.candidate_name, x.state, x.district, x.office))
        if candidate_id:
            resolved_all += x.cents
            if candidate_id in roster.person_of:
                resolved_roster += x.cents
                by_committee[x.spender_id, x.spender_name] += x.cents
            continue
        matches = roster_matches(x.candidate_name, x.state, x.district, roster.people)
        if len(matches) == 1 and len(matches[0].get('fec_candidate_ids') or []) == 1:
            fallback_roster += x.cents
        else:
            unresolved += x.cents
    return {
        'blank_registered_rows': len(blank_rows),
        'blank_registered_amount': dollars(total(blank_rows)),
        'name_index_resolved_all_candidates': dollars(resolved_all),
        'name_index_resolved_roster': dollars(resolved_roster),
        'roster_fallback_resolved_roster': dollars(fallback_roster),
        'unresolved': dollars(unresolved),
        'note': 'DIAGNOSTIC ONLY — none of these amounts is added to any published total.',
        'top_committees_behind_roster_resolved': [
            {'committee_id': committee_id, 'committee_name': name, 'amount': dollars(cents)}
            for (committee_id, name), cents in sorted(by_committee.items(), key=lambda kv: -kv[1])[
                :5
            ]
        ],
    }


# ---------- totals per candidate and cycle, for every identified candidate ----------


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


# ---------- the roster join ----------


def person_totals(person, totals):
    """{support, oppose, total, by_cycle} in cents, or None for a person with no FEC IDs."""
    ids = Roster.ids(person)
    if not ids:
        return None
    by_cycle = {cycle: totals.of(ids, {cycle}) for cycle in CYCLES}
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
    support, oppose, current_total = found['by_cycle'][CURRENT_CYCLE]
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
    """The person's top five spenders, career. A committee keeps the name it used on its
    largest (candidate, cycle) total, since names vary in case between filings."""
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


# ---------- checks against the brief ----------


def validation(udp_totals, prior, summaries):
    udp_diff = udp_totals[2024] - prior[2024]
    checked = {
        'udp_2024_exact': {
            'computed': udp_totals[2024],
            'expected': prior[2024],
            'diff': rounded(udp_diff),
            'status': 'exact' if abs(udp_diff) < 0.005 else 'MISMATCH',
        },
        'roster_totals': {},
        'top_spenders_2026': {},
        'senate_house_2026': {},
        'support_oppose_2026': {},
    }
    for cycle in CYCLES:
        roster_targeted = summaries[cycle]['roster_targeted']
        got, want = roster_targeted['total'], EXPECTED_ROSTER_TOTAL[cycle]
        checked['roster_totals'][cycle] = {
            'computed': got,
            'expected': want,
            'diff': rounded(got - want),
            'diff_pct': round(100 * (got - want) / want, 2),
            'support': roster_targeted['support'],
            'oppose': roster_targeted['oppose'],
            'status': 'within_1pct' if abs(got - want) / want < 0.01 else 'CHECK',
        }
    top_2026 = summaries[2026]['top_committees_roster_targeted']
    for name, direction, want in EXPECTED_TOP_2026:
        hit = next(
            (
                c
                for c in top_2026
                if name in c['committee_name'].upper()
                or (name == 'HOUSE MAJORITY PAC' and c['committee_name'].upper() == 'HMP')
            ),
            None,
        )
        if hit is None:
            checked['top_spenders_2026'][name] = {'status': 'NOT FOUND in top 10'}
            continue
        got = hit['support'] if direction == 'S' else hit['oppose']
        checked['top_spenders_2026'][name] = {
            'committee_id': hit['committee_id'],
            'committee_name': hit['committee_name'],
            'direction': direction,
            'computed': got,
            'expected': want,
            'diff': rounded(got - want),
            'status': 'match' if abs(got - want) / want < 0.005 else 'CHECK',
        }
    roster_2026 = summaries[2026]['roster_targeted']
    for key, fields, wanted in [
        ('senate_house_2026', ('senate', 'house'), EXPECTED_SENATE_HOUSE_2026),
        ('support_oppose_2026', ('support', 'oppose'), EXPECTED_SO_2026),
    ]:
        checked[key] = {
            field: {
                'computed': roster_2026[field],
                'expected': want,
                'diff': rounded(roster_2026[field] - want),
            }
            for field, want in zip(fields, wanted, strict=True)
        }
    return checked


def bogus_examples(kept):
    examples = {}
    for cycle, committee_id, candidate_id, label in BOGUS_FILINGS:
        hit = [
            x
            for x in kept
            if x.cycle == cycle
            and x.spender_id == committee_id
            and (not candidate_id or x.candidate_id == candidate_id)
        ]
        examples[label] = {
            'committee_id': committee_id,
            'candidate_id': candidate_id or '(blank)',
            'rows_in_file_after_dedup': len(hit),
            'amount_in_file_after_dedup': dollars(total(hit)),
            'amount_included': dollars(total(x for x in hit if x.counted)),
            'excluded_because': 'unregistered committee (not in same-cycle cm.txt)'
            + ('' if candidate_id else '; candidate ID blank'),
        }
    return examples


def roster_career_totals(roster, per_person, totals):
    """Row sums count a candidate ID shared by two roster entries twice; the distinct
    totals take that back out."""
    sharing = defaultdict(set)
    for p in roster.people:
        for candidate_id in Roster.ids(p):
            sharing[candidate_id].add(p['person_key'])
    names = {p['person_key']: p['full_name'] for p in roster.people}
    shared, overcount = [], [0, 0, 0]
    for candidate_id, person_keys in sorted(sharing.items()):
        if len(person_keys) < 2:
            continue
        amounts = totals.of({candidate_id}, set(CYCLES))
        extra = len(person_keys) - 1
        overcount = [o + extra * a for o, a in zip(overcount, amounts, strict=True)]
        shared.append(
            {
                'candidate_id': candidate_id,
                'person_keys': sorted(person_keys),
                'full_names': sorted({names[k] for k in person_keys}),
                'shared_id_career_total': dollars(amounts[2]),
                'overcounted_in_row_sums': dollars(extra * amounts[2]),
            }
        )
    found = [v for v in per_person.values() if v]
    row_sums = [sum(v[field] for v in found) for field in ('support', 'oppose', 'total')]
    return {
        'support': dollars(row_sums[0]),
        'oppose': dollars(row_sums[1]),
        'total': dollars(row_sums[2]),
        'n_persons_with_spending': sum(1 for v in found if v['total'] != 0),
        'n_persons_unknown_no_fec_id': sum(1 for v in per_person.values() if v is None),
        'duplicate_roster_entries': shared,
        'distinct_person_totals': {
            field: dollars(row_sum - over)
            for field, row_sum, over in zip(
                ('support', 'oppose', 'total'), row_sums, overcount, strict=True
            )
        },
    }


META = {
    'script': 'receipts/store/all_ie.py',
    'data_as_of': DATA_AS_OF,
    'cycles': list(CYCLES),
    'current_cycle': CURRENT_CYCLE,
    'note': 'Career totals cover the staged IE cycles (2022+2024+2026) ONLY. '
    'No IE files are staged for earlier cycles; these are not full-career totals. '
    'All-IE columns are separate from total_accepted and are never blended into it.',
    'filter_rules': [
        'dedup by (spe_id, tran_id): keep latest receipt_dat, tie-break highest file_num; '
        'blank tran_id never deduped against another row',
        'registered committee only: spe_id in same-cycle data/raw/cm/<cycle>/cm.txt',
        'identified candidate only: non-blank cand_id in any staged weball file (1980-2026) '
        'OR a roster FEC candidate ID; blank cand_id rows excluded from published totals',
        'support and oppose summed separately, never netted; blank sup_opp rows count in total only',
    ],
}
FORM_TYPE_FINDING = (
    'No form-type column exists in the bulk IE files, so F24/F3X cannot be '
    'separated by form. The bulk file carries ONE copy per expenditure (the '
    'notice copy; pull-log-b §7 verified file_num/image_num match the F24 '
    'filing), and (spe_id, tran_id) dedup removes any same-transaction repeat. '
    'Proof: UDP 2024 deduped S+O reproduces the tracker total $38,044,932.69 '
    'to the cent — a file that double-counted across form types would be ~2x. '
    'Near-duplicate rows (same committee/candidate/date/amount/direction, '
    'different tran_id AND different image_num = different filings) are '
    'treated as separate expenditures and quantified per cycle in exclusions[].'
)
COVERAGE = {
    'staged_cycles': list(CYCLES),
    'earlier_cycles_available': 'Per the FEC independent-expenditures file description '
    '(fetched Nov 12, 2026), historical data is available beginning with the 2010 '
    'cycle, and the FEC bulk-data index publishes independent_expenditure_YYYY.csv '
    'per cycle. Files for 2010/2012/2014/2016/2018/2020 exist and are NOT staged '
    'here (each ~14-19 MB, same format) — expanding to them is a follow-up, not '
    'done in this pull. Pre-2010 cycles have no such file.',
    'files_not_staged': [2010, 2012, 2014, 2016, 2018, 2020],
}


def read_store():
    with connect() as db:
        rows = [Expenditure(*row) for row in db.execute(ROWS).fetchall()]
        columns = dict(
            db.execute("SELECT cycle, columns FROM files_read WHERE file = 'ie'").fetchall()
        )
    return rows, {cycle: (text or '').split(',') for cycle, text in columns.items()}


def main():
    rows, columns = read_store()
    roster = Roster(load_roster())
    of_cycle = {cycle: [x for x in rows if x.cycle == cycle] for cycle in CYCLES}
    kept = [x for x in rows if x.excluded_because != REPLACED]
    included = [x for x in kept if x.counted]

    exclusions = {cycle: file_exclusions(of_cycle[cycle], columns[cycle]) for cycle in CYCLES}
    udp_totals = {
        cycle: dollars(
            total(
                x for x in of_cycle[cycle] if x.excluded_because != REPLACED and x.spender_id == UDP
            )
        )
        for cycle in CYCLES
    }
    prior = {
        cycle: expected(f'udp_prior_cycle_totals.{cycle}', udp_totals[cycle]) for cycle in CYCLES
    }
    for cycle in CYCLES:
        if abs(udp_totals[cycle] - prior[cycle]) >= 0.005:
            raise SystemExit(f'UDP S+O total for {cycle} does not reconcile with the prior pull')

    blank_diagnostic, collisions = {}, 0
    for cycle in CYCLES:
        index, found = name_index(x for x in included if x.cycle == cycle)
        collisions += found
        blank_diagnostic[cycle] = blank_attribution(
            [x for x in kept if x.cycle == cycle and x.excluded_because == BLANK], index, roster
        )

    totals = CandidateTotals(included)
    summaries = {
        cycle: cycle_summary([x for x in included if x.cycle == cycle], roster) for cycle in CYCLES
    }
    per_person = {p['person_key']: person_totals(p, totals) for p in roster.people}

    top = {p['person_key']: top_committees_for(p, totals) for p in roster.people}
    people = [csv_row(p, per_person[p['person_key']]) for p in roster.people]
    by_candidate = per_candidate_entries(totals, roster)
    write_gold('all_ie_people', people, {c for c in people[0] if c.startswith('all_ie_')})
    write_gold(
        'all_ie_per_candidate_cycle',
        [{k: v for k, v in e.items() if k != 'top_committees'} for e in by_candidate],
        {'all_ie_support', 'all_ie_oppose', 'all_ie_total', 'no_direction_amount'},
    )
    write_gold(
        'all_ie_top_committees',
        [
            {'person_key': person_key, 'entry': n, **committee}
            for person_key, committees in top.items()
            for n, committee in enumerate(committees or [])
        ],
        {'support', 'oppose', 'total'},
    )
    write_json(
        PATHS.intermediate / 'all_ie_per_cycle.json',
        {
            'meta': {
                **META,
                'form_type_double_count_check': {
                    'bulk_file_has_form_type_column': any(
                        e['has_form_type_column'] for e in exclusions.values()
                    ),
                    'finding': FORM_TYPE_FINDING,
                },
                'coverage': COVERAGE,
            },
            'exclusions_by_cycle': {str(c): exclusions[c] for c in CYCLES},
            'blank_attribution_diagnostic': {str(c): blank_diagnostic[c] for c in CYCLES},
            'name_index_collisions': collisions,
            'per_cycle_summaries': {str(c): summaries[c] for c in CYCLES},
            'per_candidate_per_cycle': by_candidate,
            'validation': validation(udp_totals, prior, summaries),
            'bogus_examples': bogus_examples(kept),
            'roster_career_totals': roster_career_totals(roster, per_person, totals),
        },
    )
    for cycle in CYCLES:
        roster_targeted = summaries[cycle]['roster_targeted']
        print(
            f'{cycle} roster: S ${roster_targeted["support"]:,.2f} / '
            f'O ${roster_targeted["oppose"]:,.2f} / total ${roster_targeted["total"]:,.2f}'
        )


if __name__ == '__main__':
    main()

"""All-IE, UDP support, and opposition credits, checked against the baseline."""

import csv
import json
from pathlib import Path

from receipts.square_one import ie, money, opposition, roster

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / 'data' / 'raw'
IE_CYCLES = [2022, 2024, 2026]
UDP = 'C00799031'


def _listed_committees():
    with open(ROOT / 'data' / 'source' / 'pro_israel_pacs.csv', newline='') as f:
        return sorted({row['committee_id'] for row in csv.DictReader(f)})


def test_split_person_name():
    assert ie.split_person_name('Hakeem S. Jeffries') == ('Hakeem', 'Jeffries')
    assert ie.split_person_name('Tom Kean, Jr.') == ('Tom', 'Kean')
    assert ie.split_person_name('Chris Van Hollen') == ('Chris', 'Hollen')
    assert ie.split_person_name('Madonna') == ('', 'Madonna')


def test_opposition_credit_single_backed_race():
    def row(cand, direction, cents, name='X, Y'):
        r = ie.IeRow.__new__(ie.IeRow)
        r.spender_id = 'C00799031'
        r.candidate_id = cand
        r.candidate_name = name
        r.cycle = 2024
        r.direction = direction
        r.cents = cents
        r.office = 'H'
        r.state = 'NY'
        r.district = '16'
        r.election_type = 'P'
        r.excluded_because = None
        r.resolved_via = None
        return r

    rows = [
        row('H4NY16087', 'S', 100, 'LATIMER, GEORGE'),
        row('H0NY16143', 'O', 500, 'BOWMAN, JAMAAL'),
        row('H4NY16087', 'O', 50, 'LATIMER, GEORGE'),
    ]
    credits, _, uncredited = opposition.opposition_credits(rows, {'H4NY16087': 'L000606'})
    assert credits == {('L000606', 2024): 500}
    assert uncredited == []
    two_backed = rows + [row('H9NY99999', 'S', 10, 'OTHER, PERSON')]
    credits, _, uncredited = opposition.opposition_credits(two_backed, {'H4NY16087': 'L000606'})
    assert credits == {}
    assert len(uncredited) == 1


def test_full_ie_derivation_matches_baseline():
    people = roster.load_roster(ROOT / 'congress-money-tracker.json')
    person_of = roster.person_of(people)
    weball = money.derive_weball(BULK, list(range(1980, 2027, 2)))
    rows, stats = ie.derive_ie(BULK, IE_CYCLES, people, weball)

    baseline = json.loads((ROOT / 'data' / 'source' / 'baseline.json').read_text())
    totals = {
        key.removeprefix('methodology_totals.'): value
        for key, value in baseline.items()
        if key.startswith('methodology_totals.')
    }
    by_cycle = ie.per_candidate_cycle(rows)
    known_ids = {cid for p in people for cid in p['fec_candidate_ids']}

    def roster_cycle_total(cycle, index):
        return sum(
            cents[index] for (cid, c), cents in by_cycle.items() if c == cycle and cid in known_ids
        )

    for cycle, expected in (
        (2022, baseline['all_ie_cycle_totals.2022']),
        (2024, baseline['all_ie_cycle_totals.2024']),
        (2026, baseline['all_ie_cycle_totals.2026']),
    ):
        assert roster_cycle_total(cycle, 2) == round(expected * 100), cycle

    assert sum(cents[0] for (cid, _), cents in by_cycle.items() if cid in known_ids) == round(
        totals['all_ie_support_career'] * 100
    )
    assert sum(cents[1] for (cid, _), cents in by_cycle.items() if cid in known_ids) == round(
        totals['all_ie_oppose_career'] * 100
    )
    assert sum(cents[2] for (cid, _), cents in by_cycle.items() if cid in known_ids) == round(
        totals['all_ie_total_career'] * 100
    )

    # UDP support + opposition credit, with blank IDs resolved per spender.
    udp_rows = [r for r in rows if r.spender_id == UDP]
    unresolved, _ = ie.resolve_blank_ids(udp_rows, people)
    udp_support = ie.per_candidate_cycle(udp_rows)
    assert sum(cents[0] for (cid, _), cents in udp_support.items() if cid in known_ids) == round(
        totals['udp_ie_support_career'] * 100
    )
    credits, _, _ = opposition.opposition_credits(udp_rows, person_of)
    assert sum(credits.values()) == round(totals['udp_ie_opposing_opponents_career'] * 100)

    # Pro-Israel IE support + opposition credit, spender by spender.
    listed = _listed_committees()
    pi_support_by_person, pi_credit = opposition.pro_israel_support_and_credits(
        rows, listed, people, person_of
    )
    pi_support = sum(pi_support_by_person.values())
    assert pi_support == round(baseline['pro_israel.pro_israel_ie_support_career_total'] * 100)
    assert sum(pi_credit.values()) == round(
        baseline['pro_israel.pro_israel_opp_credit_career_total'] * 100
    )

    # Spot cases: Latimer 2024 UDP support, and his opposition credit for
    # the Bowman race (both verified in the Latimer pilot report).
    assert udp_support[('H4NY16087', 2024)][0] == 468256029
    udp_credit, _, _ = opposition.opposition_credits(udp_rows, person_of)
    assert udp_credit[('L000606', 2024)] == 986549296
    # Boafo: the dataset's all-IE support (Track AIPAC's $5,734,013.28 is
    # their comparable total, not this column).
    dataset = json.loads((ROOT / 'congress-money-tracker.json').read_text())
    boafo = [r for r in dataset if r['full_name'].startswith('Adrian')][0]
    assert boafo['all_ie_support_career'] == 12093527.71
    assert sum(
        c[0] for (cid, _), c in by_cycle.items() if cid in boafo['fec_candidate_ids']
    ) == round(boafo['all_ie_support_career'] * 100)
    # Blank-direction rows count in the total, not in support or oppose:
    # Tran's 2024 total exceeds his support + oppose by the blank rows.
    tran = [r for r in dataset if r['full_name'].startswith('Derek Tran')][0]
    assert by_cycle[('H4CA45170', 2024)][2] == round(
        sum(c['all_ie_total'] for c in tran['cycles'] if c['cycle'] == 2024) * 100
    )

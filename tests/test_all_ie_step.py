from receipts.store.all_ie import outside_spending
from receipts.store.ie_rows import Expenditure, Roster


def spent(spender, candidate, cycle, direction, cents, name=None, office='H'):
    return Expenditure(
        spender, name or spender, candidate, 'NAME', cycle, direction, cents,
        office, 'NY', '16', '2024-01-01', f'{spender}-{cents}', None,
    )  # fmt: skip


def person(key, *ids):
    return {'person_key': key, 'full_name': key.title(), 'fec_candidate_ids': list(ids)}


ROSTER = Roster([person('p', 'H1', 'S1'), person('no_id')])


def by_key(spending):
    return {row['person_key']: row for row in spending.people}


def test_support_and_oppose_are_summed_apart_and_blank_direction_counts_in_total_only():
    spending = outside_spending(
        [
            spent('C1', 'H1', 2024, 'S', 100_00),
            spent('C2', 'S1', 2026, 'O', 40_00),
            spent('C3', 'H1', 2026, '', 5_00),
        ],
        ROSTER,
    )
    row = by_key(spending)['p']
    assert (row['all_ie_support_career'], row['all_ie_oppose_career']) == ('100.00', '40.00')
    assert row['all_ie_total_career'] == '145.00'
    assert (row['all_ie_support_2026'], row['all_ie_total_2026']) == ('0.00', '45.00')


def test_a_person_without_an_fec_id_is_not_searchable():
    spending = outside_spending([spent('C1', 'H1', 2024, 'S', 100_00)], ROSTER)
    row = by_key(spending)['no_id']
    assert row['all_ie_total_career'] == ''
    assert row['data_notes'].startswith('No FEC candidate ID on file')
    assert spending.top['no_id'] is None


def test_top_committees_group_across_ids_keep_the_largest_name_and_stop_at_five():
    rows = [spent(f'C{n}', 'H1', 2024, 'S', n * 100) for n in range(1, 7)]
    rows += [
        spent('C9', 'H1', 2022, 'O', 50_00, name='Small Name'),
        spent('C9', 'S1', 2024, 'O', 70_00, name='BIG NAME'),
    ]
    top = outside_spending(rows, ROSTER).top['p']
    assert [c['committee_id'] for c in top] == ['C9', 'C6', 'C5', 'C4', 'C3']
    assert top[0] == {
        'committee_id': 'C9',
        'committee_name': 'BIG NAME',
        'support': 0.0,
        'oppose': 120.0,
        'total': 120.0,
        'rows': 2,
    }


def test_off_roster_money_counts_for_all_candidates_but_not_the_roster():
    spending = outside_spending(
        [spent('C1', 'H1', 2024, 'S', 100_00), spent('C1', 'H8OFF', 2024, 'S', 900_00)], ROSTER
    )
    summary = spending.summaries[2024]
    assert summary['all_candidates']['total'] == 1000.0
    assert summary['roster_targeted']['total'] == 100.0

from receipts.domain.money import Money
from receipts.store.accepted_money import COLUMNS, accepted_by_person

CYCLES = range(2020, 2028, 2)


def amounts(**given):
    return {c: Money(given.get(c, 0)) for c in COLUMNS}


def person(key, *ids):
    return {'person_key': key, 'full_name': key.title(), 'fec_candidate_ids': list(ids)}


def run(people, counted, filed=None, on_file=None):
    filed = set(counted) if filed is None else filed
    on_file = {candidate for candidate, _ in counted} if on_file is None else on_file
    rows, per_cycle = accepted_by_person(people, counted, filed, on_file, CYCLES)
    return {r['person_key']: r for r in rows}, per_cycle


def test_money_sums_across_candidate_ids_and_cycles():
    rows, per_cycle = run(
        [person('switcher', 'H1', 'S1')],
        {
            ('H1', 2022): amounts(individual=100_00, corporate_pac=5_00),
            ('S1', 2024): amounts(individual=250_00, aipac_pac_direct=10_00),
        },
    )
    row = rows['switcher']
    assert row['individual_contribution_total_career'] == '350.00'
    assert row['corporate_pac_career'] == '5.00'
    assert row['aipac_pac_direct_career'] == '10.00'
    assert row['fec_candidate_ids'] == 'H1;S1'
    assert [(e['cycle'], e['candidate_id']) for e in per_cycle['switcher']['per_cycle']] == [
        (2022, 'H1'),
        (2024, 'S1'),
    ]


def test_cycles_outside_the_career_range_are_left_out():
    rows, _ = run([person('p', 'H1')], {('H1', 2018): amounts(individual=1_00)})
    assert rows['p']['individual_contribution_total_career'] == '0.00'


def test_a_filed_cycle_that_nets_to_zero_is_still_listed():
    _, per_cycle = run([person('p', 'H1')], {('H1', 2024): amounts()})
    assert [e['cycle'] for e in per_cycle['p']['per_cycle']] == [2024]


def test_notes_say_why_a_person_has_no_money():
    rows, _ = run(
        [person('no_id'), person('dormant', 'H9'), person('zero', 'H1')],
        {('H1', 2024): amounts()},
        on_file={'H1'},
    )
    assert rows['no_id']['data_notes'] == 'no FEC candidate IDs in roster'
    assert rows['dormant']['data_notes'] == 'no FEC activity found'
    assert rows['zero']['data_notes'] == 'FEC activity found; all totals zero'


def test_notes_flag_a_shared_id_and_a_net_negative_aipac_total():
    rows, _ = run(
        [person('first', 'H1'), person('second', 'H1')],
        {('H1', 2026): amounts(individual=1_00, aipac_pac_direct=-10_000_00)},
    )
    assert 'duplicate roster entry: FEC ID shared with second' in rows['first']['data_notes']
    assert 'net-negative AIPAC total' in rows['first']['data_notes']


def test_substituted_aipac_flows_into_the_career_total():
    from receipts.square_one.corrected import Corrected, substitute_aipac

    corrected = Corrected(
        {
            'snapshot': '2026-11-22',
            'counts': {'A': {}},
            'corrected_per_cycle': {
                'barr|2026': {
                    'aipac_a_cents': 5235943,
                    'aipac_b_cents': 5235943,
                    'pro_israel_a_cents': 9624746,
                    'pro_israel_b_cents': 9124746,
                    'jfc_aipac_cents': 0,
                    'jfc_other_cents': 0,
                }
            },
            'transfers_from_corrected': {},
            'transfers_to_corrected': {},
        }
    )
    barr = {
        'person_key': 'barr',
        'full_name': 'Barr',
        'fec_candidate_ids': ['H1', 'S1'],
        'chamber_120': 'Senate',
        'chamber_119': 'House',
    }
    counted = {
        ('H1', 2026): amounts(individual=100_00, aipac_pac_direct=500_00),
        ('S1', 2026): amounts(aipac_pac_direct=0),
    }
    filed = {('H1', 2026), ('S1', 2026)}
    counted, filed = substitute_aipac(
        counted, filed, [barr], [], corrected, COLUMNS, {'H1': 'H', 'S1': 'S'}
    )
    rows, per_cycle = run([person('barr', 'H1', 'S1')], counted, filed, {'H1', 'S1'})
    assert rows['barr']['aipac_pac_direct_career'] == '52359.43'
    assert rows['barr']['individual_contribution_total_career'] == '100.00'
    assert [e['aipac_pac_direct'] for e in per_cycle['barr']['per_cycle']] == ['0.00', '52359.43']

from receipts.store.udp import support_by_person
from receipts.store.udp_rows import UdpRow, UdpRows

LATIMER = {
    'person_key': 'L000001',
    'full_name': 'George Latimer',
    'last_name': 'Latimer',
    'first_name': 'George',
    'state': 'NY',
    'district_119': 16,
    'fec_candidate_ids': ['H4NY16087'],
}
DAVIS = {
    'person_key': 'D000001',
    'full_name': 'Donald Davis',
    'last_name': 'Davis',
    'first_name': 'Donald',
    'state': 'NC',
    'district_119': 1,
    'fec_candidate_ids': ['H2NC01131'],
}
BELL = {
    'person_key': 'B000001',
    'full_name': 'Wesley Bell',
    'last_name': 'Bell',
    'first_name': 'Wesley',
    'state': 'MO',
    'district_120': 1,
    'fec_candidate_ids': ['H4MO01134', 'S4MO00250'],
}
NO_ID = {
    'person_key': 'A000001',
    'full_name': 'Alan Appointed',
    'last_name': 'Appointed',
    'first_name': 'Alan',
    'state': 'OK',
    'fec_candidate_ids': [],
}
ROSTER = [LATIMER, DAVIS, BELL, NO_ID]


def row(candidate_id, cycle, direction, cents, name='', state='', district='', office='H'):
    return UdpRow(candidate_id, name, cycle, direction, cents, office, state, district, 'P', 't')


def outputs(filed):
    people, cycles = support_by_person(UdpRows(filed, ROSTER), ROSTER)
    return {p['person_key']: p for p in people}, cycles


def test_support_sums_by_cycle_and_oppose_is_only_noted():
    people, cycles = outputs(
        [
            row('H4NY16087', 2022, 'S', 10_000),
            row('H4NY16087', 2024, 'S', 5_000),
            row('H4NY16087', 2024, 'O', 3_000),
        ]
    )
    latimer = people['L000001']
    assert latimer['udp_ie_support_career'] == '150.00'
    assert [e['udp_ie_support'] for e in cycles['L000001']['udp_per_cycle']] == [100.0, 50.0]
    assert 'UDP also spent $30.00 opposing this person' in latimer['data_notes']


def test_a_blank_id_support_row_resolves_by_name_and_says_so():
    people, cycles = outputs([row('', 2022, 'S', 20_000, 'DAVIS, DONALD', 'NC', '01')])
    (entry,) = cycles['D000001']['udp_per_cycle']
    assert entry['candidate_id'] == 'H2NC01131'
    assert entry['attribution'].startswith('name_state_district_office_match')
    assert 'identified by candidate name/state/district' in people['D000001']['data_notes']


def test_support_under_two_ids_is_summed_and_noted():
    people, _ = outputs([row('H4MO01134', 2024, 'S', 1_000), row('S4MO00250', 2026, 'S', 2_000)])
    assert people['B000001']['udp_ie_support_career'] == '30.00'
    assert 'Summed across 2 candidate IDs' in people['B000001']['data_notes']


def test_a_person_without_an_fec_id_is_not_searchable():
    people, cycles = outputs([row('H4NY16087', 2022, 'S', 10_000)])
    assert people['A000001']['udp_ie_support_career'] == '0.00'
    assert people['A000001']['data_notes'].startswith('No FEC candidate ID on file')
    assert cycles['A000001']['udp_per_cycle'] == []


def test_support_for_someone_off_the_roster_counts_for_no_one():
    people, _ = outputs([row('H8XX99999', 2024, 'S', 50_000)])
    assert {p['udp_ie_support_career'] for p in people.values()} == {'0.00'}


def test_cycle_totals_count_support_and_oppose():
    udp = UdpRows([row('H4NY16087', 2024, 'S', 5_000), row('H4NY16087', 2024, 'O', 3_000)], ROSTER)
    assert udp.cycle_total(2024) == 8_000
    assert udp.cycle_total(2022) == 0

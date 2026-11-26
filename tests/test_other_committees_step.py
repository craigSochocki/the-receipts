from receipts.domain.money import Money
from receipts.domain.roster import Roster
from receipts.store.other_committees import (
    AIPAC,
    CORPORATE,
    LAMB_CANDIDATE,
    WINRED_KIND,
    committees_by_person,
    fill_ledger,
)


def person(key, *ids):
    return {'person_key': key, 'full_name': key.title(), 'fec_candidate_ids': list(ids)}


def contribution(candidate_id, cycle, column, cents, earmarked=0, kind=''):
    return candidate_id, cycle, column, kind, cents, earmarked


def run(people, rows, note=''):
    found, cycles = committees_by_person(Roster(people), fill_ledger(rows), note)
    return {p['person_key']: p for p in found}, cycles


def test_classes_sum_across_ids_and_cycles_into_their_own_columns():
    people, cycles = run(
        [person('p', 'H1', 'S1')],
        [
            contribution('H1', 2022, 'labor_pacs', 1_000_00),
            contribution('S1', 2024, 'labor_pacs', 500_00, earmarked=100_00),
            contribution('S1', 2024, 'party_committees', 250_00),
        ],
    )
    row = people['p']
    assert row['labor_pacs_career'] == '1500.00'
    assert row['labor_pacs_earmark_transmitted_career'] == '100.00'
    assert row['other_committees_total_career'] == '1750.00'
    assert [(e['cycle'], e['candidate_id']) for e in cycles['p']['per_cycle']] == [
        (2022, 'H1'),
        (2024, 'S1'),
    ]


def test_corporate_and_aipac_money_never_count_as_other_committees():
    people, cycles = run(
        [person('p', 'H1')],
        [contribution('H1', 2024, CORPORATE, 9_000_00), contribution('H1', 2024, AIPAC, 5_000_00)],
    )
    assert people['p']['other_committees_total_career'] == '0.00'
    assert people['p']['data_notes'] == 'FEC activity found; all other-committee totals zero'
    assert cycles['p']['per_cycle'] == []


def test_a_winred_conduit_stays_unclassified_and_is_noted():
    people, cycles = run(
        [person('p', 'H1')],
        [contribution('H1', 2024, 'other_unclassified', -52_00, kind=WINRED_KIND)],
    )
    assert people['p']['other_unclassified_career'] == '-52.00'
    assert 'includes WinRed conduit net -52.00' in people['p']['data_notes']
    assert cycles['p']['per_cycle'][0]['winred_included'] == '-52.00'


def test_a_person_without_an_fec_id_shows_blanks_not_zeros():
    people, _ = run([person('no_id')], [])
    assert people['no_id']['labor_pacs_career'] == ''
    assert people['no_id']['data_notes'] == 'no FEC candidate IDs in roster'


def test_the_reconciliation_note_lands_only_on_the_named_case():
    people, _ = run(
        [person('named', LAMB_CANDIDATE), person('other', 'H1')], [], note='PENDING RECONCILIATION'
    )
    assert people['named']['reconciliation_note'] == 'PENDING RECONCILIATION'
    assert people['other']['reconciliation_note'] == ''


def test_the_aipac_cross_check_uses_the_corrected_total():
    from receipts.domain.ledger import Ledger
    from receipts.square_one.corrected import Corrected
    from receipts.store.other_committees import LEDGER_COLUMNS, corrected_aipac_career

    corrected = Corrected(
        {
            'snapshot': '2026-11-22',
            'counts': {'A': {}},
            'corrected_per_cycle': {
                'p|2026': {
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
    ledger = Ledger(LEDGER_COLUMNS)
    ledger.add('H1', 2020, AIPAC, Money(100_00))
    ledger.add('H1', 2026, AIPAC, Money(500_00))
    ledger.add('S1', 2026, AIPAC, Money(0))
    roster = Roster([person('p', 'H1', 'S1')])
    assert corrected_aipac_career(ledger, roster, corrected) == Money(100_00 + 5235943)

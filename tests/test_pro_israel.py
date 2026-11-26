from receipts.store.pro_israel import per_cycle, person_row


def money(pac, ie, credit=0):
    return {'pro_israel_pac': pac, 'pro_israel_ie_support': ie, 'pro_israel_opp_credit': credit}


AMOUNTS = {('H1', 2022): money(500, 0), ('S1', 2024): money(0, 900), ('H9', 2024): money(7, 7)}


def test_money_is_summed_over_the_persons_own_candidate_ids_by_cycle():
    person = {'person_key': 'p', 'fec_candidate_ids': ['H1', 'S1']}
    cycles = per_cycle(person, AMOUNTS, {'p': {2024: 40}})
    assert cycles == [{'cycle': 2022, **money(500, 0)}, {'cycle': 2024, **money(0, 900, 40)}]
    assert person_row(person, cycles) == {
        'person_key': 'p',
        'pro_israel_pac_career': 500,
        'pro_israel_ie_support_career': 900,
        'pro_israel_opp_credit_career': 40,
    }


def test_a_person_without_an_fec_id_has_unknown_money():
    person = {'person_key': 'q', 'fec_candidate_ids': []}
    assert person_row(person, per_cycle(person, AMOUNTS))['pro_israel_pac_career'] is None


def test_substituted_pro_israel_replaces_the_pas2_total_and_adds_a_missing_cycle():
    from receipts.square_one.corrected import Corrected

    corrected = Corrected(
        {
            'snapshot': '2026-11-22',
            'counts': {'A': {}},
            'corrected_per_cycle': {
                'p|2022': {
                    'aipac_a_cents': 100,
                    'aipac_b_cents': 100,
                    'pro_israel_a_cents': 9624746,
                    'pro_israel_b_cents': 9124746,
                    'jfc_aipac_cents': 0,
                    'jfc_other_cents': 0,
                },
                'p|2026': {
                    'aipac_a_cents': 5235943,
                    'aipac_b_cents': 5235943,
                    'pro_israel_a_cents': 123456,
                    'pro_israel_b_cents': 123456,
                    'jfc_aipac_cents': 0,
                    'jfc_other_cents': 0,
                },
            },
            'transfers_from_corrected': {},
            'transfers_to_corrected': {},
        }
    )
    person = {'person_key': 'p', 'fec_candidate_ids': ['H1', 'S1']}
    cycles = per_cycle(person, AMOUNTS, {'p': {2024: 40}}, corrected)
    assert cycles == [
        {'cycle': 2022, **money(9624746, 0)},
        {'cycle': 2024, **money(0, 900, 40)},
        {'cycle': 2026, **money(123456, 0)},
    ]
    assert person_row(person, cycles)['pro_israel_pac_career'] == 9624746 + 123456

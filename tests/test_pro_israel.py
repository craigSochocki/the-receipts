from receipts.store.pro_israel import per_cycle, person_row


def money(pac, ie):
    return {'pro_israel_pac': pac, 'pro_israel_ie_support': ie}


AMOUNTS = {('H1', 2022): money(500, 0), ('S1', 2024): money(0, 900), ('H9', 2024): money(7, 7)}


def test_money_is_summed_over_the_persons_own_candidate_ids_by_cycle():
    person = {'person_key': 'p', 'fec_candidate_ids': ['H1', 'S1']}
    cycles = per_cycle(person, AMOUNTS)
    assert cycles == [{'cycle': 2022, **money(500, 0)}, {'cycle': 2024, **money(0, 900)}]
    assert person_row(person, cycles) == {
        'person_key': 'p',
        'pro_israel_pac_career': 500,
        'pro_israel_ie_support_career': 900,
    }


def test_a_person_without_an_fec_id_has_unknown_money():
    person = {'person_key': 'q', 'fec_candidate_ids': []}
    assert person_row(person, per_cycle(person, AMOUNTS))['pro_israel_pac_career'] is None

from receipts.domain.term import term_record


def record(year, **money):
    base = {'individual': 0, 'corp': 0, 'aipac_direct': 0, 'udp_benefit': 0, 'dirty': 0}
    return {'cycle': year, **base, **money, 'unopposed': year == 2022, 'cash_on_hand': year,
            'dep_share': 0.5, 'clean': True}  # fmt: skip


def test_money_is_summed_from_the_election_on_and_shares_come_from_the_sums():
    cycles = [record(2020, corp=1000), record(2022, individual=90, corp=10), record(2024, corp=20)]
    term = term_record(cycles, 2022)
    assert (term['cycle'], term['individual'], term['corp']) == (2022, 90, 30)
    assert term['dep_share'] == round(30 / 120, 4)
    assert term['unopposed'] is True and term['cash_on_hand'] == 2024
    assert term['aipac_udp_flag'] is False

"""The corrected-figures reader and the store-step substitutions.

Fixtures are inline: the derivation's output is a build input, so these
tests must run before any rebuild produces derived.json.
"""

import pytest

from receipts.domain.campaign_finances import CampaignFinances
from receipts.domain.money import Money
from receipts.square_one.corrected import (
    API_CYCLES,
    Corrected,
    distribute,
    kept_candidate_id,
    load,
    substitute_aipac,
    substitute_transfers,
)

COLUMNS = [
    'individual',
    'aipac_pac_direct',
    'aipac_earmark_transmitted',
    'corporate_pac',
    'corporate_earmark_transmitted',
]


def fake_output():
    return {
        'snapshot': '2026-11-22',
        'counts': {'A': {'term_flag': 299}},
        'corrected_per_cycle': {
            'B001282|2026': {
                'aipac_a_cents': 5235943,
                'aipac_b_cents': 5235943,
                'pro_israel_a_cents': 9624746,
                'pro_israel_b_cents': 9124746,
                'jfc_aipac_cents': 0,
                'jfc_other_cents': 500000,
            },
            'H001082|2026': {
                'aipac_a_cents': 1000000,
                'aipac_b_cents': 1000000,
                'pro_israel_a_cents': 1000000,
                'pro_israel_b_cents': 1000000,
                'jfc_aipac_cents': 0,
                'jfc_other_cents': 0,
            },
        },
        'transfers_from_corrected': {'B001282|2026': 282810951, 'B001282|2024': 48586314},
        'transfers_to_corrected': {'B001282|2026': 5681782, 'B001282|2024': 0},
    }


def person(key, ids, chamber_120='Senate', chamber_119='House'):
    return {
        'person_key': key,
        'full_name': key,
        'fec_candidate_ids': ids,
        'chamber_120': chamber_120,
        'chamber_119': chamber_119,
    }


def test_accessors_cover_api_cycles_and_return_none_before():
    corrected = Corrected(fake_output())
    assert corrected.aipac_cents('B001282', 2026) == 5235943
    assert corrected.pro_israel_cents('B001282', 2026) == 9624746
    assert corrected.transfers_cents('B001282', 2026) == (282810951, 5681782)
    assert corrected.aipac_cents('B001282', 2020) is None
    assert corrected.pro_israel_cents('B001282', 2020) is None
    assert corrected.transfers_cents('B001282', 2020) is None
    # Absent from the merge means the API shows $0 for that cycle.
    assert corrected.aipac_cents('NOBODY', 2026) == 0
    assert corrected.pro_israel_cents('NOBODY', 2026) == 0
    assert corrected.transfers_cents('NOBODY', 2026) == (0, 0)


def test_load_refuses_a_stale_derivation(tmp_path, monkeypatch):
    stale = fake_output()
    stale['snapshot'] = '2026-11-12'
    path = tmp_path / 'derived.json'
    import json

    path.write_text(json.dumps(stale))
    monkeypatch.setattr('receipts.square_one.corrected.derived_path', lambda: path)
    with pytest.raises(SystemExit, match='re-run'):
        load()


def test_kept_id_prefers_the_item_15_record_then_current_chamber():
    records = [{'person_key': 'B001282', 'cycle': 2024, 'kept_id': 'H0KY06104'}]
    offices = {'H0KY06104': 'H', 'S6KY00286': 'S'}
    barr = person('B001282', ['H0KY06104', 'S6KY00286'])
    assert kept_candidate_id(barr, 2024, records, offices) == 'H0KY06104'
    assert kept_candidate_id(barr, 2026, records, offices) == 'S6KY00286'
    assert kept_candidate_id(barr, 2026, [], offices) == 'S6KY00286'
    house_only = person('H001082', ['H8OK01157'], chamber_120='House')
    assert kept_candidate_id(house_only, 2026, [], {'H8OK01157': 'H'}) == 'H8OK01157'
    assert kept_candidate_id(person('X', []), 2026, [], {}) is None


def test_kept_id_follows_the_committee_master_not_the_id_prefix():
    # Roger Marshall: the master lists his House ID under office 'S',
    # so the derivation keeps the House ID for 2018/2020 even though
    # his current chamber is the Senate. The kept choice must follow
    # the master, or the apply diverges from the derivation.
    marshall = person('M001198', ['H6KS01179', 'S0KS00315'], chamber_120='', chamber_119='Senate')
    offices = {'H6KS01179': 'S', 'S0KS00315': 'S'}
    assert kept_candidate_id(marshall, 2018, [], offices) == 'H6KS01179'
    assert kept_candidate_id(marshall, 2020, [], offices) == 'H6KS01179'


def test_distribute_puts_the_total_on_the_kept_id():
    assert distribute(100, 'S1', ['H1', 'S1']) == {'H1': 0, 'S1': 100}


def _counted(entries):
    return {
        (cid, cycle): {c: Money(v.get(c, 0)) for c in COLUMNS}
        for (cid, cycle), v in entries.items()
    }


def test_substitute_aipac_sets_the_kept_entry_and_zeroes_the_other():
    corrected = Corrected(fake_output())
    barr = person('B001282', ['H0KY06104', 'S6KY00286'])
    counted = _counted(
        {
            ('H0KY06104', 2026): {'individual': 100, 'aipac_pac_direct': 500000},
            ('S6KY00286', 2026): {'individual': 200, 'aipac_pac_direct': 0},
            ('H0KY06104', 2024): {'aipac_pac_direct': 500000},
        }
    )
    filed = {('H0KY06104', 2026), ('S6KY00286', 2026), ('H0KY06104', 2024)}
    new_counted, new_filed = substitute_aipac(
        counted, filed, [barr], [], corrected, COLUMNS, {'H0KY06104': 'H', 'S6KY00286': 'S'}
    )
    assert new_counted[('S6KY00286', 2026)]['aipac_pac_direct'] == Money(5235943)
    assert new_counted[('H0KY06104', 2026)]['aipac_pac_direct'] == Money(0)
    assert new_counted[('H0KY06104', 2026)]['individual'] == Money(100)
    # 2024 has no corrected entry for Barr in the fixture, so it corrects to zero.
    assert new_counted[('H0KY06104', 2024)]['aipac_pac_direct'] == Money(0)
    assert new_filed == filed


def test_substitute_aipac_adds_a_missing_cycle_entry():
    corrected = Corrected(fake_output())
    hern = person('H001082', ['H8OK01157', 'S6OK04247'])
    counted = _counted({('H8OK01157', 2024): {'individual': 100}})
    filed = {('H8OK01157', 2024)}
    new_counted, new_filed = substitute_aipac(
        counted, filed, [hern], [], corrected, COLUMNS, {'H8OK01157': 'H', 'S6OK04247': 'S'}
    )
    assert ('S6OK04247', 2026) in new_counted
    assert new_counted[('S6OK04247', 2026)]['aipac_pac_direct'] == Money(1000000)
    assert new_counted[('S6OK04247', 2026)]['individual'] == Money(0)
    assert ('S6OK04247', 2026) in new_filed


def _finances(entries):
    def row(from_cents, to_cents):
        return CampaignFinances(
            total_receipts=Money(0),
            transfers_from_auth=Money(from_cents),
            total_disbursements=Money(0),
            transfers_to_auth=Money(to_cents),
            cash_on_hand=Money(0),
            candidate_contributions=Money(0),
            candidate_loans=Money(0),
            loan_repayments=Money(0),
            debts_owed_by=Money(0),
        )

    return {(cid, cycle): row(f, t) for (cid, cycle), (f, t) in entries.items()}


def test_substitute_transfers_keeps_the_kept_view_only():
    corrected = Corrected(fake_output())
    barr = person('B001282', ['H0KY06104', 'S6KY00286'])
    finances = _finances(
        {
            ('H0KY06104', 2026): (278097393, 336142),
            ('S6KY00286', 2026): (282810951, 5681782),
            ('H0KY06104', 2024): (48586314, 0),
        }
    )
    new = substitute_transfers(
        finances, [barr], [], corrected, {'H0KY06104': 'H', 'S6KY00286': 'S'}
    )
    assert new[('S6KY00286', 2026)].transfers_from_auth == Money(282810951)
    assert new[('S6KY00286', 2026)].transfers_to_auth == Money(5681782)
    assert new[('H0KY06104', 2026)].transfers_from_auth == Money(0)
    assert new[('H0KY06104', 2026)].transfers_to_auth == Money(0)
    assert new[('H0KY06104', 2024)].transfers_from_auth == Money(48586314)


def test_substitute_transfers_fails_loudly_without_a_weball_row():
    corrected = Corrected(fake_output())
    barr = person('B001282', ['H0KY06104', 'S6KY00286'])
    with pytest.raises(SystemExit, match='no weball row'):
        substitute_transfers(_finances({}), [barr], [], corrected, {})


def test_api_cycles_are_2022_2024_2026():
    assert API_CYCLES == (2022, 2024, 2026)

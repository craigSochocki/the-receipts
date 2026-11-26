"""Fresh parsers and roster input for the square-one re-derivation."""

from pathlib import Path

import pytest

from receipts.square_one import parsers, roster

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / 'data' / 'raw'


def test_parse_cents():
    assert parsers.parse_cents('5000') == 500000
    assert parsers.parse_cents('5000.00') == 500000
    assert parsers.parse_cents('-2500.50') == -250050
    assert parsers.parse_cents('0.06') == 6
    assert parsers.parse_cents('.77') == 77
    assert parsers.parse_cents('') == 0
    assert parsers.parse_cents('  12.3 ') == 1230
    with pytest.raises(ValueError):
        parsers.parse_cents('1.234')
    with pytest.raises(ValueError):
        parsers.parse_cents('abc')


def test_pas2_layout_and_known_row():
    rows = list(parsers.pas2_rows(BULK, 2026))
    assert len(rows) == 252533
    bell = [r for r in rows if r.committee_id == 'C00797670' and r.candidate_id == 'H4MO01134']
    assert len(bell) == 4  # 3 tracker-rule rows plus one -$6 voided earmark
    assert sum(r.amount_cents for r in bell) == 1499400
    assert sum(r.amount_cents for r in bell if r.is_earmark) == 499400


def test_pas2_wrong_width_raises(tmp_path):
    bad = tmp_path / 'itpas2.txt'
    bad.write_text('a|b|c\n')
    with pytest.raises(parsers.LayoutChanged):
        list(parsers.PipeFile(bad, parsers.Pas2Row))


def test_weball_layout_and_row_count():
    rows = list(parsers.weball_rows(BULK, 2026))
    assert len(rows) == 4372
    ryan = [r for r in rows if r.candidate_id == 'H8NY19223'][0]
    assert ryan.cents('total_receipts') == 535973343
    assert ryan.cents('individual_contributions') == 398727310


def test_cm_layout_and_aipac_row():
    rows = list(parsers.committee_rows(BULK, 2026))
    aipac = [r for r in rows if r.committee_id == 'C00797670']
    assert len(aipac) == 1
    assert aipac[0].committee_type == 'Q'
    assert aipac[0].organization_type == 'M'


def test_ie_header_and_row_counts():
    rows_2026 = list(parsers.ie_rows(BULK / 'ie', 2026))
    assert len(rows_2026) == 51401
    rows_2024 = list(parsers.ie_rows(BULK / 'ie', 2024))
    assert len(rows_2024) == 73449


def test_ie_missing_column_raises(tmp_path):
    bad = tmp_path / 'independent_expenditure_2026.csv'
    bad.write_text('cand_id,spe_id\nH1, C1\n')
    with pytest.raises(parsers.LayoutChanged):
        list(parsers.ExpenditureFile(bad))


def test_cn_layout():
    rows = list(parsers.candidate_rows(BULK, 2026))
    assert len(rows) > 4000
    ryan = [r for r in rows if r.candidate_id == 'H8NY19223']
    assert ryan and ryan[0].election_year == '2026'


def test_roster_load_is_roster_only():
    people = roster.load_roster(ROOT / 'congress-money-tracker.json')
    assert len(people) == 664
    assert set(people[0]) == set(roster.ROSTER_FIELDS)
    assert 'aipac_pac_direct_career' not in people[0]
    latimer = [p for p in people if p['person_key'] == 'L000606'][0]
    assert latimer['fec_candidate_ids'] == ['H4NY16087']
    assert latimer['senate_class'] is None
    by_id = roster.person_of(people)
    assert by_id['H4NY16087'] == 'L000606'
    assert by_id['H4MO01134'] == 'B001324'


def test_dedup_record_loads():
    records = roster.load_dedup_applied(ROOT / 'data' / 'source' / 'dedup-applied.json')
    assert len(records) == 90
    baldwin = [r for r in records if r['person_key'] == 'B001230'][0]
    assert baldwin['kept_id'] == 'S2WI00219'
    assert baldwin['dropped_ids'] == ['H8WI00018']

"""Shared-committee transfer dedup and election-attributed refunds."""

import json
from pathlib import Path

from receipts.square_one import money, parsers, roster, transfers

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / 'data' / 'raw'


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def test_shared_committee_groups():
    people = roster.load_roster(ROOT / 'congress-money-tracker.json')
    principal = transfers.principal_committees(BULK, [2022, 2024, 2026])
    offices = transfers.candidate_offices(BULK, [2022, 2024, 2026])
    groups = transfers.shared_committee_groups(people, principal, offices)
    by_person = {g['person_key']: g for g in groups}
    barr = by_person['B001282']
    assert barr['committee'] == 'C00467571'
    assert barr['ids'] == ['H0KY06104', 'S6KY00286']
    assert barr['kept_id'] == 'S6KY00286'
    pappas = by_person['P000614']
    assert pappas['committee'] == 'C00660464'
    assert pappas['kept_id'] == 'S6NH00141'
    hageman = by_person['H001096']
    assert hageman['committee'] == 'C00788943'
    # Collins has one candidate ID and one committee: no group, no double-count.
    assert 'C001035' not in by_person


def test_barr_transfer_dedup():
    people = roster.load_roster(ROOT / 'congress-money-tracker.json')
    principal = transfers.principal_committees(BULK, [2022, 2024, 2026])
    offices = transfers.candidate_offices(BULK, [2022, 2024, 2026])
    groups = transfers.shared_committee_groups(people, principal, offices)
    weball = money.derive_weball(BULK, [2026])
    # The double-count reproduces before the fix: both views summed.
    assert (
        weball[('H0KY06104', 2026)]['transfers_from_auth']
        + weball[('S6KY00286', 2026)]['transfers_from_auth']
        == 560908344
    )
    adjusted, report = transfers.apply_transfer_dedup(weball, groups)
    barr_2026 = [r for r in report if r['person_key'] == 'B001282' and r['cycle'] == 2026][0]
    assert barr_2026['kept'] == {'transfers_from_auth': 282810951, 'transfers_to_auth': 5681782}
    assert barr_2026['dropped'] == {'transfers_from_auth': 278097393, 'transfers_to_auth': 336142}
    assert adjusted[('H0KY06104', 2026)]['transfers_from_auth'] == 0
    assert adjusted[('S6KY00286', 2026)]['transfers_from_auth'] == 282810951
    # Pappas and Hageman: identical views, one copy kept.
    pappas_2026 = [r for r in report if r['person_key'] == 'P000614' and r['cycle'] == 2026][0]
    assert pappas_2026['kept']['transfers_from_auth'] == 119607997
    assert pappas_2026['dropped']['transfers_from_auth'] == 119607997
    # Collins has no group: her single weball row stands as filed.
    assert weball[('S6ME00159', 2026)]['transfers_from_auth'] == 537181134


def test_ryan_election_attributed_refunds():
    """The pilot report's +$5,000 is wrong: it missed the G2026 refund.

    All five refunds carry their election in TRANSACTION_PGI, confirmed
    live against Schedule A line 16 (same transaction IDs, same
    election_type). Two of the five refunds are 2026 (P2026 and G2026),
    so election-attributed 2026 net is +$10,000 - $10,000 = $0, and Ryan
    does NOT flip under this method. Only Schedule B-only (+$10,000)
    flips him.
    """
    rows = [
        row
        for row in parsers.pas2_rows(BULK, 2026)
        if row.candidate_id == 'H8NY19223' and row.committee_id == 'C00797670'
    ]
    # Tracker rule first: 24K/24P only, voided earmarks excluded.
    counted = [
        row
        for row in rows
        if row.transaction_type in ('24K', '24P') and not (row.is_earmark and row.amount_cents < 0)
    ]
    assert sum(row.amount_cents for row in counted) == -1500000  # pas2 netting
    assert sum(row.amount_cents for row in counted if row.amount_cents > 0) == 1000000
    attributed = transfers.attribute_refunds_by_election(counted, 2026)
    assert attributed[('H8NY19223', 2026)] == 0
    # The SA16 evidence file agrees with the pas2 PGI on every refund.
    evidence = _load_json(ROOT / 'data' / 'evidence' / 'square-one' / 'ryan_sa16_refunds.json')
    pgi_by_tran = {row.transaction_id: row.election for row in counted if row.amount_cents < 0}
    for refund in evidence['refunds']:
        assert pgi_by_tran[refund['transaction_id']] == refund['election_type']
    assert sorted(pgi_by_tran.values()) == ['G2022', 'G2024', 'G2026', 'P2024', 'P2026']
    # Schedule B-only sees no refunds at all: +$10,000.
    assert sum(row.amount_cents for row in counted if row.amount_cents > 0) == 1000000

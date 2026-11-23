import pytest

from receipts.domain.ledger import Ledger
from receipts.domain.money import ZERO, Money
from receipts.domain.roster import Roster


def test_ledger_adds_and_totals_by_column():
    ledger = Ledger(['labor', 'trade'])
    ledger.add('H1', 2024, 'labor', Money(100))
    ledger.add('H1', 2024, 'labor', Money(50))
    ledger.add('S1', 2026, 'labor', Money(-20))
    ledger.add('S1', 2026, 'trade', Money(7))

    assert ledger.amount('H1', 2024, 'labor') == Money(150)
    assert ledger.amount('H1', 2026, 'labor') == ZERO
    assert ledger.total(['H1', 'S1'], [2024, 2026], 'labor') == Money(130)
    assert ledger.column_total('trade') == Money(7)
    assert ledger.candidates_in(2026) == {'S1'}


def test_ledger_refuses_a_column_it_was_not_given():
    ledger = Ledger(['labor'])
    with pytest.raises(KeyError):
        ledger.add('H1', 2024, 'lab0r', Money(1))
    with pytest.raises(KeyError):
        ledger.amount('H1', 2024, 'trade')


def test_roster_knows_its_candidates_and_shared_ids():
    alice = {'person_key': 'A', 'fec_candidate_ids': ['H1', 'S1']}
    alice_again = {'person_key': 'A2', 'fec_candidate_ids': ['S1']}
    bob = {'person_key': 'B', 'fec_candidate_ids': None}
    roster = Roster([alice, alice_again, bob])

    assert 'H1' in roster and 'X9' not in roster
    assert roster.others_sharing_an_id_with(alice) == ['A2']
    assert roster.others_sharing_an_id_with(bob) == []

"""weball: one summary row per candidate per cycle."""
from typing import NamedTuple

from src.domain.money import Money
from src.fec.bulk_file import BulkFile


class CandidateSummary(NamedTuple):
    candidate_id: str
    name: str
    incumbent_challenger: str
    party_code: str
    party: str
    total_receipts: str
    transfers_from_authorized: str
    total_disbursements: str
    transfers_to_authorized: str
    cash_start: str
    cash_end: str
    candidate_contributions: str
    candidate_loans: str
    other_loans: str
    candidate_loan_repayments: str
    other_loan_repayments: str
    debts_owed_by: str
    individual_contributions_text: str
    office_state: str
    office_district: str
    special_election: str
    primary_election: str
    runoff_election: str
    general_election: str
    general_election_percent: str
    other_committee_contributions_text: str
    party_contributions: str
    coverage_end: str
    individual_refunds: str
    committee_refunds: str

    @property
    def individual_contributions(self):
        return Money.parse(self.individual_contributions_text)

    @property
    def other_committee_contributions(self):
        return Money.parse(self.other_committee_contributions_text)


def candidate_summaries(bulk_dir, cycle):
    return BulkFile(bulk_dir / 'weball' / f'weball{cycle % 100:02d}.txt', CandidateSummary)

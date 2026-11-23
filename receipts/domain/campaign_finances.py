"""A candidate's own money and campaign topline for one cycle."""

from dataclasses import dataclass, fields

from receipts.domain.money import Money

FLOWS = [
    'candidate_contributions',
    'candidate_loans',
    'loan_repayments',
    'total_receipts',
    'total_disbursements',
    'transfers_from_auth',
    'transfers_to_auth',
]
STOCKS = ['cash_on_hand', 'debts_owed_by']


@dataclass(frozen=True)
class CampaignFinances:
    total_receipts: Money
    transfers_from_auth: Money
    total_disbursements: Money
    transfers_to_auth: Money
    cash_on_hand: Money
    candidate_contributions: Money
    candidate_loans: Money
    loan_repayments: Money
    debts_owed_by: Money

    @classmethod
    def from_weball(cls, amounts):
        return cls(
            total_receipts=amounts['total_receipts'],
            transfers_from_auth=amounts['transfers_from_authorized'],
            total_disbursements=amounts['total_disbursements'],
            transfers_to_auth=amounts['transfers_to_authorized'],
            cash_on_hand=amounts['cash_end'],
            candidate_contributions=amounts['candidate_contributions'],
            candidate_loans=amounts['candidate_loans'],
            loan_repayments=amounts['candidate_loan_repayments'] + amounts['other_loan_repayments'],
            debts_owed_by=amounts['debts_owed_by'],
        )

    @property
    def self_funding(self):
        return self.candidate_contributions + self.candidate_loans

    def __bool__(self):
        return any(getattr(self, field.name) for field in fields(self))

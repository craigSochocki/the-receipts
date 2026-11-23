"""pas2: itemized contributions from committees to candidates."""

from typing import NamedTuple

from receipts.domain.money import Money
from receipts.fec.bulk_file import BulkFile

CONTRIBUTION_TO_CANDIDATE = ('24K', '24P')


class CommitteeContribution(NamedTuple):
    committee_id: str
    amendment: str
    report_type: str
    election: str
    image_number: str
    transaction_type: str
    entity_type: str
    recipient_name: str
    city: str
    state: str
    zip_code: str
    employer: str
    occupation: str
    date: str
    amount_text: str
    other_id: str
    candidate_id: str
    transaction_id: str
    file_number_text: str
    memo_code: str
    memo_text: str
    submission_id: str

    @property
    def is_to_candidate(self):
        return self.transaction_type in CONTRIBUTION_TO_CANDIDATE

    @property
    def amount(self):
        return Money.parse(self.amount_text)

    @property
    def is_earmark(self):
        """An individual donor's money passed through by the committee."""
        return 'EARMARK' in self.memo_text or self.memo_text.startswith('ERMK:')

    @property
    def is_memo(self):
        return self.memo_code == 'X'

    @property
    def file_number(self):
        try:
            return int(self.file_number_text or 0)
        except ValueError:
            return 0

    @property
    def identity(self):
        """Rows sharing this are the same contribution reported more than once.

        The transaction ID alone is not enough: some filers reuse it
        across distinct contributions.
        """
        return (
            self.committee_id,
            self.transaction_id or self.submission_id,
            self.candidate_id,
            self.amount,
            self.date,
            self.election,
        )


def committee_contributions(bulk_dir, cycle):
    return BulkFile(bulk_dir / 'pas2' / str(cycle) / 'itpas2.txt', CommitteeContribution)

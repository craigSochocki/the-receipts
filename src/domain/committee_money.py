"""Which committee contributions the tracker counts, and how.

Rules and evidence: methodology.md §4.
"""
from src.domain.committee_classes import CommitteeClass
from src.domain.money import ZERO

TRACKED_CLASSES = (CommitteeClass.AIPAC, CommitteeClass.CORPORATE)


def tracked_class(contribution, aipac_committee_id, corporate_pacs):
    """AIPAC or corporate, the two committee classes total_accepted counts; else None."""
    if contribution.committee_id == aipac_committee_id:
        return CommitteeClass.AIPAC
    if contribution.committee_id in corporate_pacs:
        return CommitteeClass.CORPORATE
    return None


def is_voided_earmark(contribution):
    """A refunded conduit earmark. The original transmission is not in
    pas2, so netting the refund would create a phantom negative."""
    return contribution.is_earmark and contribution.amount.is_negative


class Tally:
    def __init__(self):
        self.rows = 0
        self.amount = ZERO

    def add(self, amount):
        self.rows += 1
        self.amount += amount


class ReportedOnce:
    """One row per contribution, however many times it was reported.

    Keeps the non-memo row, then the earliest filing.
    """

    def __init__(self):
        self._kept = {}
        self.dropped = Tally()

    def add(self, contribution):
        kept = self._kept.get(contribution.identity)
        if kept is None or self._preference(contribution) < self._preference(kept):
            self._kept[contribution.identity] = contribution
        if kept is not None:
            self.dropped.add(contribution.amount)

    def __iter__(self):
        return iter(self._kept.values())

    @staticmethod
    def _preference(contribution):
        return (contribution.is_memo, contribution.file_number)

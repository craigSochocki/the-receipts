"""Which committee contributions the tracker counts (methodology.md §4)."""

from receipts.domain.money import ZERO
from receipts.domain.one_copy import OneCopyEach


def is_voided_earmark(contribution):
    """A refunded earmark whose original is not in pas2; netting it makes a phantom negative."""
    return contribution.is_earmark and contribution.amount.is_negative


def reported_once():
    """One row per contribution: the non-memo row, then the earliest filing."""

    def rank(contribution):
        return (contribution.is_memo, contribution.file_number)

    return OneCopyEach(lambda new, kept: rank(new) < rank(kept))


class Tally:
    def __init__(self):
        self.rows = 0
        self.amount = ZERO

    def add(self, amount):
        self.rows += 1
        self.amount += amount

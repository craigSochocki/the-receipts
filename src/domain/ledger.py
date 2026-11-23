"""Money per candidate ID, cycle and column."""
from collections import defaultdict

from src.domain.money import ZERO, Money


class Ledger:
    def __init__(self, columns):
        self.columns = tuple(columns)
        self._amounts = defaultdict(lambda: ZERO)

    def add(self, candidate_id, cycle, column, amount):
        self._require(column)
        self._amounts[candidate_id, cycle, column] += amount

    def amount(self, candidate_id, cycle, column):
        self._require(column)
        return self._amounts.get((candidate_id, cycle, column), ZERO)

    def total(self, candidate_ids, cycles, column):
        return Money.total(self.amount(candidate_id, cycle, column)
                           for candidate_id in candidate_ids for cycle in cycles)

    def column_total(self, column):
        self._require(column)
        return Money.total(amount for (_, _, recorded), amount in self._amounts.items()
                           if recorded == column)

    def candidates_in(self, cycle):
        return {candidate_id for candidate_id, recorded, _ in self._amounts if recorded == cycle}

    def _require(self, column):
        if column not in self.columns:
            raise KeyError(f'{column!r} is not a ledger column; expected one of {self.columns}')

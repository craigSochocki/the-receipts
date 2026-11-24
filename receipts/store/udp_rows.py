"""UDP's independent expenditures from the store, with blank candidate IDs resolved.

Shared by the UDP support pull and the opposition credit. UDP files many
rows with a blank candidate ID; the name index is built from its own rows
that carry one, across all cycles, a later row winning a name collision.
"""

from typing import NamedTuple

from receipts.common.settings import settings
from receipts.domain.blank_candidates import name_key, resolve
from receipts.store.read import connect

ROWS = (
    'SELECT candidate_id, candidate_name, cycle, direction, amount_cents, office, '
    'office_state, office_district, election_type, transaction_id '
    'FROM outside_spending WHERE spender_id = ? '
    "AND excluded_because IS DISTINCT FROM 'reported_again' ORDER BY cycle, file_order"
)


class UdpRow(NamedTuple):
    candidate_id: str
    candidate_name: str
    cycle: int
    direction: str
    cents: int
    office: str
    state: str
    district: str
    election_type: str
    transaction_id: str
    resolved_via: str = None


class UdpRows:
    """UDP's rows as filed, with each blank candidate ID resolved where the name allows."""

    def __init__(self, filed, people):
        self.index, self.collisions = self._name_index(filed)
        self.rows, self.unresolved = [], []
        for row in filed:
            if row.candidate_id:
                self.rows.append(row)
                continue
            candidate_id, via = resolve(row, self.index, people)
            self.rows.append(row._replace(candidate_id=candidate_id or '', resolved_via=via))
            if candidate_id is None:
                self.unresolved.append(row)

    @classmethod
    def from_store(cls, people):
        with connect() as db:
            filed = db.execute(ROWS, [settings().committees.udp]).fetchall()
        return cls([UdpRow(*row) for row in filed], people)

    @staticmethod
    def _name_index(rows):
        index, collisions = {}, []
        for row in rows:
            if row.candidate_id:
                key = name_key(row.candidate_name, row.state, row.district, row.office)
                if key in index and index[key] != row.candidate_id:
                    collisions.append((key, index[key], row.candidate_id))
                index[key] = row.candidate_id
        return index, collisions

    def cycle_total(self, cycle):
        return sum(row.cents for row in self.rows if row.cycle == cycle)

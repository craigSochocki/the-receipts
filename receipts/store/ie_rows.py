"""Independent-expenditure rows as the store holds them, and the arithmetic on them."""

from typing import NamedTuple

REPLACED = 'reported_again'


UNREGISTERED, BLANK, NOT_IDENTIFIED = (
    'unregistered_committee',
    'blank_candidate',
    'candidate_not_identified',
)


class Expenditure(NamedTuple):
    spender_id: str
    spender_name: str
    candidate_id: str
    candidate_name: str
    cycle: int
    direction: str
    cents: int
    office: str
    state: str
    district: str
    date: str
    transaction_id: str
    excluded_because: str

    @property
    def counted(self):
        return self.excluded_because is None


def dollars(cents):
    return cents / 100


def total(rows):
    return sum(x.cents for x in rows)


def tally(rows):
    rows = list(rows)
    return {'rows': len(rows), 'amount': dollars(total(rows))}


def by_direction(rows):
    rows = list(rows)
    return (
        dollars(total(x for x in rows if x.direction == 'S')),
        dollars(total(x for x in rows if x.direction == 'O')),
        dollars(total(rows)),
    )


class Roster:
    def __init__(self, people):
        self.people = people
        self.person_of = {}
        for p in people:
            for candidate_id in p.get('fec_candidate_ids') or []:
                self.person_of.setdefault(candidate_id, p['person_key'])

    @staticmethod
    def ids(person):
        return list(dict.fromkeys(person.get('fec_candidate_ids') or []))

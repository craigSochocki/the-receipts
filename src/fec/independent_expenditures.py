"""Independent expenditures: spending for or against a candidate by an outside group."""
import csv
from datetime import datetime
from typing import NamedTuple

from src.domain.money import Money

SUPPORT, OPPOSE = 'S', 'O'


class IndependentExpenditure(NamedTuple):
    cand_id: str
    cand_name: str
    spe_id: str
    spe_nam: str
    ele_type: str
    can_office_state: str
    can_office_dis: str
    can_office: str
    cand_pty_aff: str
    exp_amo: str
    exp_date: str
    agg_amo: str
    sup_opp: str
    pur: str
    pay: str
    file_num: str
    amndt_ind: str
    tran_id: str
    image_num: str
    receipt_dat: str
    fec_election_yr: str
    prev_file_num: str
    dissem_dt: str
    position: int

    @property
    def spender_id(self):
        return self.spe_id

    @property
    def candidate_id(self):
        return self.cand_id.strip()

    @property
    def cycle(self):
        return int(self.fec_election_yr)

    @property
    def direction(self):
        return self.sup_opp.strip()

    @property
    def amount(self):
        return Money.parse(self.exp_amo)

    @property
    def received(self):
        try:
            return datetime.strptime(self.receipt_dat.strip(), '%d-%b-%y')
        except ValueError:
            return datetime.min

    @property
    def file_number(self):
        try:
            return int(self.file_num.strip())
        except ValueError:
            return 0

    @property
    def identity(self):
        """Rows sharing this are one expenditure, filed and amended.

        A blank transaction ID is never matched to another row.
        """
        transaction = self.tran_id.strip()
        return (self.spe_id, transaction or f'blank:{self.position}')


class ExpenditureFile:
    def __init__(self, path):
        self.path = path
        self.rows_read = 0

    def __iter__(self):
        with open(self.path, newline='') as f:
            for position, row in enumerate(csv.DictReader(f)):
                self.rows_read += 1
                fields = {name: (row.get(name) or '') for name in IndependentExpenditure._fields[:-1]}
                yield IndependentExpenditure(**fields, position=position)


def independent_expenditures(ie_dir, cycle):
    return ExpenditureFile(ie_dir / str(cycle) / f'independent_expenditure_{cycle}.csv')

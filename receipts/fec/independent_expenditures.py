"""Independent expenditures: spending for or against a candidate by an outside group."""

import csv
from datetime import datetime
from typing import NamedTuple

from receipts.domain.money import Money
from receipts.fec.bulk_file import LayoutChanged

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
        """Rows sharing this are one expenditure, filed and amended; a blank ID never matches."""
        transaction = self.tran_id.strip()
        return (self.spe_id, transaction or f'blank:{self.position}')


COLUMNS = IndependentExpenditure._fields[:-1]


class ExpenditureFile:
    def __init__(self, path):
        self.path = path
        self.rows_read = 0
        self.columns = None

    def __iter__(self):
        with open(self.path, newline='') as f:
            reader = csv.DictReader(f)
            self.columns = reader.fieldnames
            self._check_header()
            for position, row in enumerate(reader):
                self.rows_read += 1
                if None in row or None in row.values():
                    raise LayoutChanged(
                        f'{self.path} line {position + 2} does not have one value per column '
                        f'of its header: the FEC file layout changed'
                    )
                yield IndependentExpenditure(**{c: row[c] for c in COLUMNS}, position=position)

    def _check_header(self):
        missing = [c for c in COLUMNS if c not in (self.columns or [])]
        if missing:
            raise LayoutChanged(
                f'{self.path} has no {", ".join(missing)} column: the FEC file layout changed'
            )


def independent_expenditures(ie_dir, cycle):
    return ExpenditureFile(ie_dir / str(cycle) / f'independent_expenditure_{cycle}.csv')

"""Independent-expenditure CSV reader, written for the square-one re-derivation.

Split out of parsers.py: the IE file is a CSV with a header, not a pipe file,
and its row type belongs with the IE derivation, not the bulk pipe readers.
"""

import csv
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from receipts.square_one.parsers import LayoutChanged, parse_cents

IE_COLUMNS = (
    'cand_id',
    'cand_name',
    'spe_id',
    'spe_nam',
    'ele_type',
    'can_office_state',
    'can_office_dis',
    'can_office',
    'cand_pty_aff',
    'exp_amo',
    'exp_date',
    'agg_amo',
    'sup_opp',
    'pur',
    'pay',
    'file_num',
    'amndt_ind',
    'tran_id',
    'image_num',
    'receipt_dat',
    'fec_election_yr',
    'prev_file_num',
    'dissem_dt',
)


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
    def candidate_id(self) -> str:
        return self.cand_id.strip()

    @property
    def cycle(self) -> int:
        return int(self.fec_election_yr)

    @property
    def direction(self) -> str:
        return self.sup_opp.strip()

    @property
    def amount_cents(self) -> int:
        return parse_cents(self.exp_amo)

    @property
    def received(self) -> datetime:
        try:
            return datetime.strptime(self.receipt_dat.strip(), '%d-%b-%y')
        except ValueError:
            return datetime.min

    @property
    def file_number(self) -> int:
        try:
            return int(self.file_num.strip())
        except ValueError:
            return 0

    @property
    def identity(self) -> tuple:
        """Rows sharing this are one expenditure, filed and amended; a blank ID never matches."""
        transaction = self.tran_id.strip()
        return (self.spe_id, transaction or f'blank:{self.position}')


class ExpenditureFile:
    """Rows of a staged independent-expenditure CSV, checked against its header."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.rows_read = 0
        self.columns: list[str] | None = None

    def __iter__(self) -> Iterator[IndependentExpenditure]:
        with open(self.path, newline='', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            self.columns = list(reader.fieldnames or [])
            missing = [c for c in IE_COLUMNS if c not in (self.columns or [])]
            if missing:
                raise LayoutChanged(
                    f'{self.path} has no {", ".join(missing)} column: the FEC file layout changed'
                )
            for position, row in enumerate(reader):
                self.rows_read += 1
                if None in row or None in row.values():
                    raise LayoutChanged(
                        f'{self.path} line {position + 2} does not have one value per column '
                        'of its header: the FEC file layout changed'
                    )
                yield IndependentExpenditure(**{c: row[c] for c in IE_COLUMNS}, position=position)


def ie_rows(ie_dir: Path, cycle: int) -> ExpenditureFile:
    return ExpenditureFile(ie_dir / str(cycle) / f'independent_expenditure_{cycle}.csv')

"""Fresh parsers for the FEC bulk files, written for the square-one re-derivation.

These readers are independent of receipts/fec/: they were written from the
file layouts as filed, they carry money as exact integer cents, and they
raise LayoutChanged on any row that does not match the expected width.
The existing readers are used only as a cross-check, never by this code.
"""

import csv
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Generic, NamedTuple, TypeVar

Record = TypeVar('Record', bound=NamedTuple)


class LayoutChanged(Exception):
    """An FEC file no longer has the columns this reader expects."""


def parse_cents(text: str) -> int:
    """Exact integer cents for a filed dollar amount; blank reads as zero."""
    raw = text.strip()
    if raw in ('', '-'):
        return 0
    negative = raw.startswith('-')
    if negative:
        raw = raw[1:]
    if '.' in raw:
        dollars, cents = raw.split('.', 1)
        if len(cents) > 2:
            raise ValueError(f'amount {text!r} has more than two decimals')
        cents = (cents + '00')[:2]
    else:
        dollars, cents = raw, '00'
    if not dollars.isdigit() or not cents.isdigit():
        raise ValueError(f'amount {text!r} is not a number')
    total = int(dollars) * 100 + int(cents)
    return -total if negative else total


class PipeFile(Generic[Record]):
    """Rows of a pipe-delimited FEC bulk file, as named records."""

    def __init__(self, path: Path, record: type[Record]) -> None:
        self.path = path
        self.record = record
        self.rows_read = 0

    def __iter__(self) -> Iterator[Record]:
        width = len(self.record._fields)
        with open(self.path, encoding='utf-8', errors='replace') as lines:
            for self.rows_read, line in enumerate(lines, start=1):
                fields = line.rstrip('\n').split('|')
                if len(fields) != width:
                    raise LayoutChanged(
                        f'{self.path} line {self.rows_read} has {len(fields)} fields where '
                        f'{self.record.__name__} expects {width}: the FEC file layout changed'
                    )
                yield self.record._make(fields)


class Pas2Row(NamedTuple):
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
    def amount_cents(self) -> int:
        return parse_cents(self.amount_text)

    @property
    def is_earmark(self) -> bool:
        return 'EARMARK' in self.memo_text or self.memo_text.startswith('ERMK:')

    @property
    def is_memo(self) -> bool:
        return self.memo_code == 'X'

    @property
    def file_number(self) -> int:
        try:
            return int(self.file_number_text or 0)
        except ValueError:
            return 0

    @property
    def identity(self) -> tuple:
        """Rows sharing this are one contribution; some filers reuse transaction IDs."""
        return (
            self.committee_id,
            self.transaction_id or self.submission_id,
            self.candidate_id,
            self.amount_cents,
            self.date,
            self.election,
        )


def pas2_rows(bulk_dir: Path, cycle: int) -> PipeFile:
    return PipeFile(bulk_dir / 'pas2' / str(cycle) / 'itpas2.txt', Pas2Row)


class WeballRow(NamedTuple):
    candidate_id: str
    name: str
    incumbent_challenger: str
    party_code: str
    party: str
    total_receipts: str
    transfers_from_authorized: str
    total_disbursements: str
    transfers_to_authorized: str
    cash_start: str
    cash_end: str
    candidate_contributions: str
    candidate_loans: str
    other_loans: str
    candidate_loan_repayments: str
    other_loan_repayments: str
    debts_owed_by: str
    individual_contributions: str
    office_state: str
    office_district: str
    special_election: str
    primary_election: str
    runoff_election: str
    general_election: str
    general_election_percent: str
    other_committee_contributions: str
    party_contributions: str
    coverage_end: str
    individual_refunds: str
    committee_refunds: str

    def cents(self, field: str) -> int:
        return parse_cents(getattr(self, field))


def weball_rows(bulk_dir: Path, cycle: int) -> PipeFile:
    return PipeFile(bulk_dir / 'weball' / f'weball{cycle % 100:02d}.txt', WeballRow)


class CommitteeRow(NamedTuple):
    committee_id: str
    name: str
    treasurer: str
    street_1: str
    street_2: str
    city: str
    state: str
    zip_code: str
    designation: str
    committee_type: str
    party: str
    filing_frequency: str
    organization_type: str
    connected_organization: str
    candidate_id: str


def committee_rows(bulk_dir: Path, cycle: int) -> PipeFile:
    return PipeFile(bulk_dir / 'cm' / str(cycle) / 'cm.txt', CommitteeRow)


class CandidateRow(NamedTuple):
    candidate_id: str
    name: str
    party: str
    election_year: str
    office_state: str
    office: str
    office_district: str
    incumbent_challenger: str
    status: str
    principal_committee: str
    street_1: str
    street_2: str
    city: str
    state: str
    zip_code: str


def candidate_rows(bulk_dir: Path, cycle: int) -> PipeFile:
    return PipeFile(bulk_dir / 'cn' / str(cycle) / 'cn.txt', CandidateRow)


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

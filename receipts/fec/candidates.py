"""cn: the candidate master file, one row per registered candidate per cycle."""
from typing import NamedTuple

from receipts.fec.bulk_file import BulkFile


class Candidate(NamedTuple):
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


def candidates(bulk_dir, cycle):
    return BulkFile(bulk_dir / 'cn' / str(cycle) / 'cn.txt', Candidate)

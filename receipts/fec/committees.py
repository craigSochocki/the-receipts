"""cm: the committee master file, one row per registered committee per cycle."""
from typing import NamedTuple

from receipts.fec.bulk_file import BulkFile

PAC_TYPES = ('Q', 'N')
CORPORATE_ORGANIZATIONS = ('C', 'W')


class Committee(NamedTuple):
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

    @property
    def is_pac(self):
        return self.committee_type in PAC_TYPES

    @property
    def is_corporate_pac(self):
        return self.is_pac and self.organization_type in CORPORATE_ORGANIZATIONS


def committees(bulk_dir, cycle):
    return BulkFile(bulk_dir / 'cm' / str(cycle) / 'cm.txt', Committee)

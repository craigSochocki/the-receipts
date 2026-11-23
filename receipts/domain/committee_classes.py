"""Which kind of committee a contribution came from (methodology §4).

First match wins. AIPAC and corporate PACs are counted in their own
columns; every other committee lands in exactly one class.
"""

from enum import Enum

PARTY_TYPES = ('X', 'Y')
LEADERSHIP_PAC = 'D'
JOINT_FUNDRAISER = 'J'
CANDIDATE_TYPES = ('H', 'S', 'P')
HYBRID_TYPES = ('V', 'W')
SUPER_PAC = 'O'


class CommitteeClass(Enum):
    AIPAC = 'aipac'
    CORPORATE = 'corporate'
    PARTY = 'party_committees'
    LEADERSHIP = 'leadership_pacs'
    LABOR = 'labor_pacs'
    TRADE = 'trade_pacs'
    MEMBERSHIP = 'membership_pacs'
    COOPERATIVE = 'cooperative_pacs'
    UNCLASSIFIED = 'other_unclassified'


OTHER_COMMITTEE_CLASSES = [
    c for c in CommitteeClass if c not in (CommitteeClass.AIPAC, CommitteeClass.CORPORATE)
]

PAC_CLASS_BY_SPONSOR = {
    'L': CommitteeClass.LABOR,
    'T': CommitteeClass.TRADE,
    'M': CommitteeClass.MEMBERSHIP,
    'V': CommitteeClass.COOPERATIVE,
}


def committee_class(committee, aipac_committee_id):
    if committee.committee_id == aipac_committee_id:
        return CommitteeClass.AIPAC
    if committee.is_corporate_pac:
        return CommitteeClass.CORPORATE
    if committee.committee_type in PARTY_TYPES:
        return CommitteeClass.PARTY
    if committee.designation == LEADERSHIP_PAC:
        return CommitteeClass.LEADERSHIP
    if committee.is_pac:
        return PAC_CLASS_BY_SPONSOR.get(committee.organization_type, CommitteeClass.UNCLASSIFIED)
    return CommitteeClass.UNCLASSIFIED


def unclassified_kind(committee, winred_committee_id):
    """What an unclassified committee is, for the diagnostics."""
    if committee.committee_id == winred_committee_id:
        return 'winred_conduit'
    if committee.committee_type in CANDIDATE_TYPES:
        return 'candidate_committees'
    if committee.designation == JOINT_FUNDRAISER:
        return 'joint_fundraisers'
    if committee.committee_type in HYBRID_TYPES:
        return 'hybrid_pacs'
    if committee.committee_type == SUPER_PAC:
        return 'super_pacs'
    if committee.is_pac:
        return 'qn_blank_org'
    return 'other_types'

from receipts.domain.committee_classes import CommitteeClass, committee_class, unclassified_kind
from receipts.fec.committees import Committee

AIPAC = 'C00797670'
WINRED = 'C00694323'


def committee(**fields):
    return Committee(**{**dict.fromkeys(Committee._fields, ''), 'committee_id': 'C1', **fields})


def classify(**fields):
    return committee_class(committee(**fields), AIPAC)


def test_aipac_and_corporate_pacs_come_first():
    assert (
        classify(committee_id=AIPAC, committee_type='Q', organization_type='M')
        is CommitteeClass.AIPAC
    )
    assert (
        classify(committee_type='Q', organization_type='C', designation='D')
        is CommitteeClass.CORPORATE
    )


def test_party_committees_are_the_party_types():
    assert classify(committee_type='Y') is CommitteeClass.PARTY
    assert classify(committee_type='X', designation='D') is CommitteeClass.PARTY


def test_leadership_pacs_are_identified_by_designation():
    assert classify(committee_type='Q', designation='D') is CommitteeClass.LEADERSHIP
    assert (
        classify(committee_type='Q', organization_type='L', designation='D')
        is CommitteeClass.LEADERSHIP
    )


def test_other_pacs_are_classed_by_sponsor():
    assert classify(committee_type='Q', organization_type='L') is CommitteeClass.LABOR
    assert classify(committee_type='N', organization_type='T') is CommitteeClass.TRADE
    assert classify(committee_type='Q', organization_type='M') is CommitteeClass.MEMBERSHIP
    assert classify(committee_type='Q', organization_type='V') is CommitteeClass.COOPERATIVE
    assert classify(committee_type='Q', organization_type='') is CommitteeClass.UNCLASSIFIED


def test_non_pac_committees_are_unclassified():
    assert classify(committee_type='H') is CommitteeClass.UNCLASSIFIED
    assert classify(committee_type='V', organization_type='L') is CommitteeClass.UNCLASSIFIED


def test_unclassified_committees_are_described_for_diagnostics():
    def kind(**fields):
        return unclassified_kind(committee(**fields), WINRED)

    assert kind(committee_id=WINRED, committee_type='V') == 'winred_conduit'
    assert kind(committee_type='S') == 'candidate_committees'
    assert kind(committee_type='Q', designation='J') == 'joint_fundraisers'
    assert kind(committee_type='W') == 'hybrid_pacs'
    assert kind(committee_type='O') == 'super_pacs'
    assert kind(committee_type='N') == 'qn_blank_org'
    assert kind(committee_type='Z') == 'other_types'


def test_a_reviewed_override_beats_the_fec_organization_code():
    union = committee(committee_type='Q', organization_type='C')
    assert committee_class(union, AIPAC, {'C1': 'labor_pacs'}) is CommitteeClass.LABOR
    assert committee_class(union, AIPAC, {'C2': 'labor_pacs'}) is CommitteeClass.CORPORATE

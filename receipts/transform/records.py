"""The shape of a person record at the assemble -> compute_2026 boundary.

The record is a plain dict at runtime — the dataset write and the JSON
round-trip need dicts — so these are TypedDicts, not dataclasses. The
per-cycle lists are the typed part: each entry builder in assemble.py
returns one of these, and compute_2026.py reads them through the
PersonRecord. The career money and rank columns are dataset columns,
not part of this boundary contract, so they are deliberately not here;
the current-cycle (``_2026``) columns are config-derived and stay
dynamic, read through plain dicts where the cycle year is a variable.
"""

from collections.abc import Iterable
from typing import TypedDict, cast


class AcceptedCycleEntry(TypedDict):
    cycle: int
    candidate_id: str
    individual: float | None
    aipac_pac_direct: float | None
    aipac_earmark_transmitted: float | None
    corporate_pac: float | None
    corporate_earmark_transmitted: float | None


class UdpCycleEntry(TypedDict):
    cycle: int
    candidate_id: str
    udp_ie_support: float | None


class UdpCycleEntryWithAttribution(UdpCycleEntry, total=False):
    attribution: str


class SelfFundingCycleEntry(TypedDict):
    cycle: int
    candidate_id: str
    candidate_contributions: float | None
    candidate_loans: float | None
    loan_repayments: float | None
    debts_owed_by: float | None
    debts_owed_to: None
    total_receipts: float | None
    total_disbursements: float | None
    cash_on_hand: float | None
    transfers_from_auth: float | None
    transfers_to_auth: float | None
    coverage_end_date: str | None


class OtherCommitteeCycleEntry(TypedDict):
    cycle: int
    candidate_id: str
    party_committees: float | None
    leadership_pacs: float | None
    labor_pacs: float | None
    trade_pacs: float | None
    membership_pacs: float | None
    cooperative_pacs: float | None
    other_unclassified: float | None
    earmark_transmitted: dict[str, float]
    winred_included: float | None


class AllIeCycleEntry(TypedDict):
    cycle: int
    candidate_id: str
    all_ie_support: float | None
    all_ie_oppose: float | None
    all_ie_total: float | None
    no_direction_amount: float | None


class ProIsraelCycleEntry(TypedDict):
    cycle: int
    pro_israel_pac: float | None
    pro_israel_ie_support: float | None
    pro_israel_opp_credit: float | None


class TopCommitteeEntry(TypedDict):
    committee_id: str
    committee_name: str
    support: float | None
    oppose: float | None
    total: float | None
    rows: int


class CycleRecord(TypedDict):
    """One cycle's money and verdict, as compute_2026.cycle_record builds it."""

    cycle: int
    individual: int | float
    corp: int | float
    aipac_direct: int | float
    udp_support: int | float
    udp_opp_credit: int | float
    udp_benefit: int | float
    dirty: int | float
    clean: bool | None
    unopposed: bool
    aipac_udp_flag: bool
    tier_balanced: str | None
    tier_lenient: str | None
    dep_share: float | None
    self_funding: int | float
    cand_loans: int | float
    cand_contrib: int | float
    total_receipts: int | float
    total_disbursements: int | float
    cash_on_hand: float | None
    other_committees_total: int | float
    all_ie_support: int | float
    all_ie_oppose: int | float
    all_ie_total: int | float
    up_for_election: bool


class PersonRecord(TypedDict, total=False):
    """A person at the assemble -> compute_2026 boundary.

    All keys are optional: a base record has no ``cycles`` or headline
    verdict yet, and the current-cycle columns arrive later under
    config-derived names.
    """

    person_key: str
    full_name: str
    chamber_119: str
    chamber_120: str
    state: str
    district_119: str
    district_120: str
    party_119: str
    party_120: str
    leadership_119: str
    leadership_120: str
    in_119th: str
    in_120th: str
    fec_candidate_ids: list[str] | None
    senate_class: int | None
    per_cycle: list[AcceptedCycleEntry]
    udp_per_cycle: list[UdpCycleEntryWithAttribution]
    self_funding_per_cycle: list[SelfFundingCycleEntry]
    other_committees_per_cycle: list[OtherCommitteeCycleEntry]
    all_ie_per_cycle: list[AllIeCycleEntry]
    pro_israel_per_cycle: list[ProIsraelCycleEntry]
    all_ie_top_committees: list[TopCommitteeEntry] | None
    data_notes: str
    data_as_of: str
    cycles: list[CycleRecord]
    verdict_cycle: int | None
    clean: bool | None
    dirty: float
    tier_balanced: str | None
    tier_lenient: str | None


def select_keys(record: PersonRecord, keys: Iterable[str]) -> PersonRecord:
    """Keep only `keys` of a record; the keys come from config, so the filter is dynamic."""
    kept = dict(record)
    return cast(PersonRecord, {k: kept[k] for k in keys})

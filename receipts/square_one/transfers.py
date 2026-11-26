"""Transfers between a person's own committees, and election-attributed refunds.

Two corrections to person-level rollups, both from the transfers/Ryan pilot:

1. Shared-committee transfer dedup. When two candidate IDs share one
   principal committee (Barr: one committee redesignated House -> Senate),
   their weball rows are two views of one committee, not two committees.
   Summing them double-counts transfers. The kept view is the ID whose
   office matches the person's current chamber (the §8 item 15 kept-choice
   precedent); the dropped view's transfer fields are zeroed. This is
   scoped to transfers: Barr's other weball fields are summed the same way
   today, and that wider double-count is flagged separately.
2. Election-attributed refunds. Pas2 nets Schedule A line-16 refunds
   against the filing cycle, but a refund belongs to the election it
   refunds: the pas2 TRANSACTION_PGI names it (P2026, G2024, ...), and the
   live Schedule A rows confirm the PGI matches the filing's election_type
   exactly. Attributing Ryan's five refunds by election year gives a 2026
   net of zero — not the positive net the pilot report computed, which
   subtracted only the primary refund and missed the general-election
   refund even though it is in the report's own election list. Ryan does
   NOT flip under the corrected election-attributed method; only Schedule
   B-only flips him. That correction is the point of this module.
"""

from pathlib import Path

from receipts.square_one import parsers

TRANSFER_FIELDS = ('transfers_from_auth', 'transfers_to_auth')


def principal_committees(bulk_dir: Path, cycles: list[int]) -> dict[str, str]:
    """candidate ID -> principal committee, from the candidate master."""
    principal = {}
    for cycle in cycles:
        for row in parsers.candidate_rows(bulk_dir, cycle):
            principal.setdefault(row.candidate_id, row.principal_committee)
    return principal


def candidate_offices(bulk_dir: Path, cycles: list[int]) -> dict[str, str]:
    """candidate ID -> office (H/S/P) in its latest cycle."""
    offices = {}
    for cycle in sorted(cycles):
        for row in parsers.candidate_rows(bulk_dir, cycle):
            offices[row.candidate_id] = row.office
    return offices


def shared_committee_groups(
    people: list[dict], principal: dict[str, str], offices: dict[str, str]
) -> list[dict]:
    """People with two candidate IDs sharing one principal committee."""
    groups = []
    for person in people:
        by_committee: dict[str, list] = {}
        for cid in person['fec_candidate_ids']:
            committee = principal.get(cid)
            if committee:
                by_committee.setdefault(committee, []).append(cid)
        for committee, ids in sorted(by_committee.items()):
            if len(ids) < 2:
                continue
            current = person.get('chamber_120') or person.get('chamber_119')
            kept = None
            for cid in ids:
                if offices.get(cid) == current:
                    kept = cid
                    break
            kept = kept or ids[-1]
            groups.append(
                {
                    'person_key': person['person_key'],
                    'committee': committee,
                    'ids': sorted(ids),
                    'kept_id': kept,
                    'dropped_ids': sorted(cid for cid in ids if cid != kept),
                }
            )
    return groups


def apply_transfer_dedup(weball: dict, groups: list[dict]) -> tuple[dict, list[dict]]:
    """Zero the dropped view's transfer fields; returns (adjusted, report)."""
    adjusted = {key: dict(entry) for key, entry in weball.items()}
    report = []
    for group in groups:
        for cycle in sorted({cycle for (_cid, cycle) in weball}):
            dropped_amounts = {}
            kept_amounts = {}
            for field in TRANSFER_FIELDS:
                kept_row = adjusted.get((group['kept_id'], cycle))
                kept_amounts[field] = kept_row[field] if kept_row else 0
                dropped_amounts[field] = 0
                for dropped_id in group['dropped_ids']:
                    row = adjusted.get((dropped_id, cycle))
                    if row is None:
                        continue
                    dropped_amounts[field] += row[field]
                    row[field] = 0
            if any(dropped_amounts.values()) or any(kept_amounts.values()):
                report.append(
                    {
                        'person_key': group['person_key'],
                        'cycle': cycle,
                        'committee': group['committee'],
                        'kept_id': group['kept_id'],
                        'dropped_ids': group['dropped_ids'],
                        'kept': kept_amounts,
                        'dropped': dropped_amounts,
                    }
                )
    return adjusted, report


def election_year(pgi: str) -> int | None:
    """The cycle a TRANSACTION_PGI designates (P2026/G2024 -> 2026/2024)."""
    digits = ''.join(ch for ch in (pgi or '') if ch.isdigit())
    return int(digits) if len(digits) == 4 else None


def attribute_refunds_by_election(rows: list, filing_cycle: int) -> dict:
    """Re-attribute negative pas2 rows (refunds) from filing cycle to election year.

    `rows` are Pas2Row objects filed in `filing_cycle` for one
    candidate+committee. Returns {(candidate_id, election_cycle): cents}
    with each refund moved to the cycle its TRANSACTION_PGI names, and
    every other row kept in the filing cycle. Rows whose PGI names no year
    stay in the filing cycle.
    """
    attributed: dict[tuple, int] = {}
    for row in rows:
        cents = row.amount_cents
        if cents < 0:
            year = election_year(row.election)
            cycle = year if year is not None else filing_cycle
        else:
            cycle = filing_cycle
        key = (row.candidate_id, cycle)
        attributed[key] = attributed.get(key, 0) + cents
    return attributed

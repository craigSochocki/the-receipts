"""Weball + pas2 money, re-derived from the pinned snapshot with fresh parsers.

Rules (methodology §2–§4, §8 item 15): committee money is the 24K/24P pas2
rows, voided earmarks excluded, deduped on the tracker identity key
(preferring the non-memo row, then the earliest filing); committees are
classified from the same-cycle committee master with the reviewed
overrides; weball individual totals are counted once per (person, cycle)
where two candidate IDs repeat one committee's summary.
"""

from pathlib import Path

from receipts.square_one import parsers

CONTRIBUTION_TYPES = ('24K', '24P')
CORPORATE_TYPES = ('Q', 'N')
CORPORATE_ORGS = ('C', 'W')
PARTY_TYPES = ('X', 'Y')
LEADERSHIP_DESIGNATION = 'D'
PAC_CLASS_BY_ORG = {
    'L': 'labor',
    'T': 'trade',
    'M': 'membership',
    'V': 'cooperative',
}
OTHER_CLASSES = ('party', 'leadership', 'labor', 'trade', 'membership', 'cooperative')
ALL_CLASSES = ('aipac', 'corporate', *OTHER_CLASSES, 'other_unclassified')

# weball attribute -> field name in the per-(candidate, cycle) record.
WEBALL_MONEY = (
    ('total_receipts', 'total_receipts'),
    ('transfers_from_authorized', 'transfers_from_auth'),
    ('total_disbursements', 'total_disbursements'),
    ('transfers_to_authorized', 'transfers_to_auth'),
    ('cash_start', 'cash_start'),
    ('cash_end', 'cash_on_hand'),
    ('candidate_contributions', 'cand_contrib'),
    ('candidate_loans', 'cand_loans'),
    ('other_loans', 'other_loans'),
    ('candidate_loan_repayments', 'cand_loan_repayments'),
    ('other_loan_repayments', 'other_loan_repayments'),
    ('debts_owed_by', 'debts_owed_by'),
    ('individual_contributions', 'individual'),
    ('other_committee_contributions', 'other_committee_col26'),
    ('party_contributions', 'party_col27'),
)
# Every financial field the double-count rule can zero (methodology §8 item 15
# as implemented: a dropped copy's field is zeroed wherever it equals the
# kept copy's, not only for the individual column).
DEDUP_FIELDS = (
    'total_receipts',
    'transfers_from_auth',
    'total_disbursements',
    'transfers_to_auth',
    'cash_start',
    'cash_on_hand',
    'cand_contrib',
    'cand_loans',
    'other_loans',
    'cand_loan_repayments',
    'other_loan_repayments',
    'debts_owed_by',
    'individual',
)
# Columns zeroed by the §8 item 15 extension, where the record flags it.
EXTENSION_FIELDS = (
    'total_receipts',
    'transfers_from_auth',
    'total_disbursements',
    'transfers_to_auth',
)


def classify_committee(row: parsers.CommitteeRow, aipac_id: str, overrides: dict) -> str:
    """The class a committee's money counts as; a reviewed override beats the filed code."""
    if row.committee_id == aipac_id:
        return 'aipac'
    if row.committee_id in overrides:
        return overrides[row.committee_id]
    if row.committee_type in CORPORATE_TYPES and row.organization_type in CORPORATE_ORGS:
        return 'corporate'
    if row.committee_type in PARTY_TYPES:
        return 'party'
    if row.designation == LEADERSHIP_DESIGNATION:
        return 'leadership'
    if row.committee_type in CORPORATE_TYPES:
        return PAC_CLASS_BY_ORG.get(row.organization_type, 'other_unclassified')
    return 'other_unclassified'


def _is_voided_earmark(row: parsers.Pas2Row) -> bool:
    return row.is_earmark and row.amount_cents < 0


def derive_committee_money(
    bulk_dir: Path, cycles: list[int], aipac_id: str, overrides: dict
) -> tuple[dict, dict]:
    """Counted pas2 money per (candidate_id, cycle), plus exclusion stats.

    Returns ({(candidate_id, cycle): {class: cents, class_earmark: cents}},
    stats). Rows from a committee missing from the same-cycle master are
    dropped (the master join), and counted in the stats, never silently.
    """
    counted: dict[tuple[str, int], dict[str, int]] = {}
    stats = {
        'rows_read': 0,
        'rows_24k': 0,
        'voided_earmark_rows': 0,
        'voided_earmark_cents': 0,
        'dedup_dropped_rows': 0,
        'dedup_dropped_cents': 0,
        'unregistered_committee_rows': 0,
        'unregistered_committee_cents': 0,
        'blank_candidate_rows': 0,
        'blank_candidate_cents': 0,
    }
    for cycle in cycles:
        registry = {r.committee_id: r for r in parsers.committee_rows(bulk_dir, cycle)}
        kept: dict[tuple, parsers.Pas2Row] = {}
        dropped: list[parsers.Pas2Row] = []
        for row in parsers.pas2_rows(bulk_dir, cycle):
            stats['rows_read'] += 1
            if row.transaction_type not in CONTRIBUTION_TYPES:
                continue
            stats['rows_24k'] += 1
            if _is_voided_earmark(row):
                stats['voided_earmark_rows'] += 1
                stats['voided_earmark_cents'] += row.amount_cents
                continue
            if row.committee_id not in registry:
                stats['unregistered_committee_rows'] += 1
                stats['unregistered_committee_cents'] += row.amount_cents
                continue
            if not row.candidate_id.strip():
                stats['blank_candidate_rows'] += 1
                stats['blank_candidate_cents'] += row.amount_cents
                continue
            prior = kept.get(row.identity)
            if prior is None:
                kept[row.identity] = row
            elif (row.is_memo, row.file_number) < (prior.is_memo, prior.file_number):
                dropped.append(prior)
                kept[row.identity] = row
            else:
                dropped.append(row)
        stats['dedup_dropped_rows'] += len(dropped)
        stats['dedup_dropped_cents'] += sum(r.amount_cents for r in dropped)
        for row in kept.values():
            kind = classify_committee(registry[row.committee_id], aipac_id, overrides)
            entry = counted.setdefault((row.candidate_id, cycle), {})
            entry[kind] = entry.get(kind, 0) + row.amount_cents
            if row.is_earmark:
                entry[f'{kind}_earmark'] = entry.get(f'{kind}_earmark', 0) + row.amount_cents
    return counted, stats


def derive_weball(bulk_dir: Path, cycles: list[int]) -> dict:
    """Weball money per (candidate_id, cycle), in cents, as filed."""
    weball: dict[tuple[str, int], dict] = {}
    for cycle in cycles:
        for row in parsers.weball_rows(bulk_dir, cycle):
            entry = {field: row.cents(attr) for attr, field in WEBALL_MONEY}
            entry['loan_repayments'] = (
                entry['cand_loan_repayments'] + entry['other_loan_repayments']
            )
            entry['coverage_end'] = row.coverage_end
            entry['elections'] = (
                row.special_election,
                row.primary_election,
                row.runoff_election,
                row.general_election,
            )
            weball[(row.candidate_id, cycle)] = entry
    return weball


def _chamber_after_cycle(person: dict, cycle: int) -> str | None:
    if cycle >= 2026:
        return person.get('chamber_120') or None
    if cycle >= 2024:
        return person.get('chamber_119') or None
    return None


def derive_dedup_candidates(weball: dict, people: list[dict]) -> list[dict]:
    """(person, cycle) groups where two IDs repeat one individual total.

    The kept ID follows the recorded rule order where the files decide it:
    the election-result W marker, then the chamber after the cycle. Groups
    the files cannot decide are returned with kept_id None, for the record
    to settle (and the audit to check).
    """
    found = []
    for person in people:
        ids = person['fec_candidate_ids']
        if len(ids) < 2:
            continue
        cycles = sorted({c for (cid, c) in weball if cid in ids})
        for cycle in cycles:
            rows = [(cid, weball[(cid, cycle)]) for cid in ids if (cid, cycle) in weball]
            if len(rows) < 2:
                continue
            by_value: dict[int, list[str]] = {}
            for cid, entry in rows:
                by_value.setdefault(entry['individual'], []).append(cid)
            for value, group in by_value.items():
                if value == 0 or len(group) < 2:
                    continue
                kept = None
                reason = None
                winners = [cid for cid in group if 'W' in weball[(cid, cycle)]['elections']]
                if len(winners) == 1:
                    kept, reason = winners[0], 'election-result marker'
                else:
                    chamber = _chamber_after_cycle(person, cycle)
                    office = {'House': 'H', 'Senate': 'S'}.get(chamber or '')
                    matches = [cid for cid in group if office and cid.startswith(office)]
                    if len(matches) == 1:
                        kept, reason = matches[0], 'chamber after cycle'
                found.append(
                    {
                        'person_key': person['person_key'],
                        'cycle': cycle,
                        'kept_id': kept,
                        'dropped_ids': [cid for cid in group if cid != kept] if kept else group,
                        'amount_cents': value,
                        'reason': reason,
                    }
                )
    return found


def check_dedup_record(weball: dict, records: list[dict]) -> list[str]:
    """Every recorded §8 item 15 decision, verified against the weball files."""
    problems = []
    for record in records:
        cycle = record['cycle']
        kept = weball.get((record['kept_id'], cycle))
        if kept is None:
            problems.append(f'{record["person_key"]} {cycle}: kept ID has no weball row')
            continue
        if kept['individual'] != round(float(record['amount']) * 100):
            problems.append(
                f'{record["person_key"]} {cycle}: kept individual '
                f'{kept["individual"]} != recorded {record["amount"]}'
            )
        for dropped_id in record['dropped_ids']:
            dropped = weball.get((dropped_id, cycle))
            if dropped is None:
                problems.append(f'{record["person_key"]} {cycle}: dropped ID has no weball row')
            elif dropped['individual'] != kept['individual']:
                problems.append(
                    f'{record["person_key"]} {cycle}: dropped {dropped_id} individual '
                    f'{dropped["individual"]} != kept {kept["individual"]}'
                )
        if record.get('extend_to_columns_6_9'):
            expected = record['extend_expected_cents']
            for field, key in (
                ('total_receipts', 'col6_kept_minus_dropped'),
                ('transfers_from_auth', 'col7_kept_minus_dropped'),
                ('total_disbursements', 'col8_kept_minus_dropped'),
            ):
                actual = kept[field] - weball[(record['dropped_ids'][0], cycle)][field]
                if actual != expected[key]:
                    problems.append(
                        f'{record["person_key"]} {cycle}: extension {field} '
                        f'{actual} != recorded {expected[key]}'
                    )
    return problems


def apply_dedup(weball: dict, records: list[dict]) -> tuple[dict, list[dict]]:
    """Weball with the recorded §8 item 15 corrections applied, and the fields left counted.

    A dropped copy's field is zeroed wherever it equals the kept copy's (the
    rule as implemented); where the extension flag is set, cols 6–9 are
    zeroed even when they differ, under the recorded guards. Fields that
    differ without the extension stay counted in both copies, and are
    returned as the differing list.
    """
    adjusted = {key: dict(entry) for key, entry in weball.items()}
    differing = []
    for record in records:
        cycle = record['cycle']
        kept = adjusted.get((record['kept_id'], cycle))
        if kept is None:
            continue
        extended = bool(record.get('extend_to_columns_6_9'))
        for dropped_id in record['dropped_ids']:
            entry = adjusted.get((dropped_id, cycle))
            if entry is None:
                continue
            for field in DEDUP_FIELDS:
                if (extended and field in EXTENSION_FIELDS) or entry[field] == kept[field]:
                    entry[field] = 0
                else:
                    differing.append(
                        {
                            'person_key': record['person_key'],
                            'cycle': cycle,
                            'candidate_id': dropped_id,
                            'field': field,
                            'kept_id': record['kept_id'],
                            'kept_cents': kept[field],
                            'dropped_cents': entry[field],
                        }
                    )
            entry['loan_repayments'] = (
                entry['cand_loan_repayments'] + entry['other_loan_repayments']
            )
    return adjusted, differing


def rollup_person_cycle(
    weball: dict, committee_money: dict, people: list[dict], cycles: list[int]
) -> dict:
    """Per (person_key, cycle): weball + committee money, summed across the person's IDs."""
    per_person: dict[tuple[str, int], dict] = {}
    weball_fields = (
        'individual',
        'total_receipts',
        'transfers_from_auth',
        'total_disbursements',
        'transfers_to_auth',
        'cash_on_hand',
        'cand_contrib',
        'cand_loans',
        'loan_repayments',
        'debts_owed_by',
        'other_committee_col26',
        'party_col27',
    )
    for person in people:
        key = person['person_key']
        for cycle in cycles:
            totals: dict[str, int] = {field: 0 for field in weball_fields}
            for kind in ALL_CLASSES:
                totals[kind] = 0
                totals[f'{kind}_earmark'] = 0
            coverage_end = None
            has_weball = False
            has_committee_money = False
            for cid in person['fec_candidate_ids']:
                web = weball.get((cid, cycle))
                if web is not None:
                    has_weball = True
                    for field in weball_fields:
                        totals[field] += web[field]
                    coverage_end = web['coverage_end']
                money = committee_money.get((cid, cycle))
                if money is not None:
                    has_committee_money = True
                    for kind in ALL_CLASSES:
                        totals[kind] += money.get(kind, 0)
                        totals[f'{kind}_earmark'] += money.get(f'{kind}_earmark', 0)
            per_person[(key, cycle)] = {
                'person_key': key,
                'cycle': cycle,
                **totals,
                'coverage_end': coverage_end,
                'has_weball': has_weball,
                'has_committee_money': has_committee_money,
            }
    return per_person

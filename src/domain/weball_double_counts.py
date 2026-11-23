"""Weball repeats a chamber-switcher's whole summary under both IDs.

data/source/dedup-applied.json records each case. The dropped copy is
zeroed wherever it equals the kept copy; a column that differs is
flagged, not corrected. One recorded exception (Curtis 2024) also
zeroes receipts, transfers and disbursements, behind exact guards.
Evidence: research/self-funding-notes.md.
"""
from src.domain.money import ZERO, Money

FINANCIAL_FIELDS = [
    'total_receipts', 'transfers_from_authorized', 'total_disbursements',
    'transfers_to_authorized', 'cash_start', 'cash_end', 'candidate_contributions',
    'candidate_loans', 'other_loans', 'candidate_loan_repayments',
    'other_loan_repayments', 'debts_owed_by', 'individual_contributions',
]
EXTENDED_FIELDS = FINANCIAL_FIELDS[:4]
EXTENSION_GUARDS = [('total_receipts', 'col6_kept_minus_dropped'),
                    ('transfers_from_authorized', 'col7_kept_minus_dropped'),
                    ('total_disbursements', 'col8_kept_minus_dropped')]


class DoubleCountReport:
    def __init__(self):
        self.groups_applied = 0
        self.cells_zeroed = 0
        self.differing = []


def remove_double_counts(amounts, records, person_keys):
    """Correct `amounts` ({(candidate_id, cycle): {field: Money}}) in place."""
    report = DoubleCountReport()
    for record in records:
        kept, dropped_copies = _copies(amounts, record, person_keys)
        report.groups_applied += 1
        extended = bool(record.get('extend_to_columns_6_9'))
        for dropped_id, dropped in dropped_copies:
            if extended:
                _check_extension(record, kept, dropped)
            for field in FINANCIAL_FIELDS:
                if (extended and field in EXTENDED_FIELDS) or dropped[field] == kept[field]:
                    report.cells_zeroed += bool(dropped[field])
                    dropped[field] = ZERO
                else:
                    report.differing.append((record, dropped_id, field, kept[field], dropped[field]))
    return report


def _copies(amounts, record, person_keys):
    cycle, recorded = record['cycle'], Money.parse(record['amount'])
    if record['person_key'] not in person_keys:
        raise SystemExit(f"dedup-applied.json has unknown person_key {record['person_key']}")

    def copy(candidate_id, role):
        found = amounts.get((candidate_id, cycle))
        if found is None:
            raise SystemExit(f"{record['name']} {cycle}: {role} entry {candidate_id} not in weball")
        if found['individual_contributions'] != recorded:
            raise SystemExit(f"{record['name']} {cycle}: {role} TTL_INDIV_CONTRIB "
                             f"{found['individual_contributions']} != recorded {record['amount']}")
        return found

    kept = copy(record['kept_id'], 'kept')
    return kept, [(dropped_id, copy(dropped_id, 'dropped')) for dropped_id in record['dropped_ids']]


def _check_extension(record, kept, dropped):
    guards = record.get('extend_expected_cents') or {}

    def require(condition, what):
        if not condition:
            raise SystemExit(f"{record['name']} {record['cycle']}: Curtis extension guard "
                             f"failed: {what}")

    for field, key in EXTENSION_GUARDS:
        require((kept[field].cents - dropped[field].cents) == guards.get(key),
                f'{field} kept-minus-dropped != recorded {key}')
    require(dropped['transfers_to_authorized'].cents == guards.get('col9_dropped'),
            'dropped transfers_to_authorized != recorded col9_dropped')
    require(kept['transfers_to_authorized'].cents == guards.get('col9_kept'),
            'kept transfers_to_authorized != recorded col9_kept')

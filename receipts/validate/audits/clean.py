"""Clean counts, the named clean-rule spot cases, and the unopposed rule."""

from collections.abc import Mapping, Sequence
from typing import Any

from receipts.common.settings import settings
from receipts.domain.clean_2026 import is_career_clean
from receipts.validate.audits.published import is_num


def count_where(records, key, value):
    """Rows whose `key` is `value` (identity: the clean verdicts are True/False/None)."""
    return sum(1 for r in records if r[key] is value)


def clean_count_values(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """The clean counts, keyed by baseline key; the audits pin these, the build checks them."""
    house120 = [r for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'House']
    house_clean = [r for r in house120 if r['clean_2026'] is True]
    career_clean = [r for r in house120 if is_career_clean(r)]
    career_keys = {r['person_key'] for r in career_clean}
    found = {
        'clean_2026.true_total': count_where(records, 'clean_2026', True),
        'clean_2026.false_total': count_where(records, 'clean_2026', False),
        'clean_2026.null_total': count_where(records, 'clean_2026', None),
        'clean_2026.house_120th_verified_clean': len(house_clean),
        'clean_2026.house_120th_career_clean': len(career_clean),
        'clean_2026.house_120th_clean_2026_not_career_clean': sum(
            1 for r in house_clean if r['person_key'] not in career_keys
        ),
    }
    for party in ('Democrat', 'Republican'):
        found[f'clean_2026.house_120th_verified_clean_{party.lower()}'] = sum(
            1 for r in house_clean if r['party_120'] == party
        )
        found[f'clean_2026.house_120th_career_clean_{party.lower()}'] = sum(
            1 for r in career_clean if r['party_120'] == party
        )
    return found


def clean_counts(audit, dataset):
    """(d) clean counts (baseline clean_2026.*)"""
    values = clean_count_values(dataset.records)
    for key in ('true_total', 'false_total', 'null_total'):
        audit.pin(f'clean_2026 {key}', f'clean_2026.{key}', values[f'clean_2026.{key}'])
    audit.pin(
        '120th House clean',
        'clean_2026.house_120th_verified_clean',
        values['clean_2026.house_120th_verified_clean'],
    )
    for party in ('Democrat', 'Republican'):
        audit.pin(
            f'120th House clean {party}',
            f'clean_2026.house_120th_verified_clean_{party.lower()}',
            values[f'clean_2026.house_120th_verified_clean_{party.lower()}'],
        )
    audit.pin(
        'career-clean 120th House',
        'clean_2026.house_120th_career_clean',
        values['clean_2026.house_120th_career_clean'],
    )
    for party in ('Democrat', 'Republican'):
        audit.pin(
            f'career-clean 120th House {party}',
            f'clean_2026.house_120th_career_clean_{party.lower()}',
            values[f'clean_2026.house_120th_career_clean_{party.lower()}'],
        )
    audit.pin(
        'current-cycle clean but not career-clean (120th House)',
        'clean_2026.house_120th_clean_2026_not_career_clean',
        values['clean_2026.house_120th_clean_2026_not_career_clean'],
    )


def clean_spot_cases(audit, dataset):
    """(m) clean-rule spot cases (methodology §14)."""

    def sf26_view(rec):
        return [
            {'coverage_end_date': e['coverage_end_date'], 'candidate_loans': e['candidate_loans']}
            for e in rec['self_funding_per_cycle']
            if e['cycle'] == settings().cycles.current
        ]

    const = dataset.by_key['anthonyconstantinonyhouse']
    audit.pin(
        'Constantino clean-rule spot case',
        'spot.clean.constantino',
        {
            'clean_2026': const['clean_2026'],
            'self_funding_2026_rows': sf26_view(const),
            'all_ie_support_2026': const['all_ie_support_2026'],
            'all_ie_oppose_2026': const['all_ie_oppose_2026'],
        },
    )
    luria = dataset.by_key['L000591']
    audit.pin(
        'Luria clean-rule spot case',
        'spot.clean.luria',
        {
            'clean_2026': luria['clean_2026'],
            'self_funding_2026_rows': sf26_view(luria),
            'other_committees_total_2026': luria['other_committees_total_2026'],
            'all_ie_support_2026': luria['all_ie_support_2026'],
        },
    )
    audit.check(
        'Luria: her real current-cycle campaign ID is still not linked in the roster',
        'H6VA02198' not in luria['fec_candidate_ids'],
    )


def unopposed(audit, dataset):
    """(m) unopposed exclusion."""
    unopposed = sorted(r['person_key'] for r in dataset.records if r['unopposed_2026'] is True)
    audit.pin('members unopposed in 2026', 'spot.unopposed_2026', unopposed)
    audit.pin(
        'members with clean_2026 null (unverified or unopposed-and-not-dirty)',
        'spot.clean_2026_null',
        sorted(r['person_key'] for r in dataset.records if r['clean_2026'] is None),
    )
    audit.check(
        'an unopposed member with no net dirty money is null, not clean',
        all(
            r['clean_2026'] is None
            for r in dataset.records
            if r['unopposed_2026'] is True and is_num(r['dirty_2026']) and r['dirty_2026'] <= 0
        ),
    )
    audit.check(
        'UNOPPOSED note sits exactly on the unopposed members held null',
        all(
            ('UNOPPOSED' in r['data_notes'])
            == (r['unopposed_2026'] is True and r['clean_2026'] is None)
            for r in dataset.records
        ),
    )
    audit.check(
        'UNVERIFIED note sits exactly on the null members who are not unopposed',
        all(
            ('UNVERIFIED' in r['data_notes'])
            == (r['clean_2026'] is None and r['unopposed_2026'] is not True)
            for r in dataset.records
        ),
    )
    king_hinds = dataset.by_key['K000404']
    audit.check(
        'King-Hinds contested, not unopposed — MP race is district 01',
        king_hinds['unopposed_2026'] is False and 'UNOPPOSED' not in king_hinds['data_notes'],
        f'unopposed={king_hinds["unopposed_2026"]}',
    )

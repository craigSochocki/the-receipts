"""Clean counts, the named clean-rule spot cases, and the unopposed rule."""

from receipts.common.settings import settings
from receipts.domain.clean_2026 import is_career_clean
from receipts.validate.audits.published import is_num


def pin_by_party(audit, label, key, members):
    for party in ('Democrat', 'Republican'):
        audit.pin(
            f'{label} {party}',
            f'{key}_{party.lower()}',
            sum(1 for r in members if r['party_120'] == party),
        )


def clean_counts(audit, dataset):
    """(d) clean counts (baseline clean_2026.*)"""
    records = dataset.records
    for key, value in (('true_total', True), ('false_total', False), ('null_total', None)):
        audit.pin(
            f'clean_2026 {key}',
            f'clean_2026.{key}',
            sum(1 for r in records if r['clean_2026'] is value),
        )
    house120 = [r for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'House']
    house_clean = [r for r in house120 if r['clean_2026'] is True]
    audit.pin('120th House clean', 'clean_2026.house_120th_verified_clean', len(house_clean))
    pin_by_party(audit, '120th House clean', 'clean_2026.house_120th_verified_clean', house_clean)
    career_clean = [r for r in house120 if is_career_clean(r)]
    audit.pin('career-clean 120th House', 'clean_2026.house_120th_career_clean', len(career_clean))
    pin_by_party(
        audit, 'career-clean 120th House', 'clean_2026.house_120th_career_clean', career_clean
    )
    career_keys = {r['person_key'] for r in career_clean}
    audit.pin(
        '2026-clean but not career-clean (120th House)',
        'clean_2026.house_120th_clean_2026_not_career_clean',
        sum(1 for r in house_clean if r['person_key'] not in career_keys),
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
        'Luria: real 2026 campaign ID H6VA02198 is still not linked in the roster',
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

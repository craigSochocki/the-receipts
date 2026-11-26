"""The tiered dirty rule: flag and tier counts, corp-only splits, next-cycle targets, spot cases."""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from receipts.common.settings import settings
from receipts.domain.clean_2026 import corporate_money_material
from receipts.domain.targets import DIRTY_UNDER, primary_targets

PRESETS = ('balanced', 'lenient')
TIER_SPOT_FIELDS = (
    'clean_2026',
    'corp_2026',
    'aipac_direct_2026',
    'dirty_2026',
    'aipac_udp_flag_2026',
    'tier_balanced_2026',
    'tier_lenient_2026',
)
# Members whose tier turns on a net-negative AIPAC component (refunds).
TIER_SPOT_CASES = (
    ('ryan', 'Patrick Ryan'),
    ('randall', 'Emily Randall'),
    ('garcia', 'Sylvia R. Garcia'),
)


def tier_count_values(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """The flag and tier counts, keyed by baseline key; the audits pin these, the build checks them."""
    r120 = [r for r in records if r['in_120th'] == 'yes']
    found = {
        'tiered_2026.aipac_udp_flag_all': sum(
            1 for r in records if r['aipac_udp_flag_2026'] is True
        ),
        'tiered_2026.aipac_udp_flag_120th': sum(
            1 for r in r120 if r['aipac_udp_flag_2026'] is True
        ),
    }
    for preset in PRESETS:
        tiers = Counter(r[f'tier_{preset}_2026'] for r in r120)
        for name in ('clean', 'below_threshold', 'dirty'):
            found[f'tiered_2026.{preset}.{name}'] = tiers.get(name, 0)
        found[f'tiered_2026.{preset}.null'] = tiers.get(None, 0)
        found[f'tiered_2026.{preset}.not_dirty'] = tiers.get('clean', 0) + tiers.get(
            'below_threshold', 0
        )
    return found


def flag_counts(audit, records, r120, values):
    audit.pin(
        'aipac_udp_flag_2026 120th',
        'tiered_2026.aipac_udp_flag_120th',
        values['tiered_2026.aipac_udp_flag_120th'],
    )
    audit.pin(
        'aipac_udp_flag_2026 roster-wide',
        'tiered_2026.aipac_udp_flag_all',
        values['tiered_2026.aipac_udp_flag_all'],
    )
    audit.check(
        'aipac_udp_flag_2026 is a boolean on every row',
        all(r['aipac_udp_flag_2026'] in (True, False) for r in records),
    )


def preset_tiers(audit, records, r120, preset, values):
    column = f'tier_{preset}_2026'
    for tier_name in ('clean', 'below_threshold', 'dirty'):
        audit.pin(
            f'{column} {tier_name}',
            f'tiered_2026.{preset}.{tier_name}',
            values[f'tiered_2026.{preset}.{tier_name}'],
        )
    audit.pin(
        f'{column} null',
        f'tiered_2026.{preset}.null',
        values[f'tiered_2026.{preset}.null'],
    )
    audit.pin(
        f'{column} not-dirty (clean + below_threshold)',
        f'tiered_2026.{preset}.not_dirty',
        values[f'tiered_2026.{preset}.not_dirty'],
    )
    audit.check(
        f'{column} is null exactly where clean_2026 is null',
        all((r[column] is None) == (r['clean_2026'] is None) for r in records),
    )
    # A looser preset only relaxes the corporate rule, so Strict-clean stays not dirty.
    audit.check(
        f'no Strict-clean member is dirty under {preset}',
        all(r[column] != 'dirty' for r in records if r['clean_2026'] is True),
    )
    audit.check(
        f'every flagged member is dirty under {preset}',
        all(
            r[column] == 'dirty'
            for r in records
            if r['aipac_udp_flag_2026'] is True and r['clean_2026'] is not None
        ),
    )


def corp_only_split(audit, r120):
    """Members with corporate PAC money and no AIPAC or UDP money, and where each preset puts them."""
    corp_only = [
        r
        for r in r120
        if r['corp_2026'] > 0 and r['aipac_direct_2026'] == 0 and r['udp_benefit_2026'] == 0
    ]
    audit.pin('corp-only members in the 120th', 'tiered_2026.corp_only_2026_120th', len(corp_only))
    for preset in PRESETS:
        thresholds = settings().verification.tolerance_presets[preset]
        staying = sum(
            corporate_money_material(r['corp_2026'], r['total_receipts_2026'], thresholds)
            for r in corp_only
        )
        audit.pin(
            f'corp-only staying dirty under {preset}',
            f'tiered_2026.corp_only_staying_dirty_{preset}',
            staying,
        )
        audit.pin(
            f'corp-only below threshold under {preset}',
            f'tiered_2026.corp_only_below_{preset}',
            len(corp_only) - staying,
        )


def targets_next(audit, r120):
    """The next cycle's primary targets by preset: [House, Senate]."""
    cycle = settings().cycles.next
    for preset in DIRTY_UNDER:
        targets = primary_targets(r120, preset, cycle)
        audit.pin(
            f'next-cycle targets {preset} (House, Senate)',
            f'targets.{preset}',
            [
                sum(1 for r in targets if r['chamber_120'] == chamber)
                for chamber in ('House', 'Senate')
            ],
        )


def tier_spot_cases(audit, records):
    for slug, name in TIER_SPOT_CASES:
        rec = next(r for r in records if r['full_name'] == name)
        audit.pin(
            f'{name} tier spot case', f'spot.tier.{slug}', {f: rec[f] for f in TIER_SPOT_FIELDS}
        )


def tiered_rule(audit, dataset):
    """(o) tiered dirty rule: flag, tiers, corp-only splits, targets."""
    records = dataset.records
    r120 = [r for r in records if r['in_120th'] == 'yes']
    values = tier_count_values(records)
    flag_counts(audit, records, r120, values)
    for preset in PRESETS:
        preset_tiers(audit, records, r120, preset, values)
    corp_only_split(audit, r120)
    targets_next(audit, r120)
    tier_spot_cases(audit, records)

"""The tiered dirty rule: flag and tier counts, corp-only splits, 2028 targets, spot cases."""

from collections import Counter

from receipts.common.settings import settings
from receipts.domain.clean_2026 import corporate_money_material

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


def flag_counts(audit, records, r120):
    audit.pin(
        'aipac_udp_flag_2026 120th',
        'tiered_2026.aipac_udp_flag_120th',
        sum(1 for r in r120 if r['aipac_udp_flag_2026'] is True),
    )
    audit.pin(
        'aipac_udp_flag_2026 roster-wide',
        'tiered_2026.aipac_udp_flag_all',
        sum(1 for r in records if r['aipac_udp_flag_2026'] is True),
    )
    audit.check(
        'aipac_udp_flag_2026 is a boolean on every row',
        all(r['aipac_udp_flag_2026'] in (True, False) for r in records),
    )


def preset_tiers(audit, records, r120, preset):
    column = f'tier_{preset}_2026'
    got = Counter(r[column] for r in r120)
    for tier_name in ('clean', 'below_threshold', 'dirty'):
        audit.pin(
            f'{column} {tier_name}', f'tiered_2026.{preset}.{tier_name}', got.get(tier_name, 0)
        )
    audit.pin(f'{column} null', f'tiered_2026.{preset}.null', got.get(None, 0))
    audit.pin(
        f'{column} not-dirty (clean + below_threshold)',
        f'tiered_2026.{preset}.not_dirty',
        got.get('clean', 0) + got.get('below_threshold', 0),
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


def targets_2028(audit, r120):
    """House Democrats and Class 3 Senate Democrats on the 2028 watchlist under each preset."""
    house_dem = [r for r in r120 if r['chamber_120'] == 'House' and r['party_120'] == 'Democrat']
    sen3_dem = [
        r
        for r in r120
        if r['chamber_120'] == 'Senate' and r['party_120'] == 'Democrat' and r['senate_class'] == 3
    ]
    audit.pin(
        '2028 targets Strict House',
        'tiered_2026.targets_2028_strict_house',
        sum(1 for r in house_dem if r['dirty_2026'] > 0),
    )
    audit.pin(
        '2028 targets Strict Senate Class 3',
        'tiered_2026.targets_2028_strict_senate_class3',
        sum(1 for r in sen3_dem if r['dirty_2026'] > 0),
    )
    for preset in PRESETS:
        column = f'tier_{preset}_2026'
        audit.pin(
            f'2028 targets {preset} House',
            f'tiered_2026.targets_2028_{preset}_house',
            sum(1 for r in house_dem if r[column] == 'dirty'),
        )
        audit.pin(
            f'2028 targets {preset} Senate Class 3',
            f'tiered_2026.targets_2028_{preset}_senate_class3',
            sum(1 for r in sen3_dem if r[column] == 'dirty'),
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
    flag_counts(audit, records, r120)
    for preset in PRESETS:
        preset_tiers(audit, records, r120, preset)
    corp_only_split(audit, r120)
    targets_2028(audit, r120)
    tier_spot_cases(audit, records)

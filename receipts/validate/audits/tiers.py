"""The tiered dirty rule, re-derived independently of domain/clean_2026.py.

This copy is deliberate: tests/test_rule_agreement.py keeps it in step with domain/."""

from collections import Counter

from receipts.common.settings import settings


# The tier logic is re-derived from the config thresholds, independently of
# compute_2026.py (same definitions, separate code).
def corp_material(corp, total_receipts, preset):
    th = settings().verification.tolerance_presets[preset]
    if corp <= th.corp_amount:
        return False
    if (
        not isinstance(total_receipts, (int, float))
        or isinstance(total_receipts, bool)
        or total_receipts <= 0
    ):
        return False
    return corp / total_receipts > th.corp_share


def flag_for(aipac_direct, udp_benefit):
    """Any AIPAC direct dollar or UDP benefit dollar flags the member under every preset."""
    return bool(aipac_direct > 0 or udp_benefit > 0)


def tier_for(clean, flag, corp, total_receipts, preset):
    if clean is None:
        return None
    if flag or corp_material(corp, total_receipts, preset):
        return 'dirty'
    if corp > 0:
        return 'below_threshold'
    return 'clean'


def tiered_rule(audit, dataset):
    """(o) tiered dirty rule: flag, tiers, corp-only splits, targets."""
    r120 = [r for r in dataset.records if r['in_120th'] == 'yes']
    audit.pin(
        'aipac_udp_flag_2026 120th',
        'tiered_2026.aipac_udp_flag_120th',
        sum(1 for r in r120 if r['aipac_udp_flag_2026'] is True),
    )
    audit.pin(
        'aipac_udp_flag_2026 roster-wide',
        'tiered_2026.aipac_udp_flag_all',
        sum(1 for r in dataset.records if r['aipac_udp_flag_2026'] is True),
    )
    audit.check(
        'aipac_udp_flag_2026 is a boolean on every row',
        all(r['aipac_udp_flag_2026'] in (True, False) for r in dataset.records),
    )
    for preset in ('balanced', 'lenient'):
        got = Counter(r[f'tier_{preset}_2026'] for r in r120)
        for tier_name in ('clean', 'below_threshold', 'dirty'):
            audit.pin(
                f'tier_{preset}_2026 {tier_name}',
                f'tiered_2026.{preset}.{tier_name}',
                got.get(tier_name, 0),
            )
        audit.pin(f'tier_{preset}_2026 null', f'tiered_2026.{preset}.null', got.get(None, 0))
        audit.pin(
            f'tier_{preset}_2026 not-dirty (clean + below_threshold)',
            f'tiered_2026.{preset}.not_dirty',
            got.get('clean', 0) + got.get('below_threshold', 0),
        )
        # Tier nulls coincide exactly with clean_2026 nulls.
        audit.check(
            f'tier_{preset}_2026 is null exactly where clean_2026 is null',
            all(
                (r[f'tier_{preset}_2026'] is None) == (r['clean_2026'] is None)
                for r in dataset.records
            ),
        )
        # Monotonicity: a Strict-clean member is never dirty under a
        # looser preset (a looser preset only relaxes the corp rule).
        audit.check(
            f'no Strict-clean member is dirty under {preset}',
            all(
                r[f'tier_{preset}_2026'] != 'dirty'
                for r in dataset.records
                if r['clean_2026'] is True
            ),
        )
        # The flag takes precedence: every flagged member is dirty
        # under every preset.
        audit.check(
            f'every flagged member is dirty under {preset}',
            all(
                r[f'tier_{preset}_2026'] == 'dirty'
                for r in dataset.records
                if r['aipac_udp_flag_2026'] is True and r['clean_2026'] is not None
            ),
        )
    # Corp-only members in the 120th (corp > 0, AIPAC == 0, UDP == 0)
    # and how many stay dirty under each preset.
    corp_only = [
        r
        for r in r120
        if r['corp_2026'] > 0 and r['aipac_direct_2026'] == 0 and r['udp_benefit_2026'] == 0
    ]
    audit.pin('corp-only members in the 120th', 'tiered_2026.corp_only_2026_120th', len(corp_only))
    for preset in ('balanced', 'lenient'):
        staying = sum(
            1 for r in corp_only if corp_material(r['corp_2026'], r['total_receipts_2026'], preset)
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
    # 2028 primary targets under each preset: tier dirty among House
    # Democrats / Class 3 Senate Democrats in the 120th; Strict is
    # dirty_2026 > 0.
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
    for preset in ('balanced', 'lenient'):
        audit.pin(
            f'2028 targets {preset} House',
            f'tiered_2026.targets_2028_{preset}_house',
            sum(1 for r in house_dem if r[f'tier_{preset}_2026'] == 'dirty'),
        )
        audit.pin(
            f'2028 targets {preset} Senate Class 3',
            f'tiered_2026.targets_2028_{preset}_senate_class3',
            sum(1 for r in sen3_dem if r[f'tier_{preset}_2026'] == 'dirty'),
        )
    # Members whose tier turns on a net-negative AIPAC component (refunds).
    spot_fields = (
        'clean_2026',
        'corp_2026',
        'aipac_direct_2026',
        'dirty_2026',
        'aipac_udp_flag_2026',
        'tier_balanced_2026',
        'tier_lenient_2026',
    )
    for slug, name in (
        ('ryan', 'Patrick Ryan'),
        ('randall', 'Emily Randall'),
        ('garcia', 'Sylvia R. Garcia'),
    ):
        rec = next(r for r in dataset.records if r['full_name'] == name)
        audit.pin(f'{name} tier spot case', f'spot.tier.{slug}', {f: rec[f] for f in spot_fields})

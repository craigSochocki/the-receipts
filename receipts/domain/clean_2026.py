"""Whether a member's 2026 campaign was clean, and how dirty under each preset."""

from dataclasses import dataclass

UNLINKED, UNOPPOSED = 'unlinked', 'unopposed'
NOT_DIRTY_TIERS = ('clean', 'below_threshold')


@dataclass(frozen=True)
class TolerancePreset:
    """How much corporate PAC money a preset tolerates before it counts as dirty."""

    corp_amount: int
    corp_share: float


UNLINKED_NOTE = (
    " | 2026 DATA GAP: no 2026 per-cycle data found under the roster's linked candidate ID "
    '(returning former member; 2026 committee ID not linked) — clean_2026=True reflects '
    'absence of data, NOT verified zero fundraising; do not present as confirmed clean.'
    ' | 2026 clean status UNVERIFIED — no 2026 per-cycle data under linked candidate ID '
    '(returning former member; 2026 committee ID not linked). '
    'Not counted as verified-clean.'
)
UNOPPOSED_NOTE = (
    ' | 2026 clean status UNOPPOSED — ran unopposed in 2026 ({race}): '
    'no opponent with receipts over $0, so $0 dirty money reflects no contest, '
    'not a verified-clean campaign. Not counted as verified-clean.'
)
NO_INDIVIDUAL_MONEY_NOTE = (
    ' | 2026 DATA GAP: corporate PAC ${corp} in 2026 but $0 individual contributions — '
    'the $0 individual figure is a likely missing-committee-linkage gap, not a real zero; '
    'do not present as $0 raised from individuals.'
)


def races_and_unopposed(candidate_ids, race_map, race_of):
    """A person's 2026 races, and those with no opponent who raised money."""
    ids = set(candidate_ids)
    races = sorted({race_of[c] for c in ids if c in race_of})
    unopposed = [
        race
        for race in races
        if not any(c not in ids and receipts > 0 for c, receipts in race_map.get(race, []))
    ]
    return races, unopposed


def race_label(race):
    office, state, district = race
    return f'{state} Senate' if office == 'S' else f'{state}-{district}'


def verdict(in_120th, linked, unopposed, dirty, flagged):
    """(clean_2026, why unknown): None without 2026 data or when unopposed; else net dirty <= 0 with no flagged money.

    The flag takes precedence over the net: a member who took any AIPAC
    direct or UDP benefit dollar is not clean even when refunds
    elsewhere make the net negative — corporate refunds cannot cancel
    AIPAC/UDP money. A flagged unopposed member stays dirty, not null.
    """
    if in_120th and not linked:
        return None, UNLINKED
    if unopposed and dirty <= 0 and not flagged:
        return None, UNOPPOSED
    return dirty <= 0 and not flagged, None


CAREER_DIRTY_COLUMNS = (
    'corporate_pac_career',
    'aipac_pac_direct_career',
    'udp_ie_support_career',
    'udp_ie_opposing_opponents_career',
)


def is_career_clean(person):
    """No career dirty money: corporate PAC, AIPAC direct, UDP support and opposition credit all 0."""
    return all(person[column] == 0 for column in CAREER_DIRTY_COLUMNS)


def is_not_dirty(tier_name):
    """Clean or below threshold under a preset: the page's "not dirty"."""
    return tier_name in NOT_DIRTY_TIERS


def aipac_udp_flagged(aipac_direct, udp_benefit):
    """Any AIPAC PAC direct or UDP benefit dollar in 2026 makes a member dirty under every preset."""
    return aipac_direct > 0 or udp_benefit > 0


def corporate_money_material(corporate, total_receipts, preset):
    """Corporate PAC money is dirty under a preset only above both of its thresholds."""
    if corporate <= preset.corp_amount:
        return False
    if isinstance(total_receipts, bool) or not isinstance(total_receipts, int | float):
        return False
    return total_receipts > 0 and corporate / total_receipts > preset.corp_share


def tier(clean, flagged, corporate, total_receipts, preset):
    """'dirty', 'below_threshold' or 'clean' under a preset; None exactly where clean is."""
    if clean is None:
        return None
    if flagged or corporate_money_material(corporate, total_receipts, preset):
        return 'dirty'
    return 'below_threshold' if corporate > 0 else 'clean'

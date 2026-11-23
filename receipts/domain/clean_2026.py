"""Whether a member's 2026 campaign was clean, and how dirty under each tolerance preset.

Methodology §14. Dirty money is corporate PAC + AIPAC PAC direct + UDP
benefit; individual contributions never are. Clean means no NET dirty
money in 2026, judged only where there is 2026 data to judge and the race
was contested.
"""

UNLINKED, UNOPPOSED = 'unlinked', 'unopposed'

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
    """The races behind a person's 2026 candidate IDs, and those with no funded opponent.

    A filed opponent with $0 receipts does not contest a race.
    """
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


def verdict(in_120th, linked, unopposed, dirty):
    """(clean_2026, why it is unknown). Unknown (None) without 2026 data, or when unopposed
    and otherwise clean; else clean exactly when net dirty money is at most zero."""
    if in_120th and not linked:
        return None, UNLINKED
    if unopposed and dirty <= 0:
        return None, UNOPPOSED
    return dirty <= 0, None


def corporate_money_material(corporate, total_receipts, preset):
    """Corporate PAC money counts as dirty under a preset only above BOTH its dollar and its
    share-of-receipts thresholds; with no positive receipts the share is undefined."""
    if corporate <= preset['corp_amount']:
        return False
    if isinstance(total_receipts, bool) or not isinstance(total_receipts, int | float):
        return False
    return total_receipts > 0 and corporate / total_receipts > preset['corp_share']


def tier(clean, flagged, corporate, total_receipts, preset):
    """'dirty', 'below_threshold' or 'clean' under a preset; None exactly where clean is."""
    if clean is None:
        return None
    if flagged or corporate_money_material(corporate, total_receipts, preset):
        return 'dirty'
    return 'below_threshold' if corporate > 0 else 'clean'

"""A member's term: their latest election's cycle and every cycle since, as one record."""

from receipts.domain.clean_2026 import aipac_udp_flagged

NOT_SUMMED = (
    'cycle',
    'clean',
    'unopposed',
    'aipac_udp_flag',
    'tier_balanced',
    'tier_lenient',
    'dep_share',
    'cash_on_hand',
    'up_for_election',
)


def term_record(cycles, first):
    """Money summed from cycle `first` on; shares and flags from the sums; the election's race."""
    since = sorted((c for c in cycles if c['cycle'] >= first), key=lambda c: c['cycle'])
    term = {k: round(sum(c[k] or 0 for c in since), 2) for k in since[0] if k not in NOT_SUMMED}
    accepted = term['individual'] + term['corp'] + term['aipac_direct']
    dependent = term['corp'] + term['aipac_direct']
    return {
        **term,
        'cycle': first,
        'unopposed': since[0]['unopposed'],
        'cash_on_hand': since[-1]['cash_on_hand'],
        'dep_share': round(dependent / accepted, 4) if accepted > 0 else None,
        'aipac_udp_flag': aipac_udp_flagged(term['aipac_direct'], term['udp_benefit']),
    }

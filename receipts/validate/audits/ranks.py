"""Every rank column recomputed, and the career dirty-money column."""

from receipts.validate.audits.published import competition_ranks, is_num


def ranks_and_dirty(audit, dataset):
    """(c) rank columns recompute exactly"""
    rank_defs = [
        ('rank_total_accepted', 'total_accepted_career'),
        ('rank_individual', 'individual_contribution_total_career'),
        ('rank_corporate_pac', 'corporate_pac_career'),
        ('rank_aipac_direct', 'aipac_pac_direct_career'),
        ('rank_udp_support', 'udp_ie_support_career'),
        ('rank_udp_opposing_opponents', 'udp_ie_opposing_opponents_career'),
        ('rank_udp_total_benefit', 'udp_ie_total_benefit_career'),
        ('rank_self_funding', 'self_funding_career'),
        ('rank_all_ie_support', 'all_ie_support_career'),
        ('rank_all_ie_oppose', 'all_ie_oppose_career'),
        ('rank_all_ie_total', 'all_ie_total_career'),
        ('rank_other_committees_total', 'other_committees_total_career'),
    ]
    # total_accepted itself
    ta_mism = sum(
        1
        for r in dataset.with_known_money
        if round(
            r['individual_contribution_total_career']
            + r['corporate_pac_career']
            + r['aipac_pac_direct_career'],
            2,
        )
        != r['total_accepted_career']
    )
    audit.check('total_accepted recomputes exactly', ta_mism == 0, f'{ta_mism} mismatches')
    # (c2) dirty_career recomputes exactly: corporate PAC + AIPAC
    # direct + UDP total benefit, career. Null only for Armstrong
    # (money unknown, not zero).
    dc_mism = 0
    for r in dataset.records:
        parts = [
            r['corporate_pac_career'],
            r['aipac_pac_direct_career'],
            r['udp_ie_total_benefit_career'],
        ]
        want = round(sum(parts), 2) if all(is_num(v) for v in parts) else None
        if r['dirty_career'] != want:
            dc_mism += 1
    audit.check(
        'dirty_career recomputes exactly (corp + AIPAC + UDP benefit)',
        dc_mism == 0,
        f'{dc_mism} mismatches',
    )
    audit.check(
        'dirty_career is null only for Armstrong',
        [r['person_key'] for r in dataset.records if r['dirty_career'] is None] == ['A000383'],
    )
    top_dirty = max(
        (r for r in dataset.records if is_num(r['dirty_career'])), key=lambda r: r['dirty_career']
    )
    audit.pin(
        'career dirty #1 (person, amount)',
        'spot.dirty_career_top',
        [top_dirty['person_key'], top_dirty['dirty_career']],
    )
    for rank_col, val_col in rank_defs:
        ranks = competition_ranks(dataset.records, val_col)
        mism = sum(1 for r in dataset.records if r[rank_col] != ranks[r['person_key']])
        audit.check(f'{rank_col} recomputes exactly', mism == 0, f'{mism} mismatches')

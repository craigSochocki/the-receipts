"""Every 2026 column, the clean verdict and dep_share, recomputed row by row."""

from receipts.common.settings import settings
from receipts.domain.clean_2026 import aipac_udp_flagged, races_and_unopposed, tier, verdict
from receipts.transform.compute_2026 import has_2026_linkage
from receipts.validate.audits.published import cycle_sum, load_weball_2026_races, opposition_credit

OTHER_COMMITTEE_BUCKETS = [
    'party_committees',
    'leadership_pacs',
    'labor_pacs',
    'trade_pacs',
    'membership_pacs',
    'cooperative_pacs',
    'other_unclassified',
]


def current_entries(entries):
    return [e for e in entries if e['cycle'] == settings().cycles.current]


def expected_money_2026(r, credit):
    """Every 2026 money column, recomputed from the person's per-cycle lists."""
    expect = {
        'individual_2026': cycle_sum(r['per_cycle'], 'individual'),
        'corp_2026': cycle_sum(r['per_cycle'], 'corporate_pac'),
        'aipac_direct_2026': cycle_sum(r['per_cycle'], 'aipac_pac_direct'),
        'udp_support_2026': cycle_sum(r['udp_per_cycle'], 'udp_ie_support'),
        'udp_opp_credit_2026': credit,
    }
    expect['udp_benefit_2026'] = round(expect['udp_support_2026'] + credit, 2)
    expect['dirty_2026'] = round(
        expect['corp_2026'] + expect['aipac_direct_2026'] + expect['udp_benefit_2026'], 2
    )
    denom = expect['individual_2026'] + expect['corp_2026'] + expect['aipac_direct_2026']
    expect['dep_share_2026'] = (
        round((expect['corp_2026'] + expect['aipac_direct_2026']) / denom, 4) if denom > 0 else None
    )
    sf, sf26 = r['self_funding_per_cycle'], current_entries(r['self_funding_per_cycle'])
    expect['self_funding_2026'] = (
        round(sum(e['candidate_contributions'] + e['candidate_loans'] for e in sf26), 2)
        if sf26
        else 0
    )
    expect['cand_loans_2026'] = cycle_sum(sf, 'candidate_loans')
    expect['cand_contrib_2026'] = cycle_sum(sf, 'candidate_contributions')
    expect['total_receipts_2026'] = cycle_sum(sf, 'total_receipts')
    expect['total_disbursements_2026'] = cycle_sum(sf, 'total_disbursements')
    expect['cash_on_hand_2026'] = round(sum(e['cash_on_hand'] for e in sf26), 2) if sf26 else None
    oc26 = current_entries(r['other_committees_per_cycle'])
    expect['other_committees_total_2026'] = (
        round(sum(sum(e[b] for b in OTHER_COMMITTEE_BUCKETS) for e in oc26), 2) if oc26 else 0
    )
    for direction in ('support', 'oppose', 'total'):
        field = f'all_ie_{direction}'
        expect[f'{field}_2026'] = cycle_sum(r['all_ie_per_cycle'], field)
    return expect


def is_unopposed(r, race_map, race_of):
    races, unopposed = races_and_unopposed(r['fec_candidate_ids'] or [], race_map, race_of)
    return bool(races) and len(unopposed) == len(races)


def expected_verdict(r, money, unopposed):
    """The AIPAC/UDP flag, the net clean verdict and both tolerance tiers."""
    flag = aipac_udp_flagged(money['aipac_direct_2026'], money['udp_benefit_2026'])
    linked = has_2026_linkage(r)
    clean, _ = verdict(r['in_120th'] == 'yes', linked, unopposed, money['dirty_2026'])
    presets = settings().verification.tolerance_presets
    return {
        'unopposed_2026': unopposed,
        'aipac_udp_flag_2026': flag,
        'clean_2026': clean,
        **{
            f'tier_{p}_2026': tier(
                clean, flag, money['corp_2026'], money['total_receipts_2026'], presets[p]
            )
            for p in ('balanced', 'lenient')
        },
    }


def columns_2026(audit, dataset):
    """(e) 2026 columns, clean rule, dep_share"""
    race_map, by_cid = load_weball_2026_races()
    credit_2026 = opposition_credit(cycle=settings().cycles.current)
    mism = 0
    for r in dataset.records:
        money = expected_money_2026(r, credit_2026.get(r['person_key'], 0.0))
        expect = {**money, **expected_verdict(r, money, is_unopposed(r, race_map, by_cid))}
        for k, v in expect.items():
            if r[k] != v:
                mism += 1
                if mism <= 5:
                    print(f'  2026 mismatch {r["person_key"]} {k}: {r[k]!r} != {v!r}')
    audit.check(
        '2026 columns + clean rule + dep_share recompute exactly', mism == 0, f'{mism} mismatches'
    )

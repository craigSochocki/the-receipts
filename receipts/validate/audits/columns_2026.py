"""Every 2026 column, the clean verdict and dep_share, recomputed row by row."""

from receipts.common.settings import settings
from receipts.validate.audits.published import cycle_sum, load_weball_2026_races, opposition_credit
from receipts.validate.audits.tiers import flag_for, tier_for


def columns_2026(audit, dataset):
    """(e) 2026 columns, clean rule, dep_share"""
    race_map, by_cid = load_weball_2026_races()
    credit_2026 = opposition_credit(cycle=settings().cycles.current)
    oc_buckets_e = [
        'party_committees',
        'leadership_pacs',
        'labor_pacs',
        'trade_pacs',
        'membership_pacs',
        'cooperative_pacs',
        'other_unclassified',
    ]
    mism = 0
    for r in dataset.records:
        expect = {
            'individual_2026': cycle_sum(r['per_cycle'], 'individual'),
            'corp_2026': cycle_sum(r['per_cycle'], 'corporate_pac'),
            'aipac_direct_2026': cycle_sum(r['per_cycle'], 'aipac_pac_direct'),
            'udp_support_2026': cycle_sum(r['udp_per_cycle'], 'udp_ie_support'),
            'udp_opp_credit_2026': credit_2026.get(r['person_key'], 0.0),
        }
        expect['udp_benefit_2026'] = round(
            expect['udp_support_2026'] + expect['udp_opp_credit_2026'], 2
        )
        expect['dirty_2026'] = round(
            expect['corp_2026'] + expect['aipac_direct_2026'] + expect['udp_benefit_2026'], 2
        )
        denom = expect['individual_2026'] + expect['corp_2026'] + expect['aipac_direct_2026']
        expect['dep_share_2026'] = (
            round((expect['corp_2026'] + expect['aipac_direct_2026']) / denom, 4)
            if denom > 0
            else None
        )
        sf26 = [e for e in r['self_funding_per_cycle'] if e['cycle'] == settings().cycles.current]
        expect['self_funding_2026'] = (
            round(sum(e['candidate_contributions'] + e['candidate_loans'] for e in sf26), 2)
            if sf26
            else 0
        )
        expect['cand_loans_2026'] = cycle_sum(r['self_funding_per_cycle'], 'candidate_loans')
        expect['cand_contrib_2026'] = cycle_sum(
            r['self_funding_per_cycle'], 'candidate_contributions'
        )
        expect['total_receipts_2026'] = cycle_sum(r['self_funding_per_cycle'], 'total_receipts')
        expect['total_disbursements_2026'] = cycle_sum(
            r['self_funding_per_cycle'], 'total_disbursements'
        )
        expect['cash_on_hand_2026'] = (
            round(sum(e['cash_on_hand'] for e in sf26), 2) if sf26 else None
        )
        oc26 = [
            e for e in r['other_committees_per_cycle'] if e['cycle'] == settings().cycles.current
        ]
        expect['other_committees_total_2026'] = (
            round(sum(sum(e[b] for b in oc_buckets_e) for e in oc26), 2) if oc26 else 0
        )
        expect['all_ie_support_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_support')
        expect['all_ie_oppose_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_oppose')
        expect['all_ie_total_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_total')
        # Generalized linkage rule (see compute_2026.py): a tracked/UDP
        # 2026 entry, or a self-funding 2026 entry whose coverage end
        # date falls in calendar 2026.
        has_linkage = (
            any(e['cycle'] == settings().cycles.current for e in r['per_cycle'])
            or any(e['cycle'] == settings().cycles.current for e in r['udp_per_cycle'])
            or any(
                e['cycle'] == settings().cycles.current
                and str(e.get('coverage_end_date', '')).endswith('/2026')
                for e in r['self_funding_per_cycle']
            )
        )
        # Unopposed rule (see compute_2026.py): every 2026 race the
        # person filed in has no OTHER candidate with receipts over $0.
        # False when they filed no 2026 candidacy at all.
        ids = set(r['fec_candidate_ids'] or [])
        races = sorted({by_cid[cid] for cid in ids if cid in by_cid})
        expect['unopposed_2026'] = bool(races) and all(
            not any(cid not in ids and receipts > 0 for cid, receipts in race_map.get(race, []))
            for race in races
        )
        expect['aipac_udp_flag_2026'] = flag_for(
            expect['aipac_direct_2026'], expect['udp_benefit_2026']
        )
        # Net-negative clean rule: no NET dirty money (dirty_2026 <= 0)
        # reads clean; the unopposed test is the same net test.
        if (
            r['in_120th'] == 'yes'
            and not has_linkage
            or expect['unopposed_2026']
            and expect['dirty_2026'] <= 0
        ):
            expect['clean_2026'] = None
        else:
            expect['clean_2026'] = expect['dirty_2026'] <= 0
        # Tolerance tiers.
        for preset in ('balanced', 'lenient'):
            expect[f'tier_{preset}_2026'] = tier_for(
                expect['clean_2026'],
                expect['aipac_udp_flag_2026'],
                expect['corp_2026'],
                expect['total_receipts_2026'],
                preset,
            )
        for k, v in expect.items():
            if r[k] != v:
                mism += 1
                if mism <= 5:
                    print(f'  2026 mismatch {r["person_key"]} {k}: {r[k]!r} != {v!r}')
    audit.check(
        '2026 columns + clean rule + dep_share recompute exactly', mism == 0, f'{mism} mismatches'
    )

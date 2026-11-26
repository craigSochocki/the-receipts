"""Flag and clean counts under both JFC variants, from the square-one derivation.

The committed dataset holds the Variant A figures, so Variant A must
reproduce the committed counts exactly (cycle flag 258, Strict clean 81,
Balanced not-dirty 189, Lenient 234; term flag 299, Strict clean 77,
Balanced 170, Lenient 203). The baseline variant must reproduce the
recount's baseline counts (cycle flag 231, Strict clean 83, Balanced
not-dirty 201, Lenient 253; term flag 270, Strict clean 79, Balanced 183,
Lenient 224). Variants A and B must reproduce the JFC recount's counts.
Ryan stays null and unflagged under every variant: his committee maps to
an unlinked candidate ID, so the API money is unattributed.
"""

import json
from pathlib import Path

from receipts.square_one import (
    conduit,
    counts,
    ie,
    money,
    opposition,
    roster,
    variants,
)

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / 'data' / 'raw'
EVIDENCE = ROOT / 'data' / 'evidence' / 'jfc-variants'
SQUARE_ONE = ROOT / 'data' / 'evidence' / 'square-one'
JFC_DIR = ROOT / 'data' / 'source'
AIPAC = 'C00797670'
UDP = 'C00799031'
OVERRIDES = {'C00003251': 'labor', 'C00468314': 'other_unclassified'}
CAREER = list(range(1980, 2027, 2))
IE_CYCLES = [2022, 2024, 2026]
RECOUNT = json.loads((JFC_DIR / 'recount_results.json').read_text())


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def _assemble():
    """Every derivation input the counts need, from the pinned snapshot and evidence."""
    people = roster.load_roster(ROOT / 'congress-money-tracker.json')
    weball = money.derive_weball(BULK, CAREER)
    records = roster.load_dedup_applied(ROOT / 'data' / 'source' / 'dedup-applied.json')
    assert money.check_dedup_record(weball, records) == []
    adjusted, _differing = money.apply_dedup(weball, records)
    committee_money, _stats = money.derive_committee_money(BULK, CAREER, AIPAC, OVERRIDES)
    rollup = money.rollup_person_cycle(adjusted, committee_money, people, CAREER)

    person_of = roster.person_of(people)
    surnames = conduit.person_surnames(people)
    cm_by_cycle, cm_multi_by_cycle = {}, {}
    for cycle in IE_CYCLES:
        cm_by_cycle[cycle], cm_multi_by_cycle[cycle] = conduit.load_cm_maps(BULK, cycle)
    pas2_names = conduit.build_pas2_name_map(BULK, [2024, 2026])
    committees = conduit.listed_committees(ROOT / 'data' / 'source' / 'pro_israel_pacs.csv')
    resolutions = _load_json(JFC_DIR / 'collision_resolutions.json')
    direct, report = conduit.direct_from_by_recipient(
        EVIDENCE,
        committees,
        IE_CYCLES,
        cm_by_cycle,
        cm_multi_by_cycle,
        pas2_names,
        person_of,
        surnames,
        resolutions,
    )
    fixes = _load_json(SQUARE_ONE / 'collision_fixes.json')['fixes']
    conduit.apply_collision_fixes(direct, fixes, report['resolved_keys'])
    jfc = variants.combine_jfc(
        JFC_DIR / 'jfc_attribution4.json', JFC_DIR / 'jfc_outflow_shares4.json'
    )
    corrected = variants.corrected_figures(direct, jfc)

    ie_rows, _stats = ie.derive_ie(BULK, IE_CYCLES, people, adjusted)
    ie_by_candidate = ie.per_candidate_cycle(ie_rows)
    # UDP support + opposition credit: blank candidate IDs resolved by
    # name on the UDP rows only, the pipeline's method (all-IE leaves
    # blank IDs unidentified and excludes them).
    udp_rows = [r for r in ie_rows if r.spender_id == UDP]
    ie.resolve_blank_ids(udp_rows, people)
    udp_by_candidate = ie.per_candidate_cycle(udp_rows)
    opp_credits, _nonroster, _uncredited = opposition.opposition_credits(udp_rows, person_of)
    udp_support: dict[tuple, int] = {}
    all_ie: dict[tuple, tuple[int, int, int]] = {}
    for person in people:
        key = person['person_key']
        ids = set(person['fec_candidate_ids'])
        for cycle in IE_CYCLES:
            udp_support[(key, cycle)] = sum(
                cents[0]
                for (cid, cy), cents in udp_by_candidate.items()
                if cy == cycle and cid in ids
            )
            support = sum(
                cents[0]
                for (cid, cy), cents in ie_by_candidate.items()
                if cy == cycle and cid in ids
            )
            oppose = sum(
                cents[1]
                for (cid, cy), cents in ie_by_candidate.items()
                if cy == cycle and cid in ids
            )
            total = sum(
                cents[2]
                for (cid, cy), cents in ie_by_candidate.items()
                if cy == cycle and cid in ids
            )
            all_ie[(key, cycle)] = (support, oppose, total)
    filed = counts.build_filed(BULK)
    races_for = counts.build_races_getter(BULK)
    return {
        'people': people,
        'rollup': rollup,
        'weball': adjusted,
        'weball_filed': weball,
        'committee_money': committee_money,
        'corrected': corrected,
        'udp_support': udp_support,
        'all_ie': all_ie,
        'opp_credits': opp_credits,
        'filed': filed,
        'races_for': races_for,
    }


def _recount_counts(variant):
    rows = [v for v in RECOUNT[variant].values() if v['in_120']]

    def cnt(key, val):
        return sum(1 for v in rows if v[key] == val)

    def not_dirty(key):
        return sum(1 for v in rows if v[key] in ('clean', 'below_threshold'))

    return {
        'n': len(rows),
        'c26_flag': cnt('c26_flag', True),
        'c26_strict_clean': cnt('c26_clean', True),
        'c26_null': cnt('c26_clean', None),
        'c26_bal_notdirty': not_dirty('c26_tier_balanced'),
        'c26_len_notdirty': not_dirty('c26_tier_lenient'),
        'term_flag': cnt('term_flag', True),
        'term_strict_clean': cnt('term_clean', True),
        'term_null': cnt('term_clean', None),
        'term_bal_notdirty': not_dirty('term_tier_balanced'),
        'term_len_notdirty': not_dirty('term_tier_lenient'),
        # House-120th career-clean is 58 in the baseline; the JFC report
        # finds only Zinke flips it, and he is 119th-only.
        'house_120th_career_clean': 58,
    }


def test_counts_reproduce_recount_under_all_variants():
    data = _assemble()
    edges = {
        'baseline': [],
        'A': [('J000310', 2026), ('Z000018', 2026)],
        'B': [('J000310', 2026)],
    }
    for variant in ('baseline', 'A', 'B'):
        results, got = counts.run_variant(
            data['people'],
            data['rollup'],
            data['weball'],
            data['weball_filed'],
            data['committee_money'],
            data['corrected'] if variant != 'baseline' else None,
            variant,
            data['udp_support'],
            data['all_ie'],
            data['opp_credits'],
            data['races_for'],
            data['filed'],
        )
        assert got == _recount_counts(variant), (variant, got)
        got_edges = sorted((v['person_key'], cycle) for v in results for cycle in v['edge_cycles'])
        assert got_edges == edges[variant], (variant, got_edges)


def test_ryan_stays_null_and_unflagged_under_both_variants():
    data = _assemble()
    for variant in ('A', 'B'):
        results, _got = counts.run_variant(
            data['people'],
            data['rollup'],
            data['weball'],
            data['weball_filed'],
            data['committee_money'],
            data['corrected'],
            variant,
            data['udp_support'],
            data['all_ie'],
            data['opp_credits'],
            data['races_for'],
            data['filed'],
        )
        ryan = next(v for v in results if v['person_key'] == 'R000600')
        assert ryan['c26']['aipac_direct'] == 0.0
        assert ryan['c26']['aipac_udp_flag'] is False
        assert ryan['c26']['clean'] is None
        assert ryan['headline']['clean'] is None
        assert ryan['term']['aipac_udp_flag'] is False


def test_cycle_records_match_dataset_for_spot_members():
    # The committed dataset holds the Variant A figures, so the
    # derivation's Variant A records must match it cycle by cycle.
    data = _assemble()
    results, _got = counts.run_variant(
        data['people'],
        data['rollup'],
        data['weball'],
        data['weball_filed'],
        data['committee_money'],
        data['corrected'],
        'A',
        data['udp_support'],
        data['all_ie'],
        data['opp_credits'],
        data['races_for'],
        data['filed'],
    )
    dataset = {row['person_key']: row for row in _load_json(ROOT / 'congress-money-tracker.json')}
    for person_key in ('B001324', 'J000305', 'R000600', 'S001215'):
        mine = next(v for v in results if v['person_key'] == person_key)
        theirs = dataset[person_key]
        mine_by_cycle = {c['cycle']: c for c in mine['cycles']}
        theirs_by_cycle = {c['cycle']: c for c in theirs['cycles']}
        assert set(mine_by_cycle) == set(theirs_by_cycle), (
            person_key,
            sorted(set(mine_by_cycle) ^ set(theirs_by_cycle)),
        )
        for cycle in (2022, 2024, 2026):
            if cycle not in theirs_by_cycle:
                continue
            mine_record = mine_by_cycle[cycle]
            theirs_record = theirs_by_cycle[cycle]
            for field in (
                'individual',
                'corp',
                'aipac_direct',
                'udp_support',
                'udp_benefit',
                'dirty',
                'clean',
                'unopposed',
                'aipac_udp_flag',
                'tier_balanced',
                'tier_lenient',
                'total_receipts',
                'cash_on_hand',
            ):
                assert mine_record[field] == theirs_record[field], (
                    person_key,
                    cycle,
                    field,
                    mine_record[field],
                    theirs_record[field],
                )

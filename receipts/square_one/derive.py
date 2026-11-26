"""Square-one derivation CLI: run every step and write the derived figures.

Usage:
    python3 -m receipts.square_one.derive [--root PATH] [--out PATH] [--smoke]

Writes data/intermediate/square_one/derived.json (gitignored): per-person
per-cycle corrected figures (both JFC variants), career totals, counts,
audit results, the transfer-dedup report, and the Ryan election-attributed
figure. The full run takes several minutes over the pinned snapshot;
--smoke runs the 2026 cycle only into a throwaway output, to check the
wiring. Config values (committee IDs, overrides, cycles) come from
config.yaml via settings(); the derivation core takes them as arguments.
"""

import argparse
import json
import time
from pathlib import Path

from receipts.common.settings import repo_root, settings
from receipts.square_one import (
    audits,
    conduit,
    counts,
    ie,
    money,
    opposition,
    parsers,
    roster,
    transfers,
    variants,
)

EVIDENCE = Path('data') / 'evidence'
JFC_DIR = Path('/home/hatch/workspace/tmp-jfc')
AUDIT_CYCLES = [2022, 2024, 2026]


def _overrides() -> dict:
    """Config class overrides, translated from bucket names to class names."""
    short = {bucket: kind for kind, bucket in counts.BUCKET_MAP.items()}
    short['other_unclassified'] = 'other_unclassified'
    return {cid: short[bucket] for cid, bucket in settings().committees.class_overrides.items()}


def _step(name: str, started: float) -> None:
    print(f'[{time.time() - started:6.1f}s] {name}', flush=True)


def derive_money(root, bulk, cycles, ie_cycles, aipac, overrides, started):
    """Roster, weball + dedup, committee money, transfer dedup."""
    _step('roster + weball', started)
    people = roster.load_roster(root / 'congress-money-tracker.json')
    weball = money.derive_weball(bulk, cycles)
    records = roster.load_dedup_applied(root / 'data' / 'source' / 'dedup-applied.json')
    records = [r for r in records if r['cycle'] in cycles]
    problems = money.check_dedup_record(weball, records)
    if problems:
        raise SystemExit(f'dedup record disagrees with weball: {problems[:5]}')
    adjusted, differing = money.apply_dedup(weball, records)

    _step('committee money', started)
    committee_money, cm_stats = money.derive_committee_money(bulk, cycles, aipac, overrides)
    rollup = money.rollup_person_cycle(adjusted, committee_money, people, cycles)

    _step('transfer dedup', started)
    principal = transfers.principal_committees(bulk, ie_cycles)
    offices = transfers.candidate_offices(bulk, ie_cycles)
    groups = transfers.shared_committee_groups(people, principal, offices)
    weball_transfers, transfer_report = transfers.apply_transfer_dedup(adjusted, groups, records)
    rollup_transfers = money.rollup_person_cycle(weball_transfers, committee_money, people, cycles)
    return {
        'people': people,
        'person_of': roster.person_of(people),
        'weball': weball,
        'adjusted': adjusted,
        'committee_money': committee_money,
        'rollup': rollup,
        'rollup_transfers': rollup_transfers,
        'transfer_report': transfer_report,
        'records': records,
        'differing': differing,
        'cm_stats': cm_stats,
    }


def derive_conduit(root, bulk, people, person_of, ie_cycles, started):
    """API conduit merge + JFC variants."""
    _step('conduit merge', started)
    surnames = conduit.person_surnames(people)
    cm_by_cycle, cm_multi_by_cycle = {}, {}
    for cycle in ie_cycles:
        cm_by_cycle[cycle], cm_multi_by_cycle[cycle] = conduit.load_cm_maps(bulk, cycle)
    pas2_names = conduit.build_pas2_name_map(bulk, [2024, 2026])
    committees = conduit.listed_committees(root / 'data' / 'source' / 'pro_israel_pacs.csv')
    resolutions = json.loads((JFC_DIR / 'collision_resolutions.json').read_text())
    direct, merge_report = conduit.direct_from_by_recipient(
        root / EVIDENCE / 'jfc-variants',
        committees,
        ie_cycles,
        cm_by_cycle,
        cm_multi_by_cycle,
        pas2_names,
        person_of,
        surnames,
        resolutions,
    )
    fixes = json.loads((root / EVIDENCE / 'square-one' / 'collision_fixes.json').read_text())[
        'fixes'
    ]
    conduit.apply_collision_fixes(direct, fixes, merge_report['resolved_keys'])
    jfc = variants.combine_jfc(
        JFC_DIR / 'jfc_attribution4.json', JFC_DIR / 'jfc_outflow_shares4.json'
    )
    return variants.corrected_figures(direct, jfc), merge_report


def derive_ie_data(bulk, people, adjusted, udp, person_of, ie_cycles, started):
    """IE rows: UDP support, all-IE per candidate, opposition credits."""
    _step('independent expenditures', started)
    ie_rows, ie_stats = ie.derive_ie(bulk, ie_cycles, people, adjusted)
    ie_by_candidate = ie.per_candidate_cycle(ie_rows)
    udp_rows = [r for r in ie_rows if r.spender_id == udp]
    ie.resolve_blank_ids(udp_rows, people)
    udp_by_candidate = ie.per_candidate_cycle(udp_rows)
    opp_credits, _nonroster, _uncredited = opposition.opposition_credits(udp_rows, person_of)
    udp_support: dict[tuple, int] = {}
    all_ie: dict[tuple, tuple[int, int, int]] = {}
    for person in people:
        key = person['person_key']
        ids = set(person['fec_candidate_ids'])
        for cycle in ie_cycles:
            udp_support[(key, cycle)] = sum(
                cents[0]
                for (cid, cy), cents in udp_by_candidate.items()
                if cy == cycle and cid in ids
            )
            all_ie[(key, cycle)] = tuple(
                sum(
                    cents[index]
                    for (cid, cy), cents in ie_by_candidate.items()
                    if cy == cycle and cid in ids
                )
                for index in (0, 1, 2)
            )
    return udp_support, all_ie, opp_credits, ie_stats


def derive_ryan(bulk, aipac, started):
    """Ryan's election-attributed refunds on the name-matched rows."""
    _step('Ryan election-attributed refunds', started)
    ryan_rows = [
        row
        for row in parsers.pas2_rows(bulk, 2026)
        if row.candidate_id == 'H8NY19223' and row.committee_id == aipac
    ]
    ryan_counted = [
        row
        for row in ryan_rows
        if row.transaction_type in ('24K', '24P') and not (row.is_earmark and row.amount_cents < 0)
    ]
    attributed = transfers.attribute_refunds_by_election(ryan_counted, 2026)
    net = sum(row.amount_cents for row in ryan_counted)
    return attributed, net


def derive_counts(money_data, corrected, udp_support, all_ie, opp_credits, bulk, cycles, started):
    """Flag and clean counts under the baseline and both JFC variants."""
    _step('counts', started)
    filed = counts.build_filed(bulk, cycles)
    races_for = counts.build_races_getter(bulk)
    all_counts = {}
    for variant in ('baseline', 'A', 'B'):
        _results, variant_counts = counts.run_variant(
            money_data['people'],
            money_data['rollup'],
            money_data['adjusted'],
            money_data['weball'],
            money_data['committee_money'],
            corrected if variant != 'baseline' else None,
            variant,
            udp_support,
            all_ie,
            opp_credits,
            races_for,
            filed,
        )
        all_counts[variant] = variant_counts
    return all_counts


def run(root: Path, out_path: Path, cycles: list[int], ie_cycles: list[int]) -> dict:
    """The full derivation. Returns the dict written to `out_path`."""
    started = time.time()
    bulk = root / 'data' / 'raw'
    aipac = settings().committees.aipac_pac
    udp = settings().committees.udp
    money_data = derive_money(root, bulk, cycles, ie_cycles, aipac, _overrides(), started)
    corrected, merge_report = derive_conduit(
        root, bulk, money_data['people'], money_data['person_of'], ie_cycles, started
    )
    udp_support, all_ie, opp_credits, ie_stats = derive_ie_data(
        bulk,
        money_data['people'],
        money_data['adjusted'],
        udp,
        money_data['person_of'],
        ie_cycles,
        started,
    )
    ryan_attributed, ryan_net = derive_ryan(bulk, aipac, started)
    all_counts = derive_counts(
        money_data, corrected, udp_support, all_ie, opp_credits, bulk, cycles, started
    )

    _step('audits', started)
    audit_results = audits.audit_no_zero_columns(
        corrected,
        ie_cycles,
        ['aipac_a_cents', 'aipac_b_cents', 'pro_israel_a_cents', 'pro_israel_b_cents'],
    )
    audit_results += audits.audit_live_spot_checks(
        {key: entry['aipac_b_cents'] for (key, cycle), entry in corrected.items() if cycle == 2026},
        root / EVIDENCE / 'square-one' / 'spot_checks.json',
    )
    audit_passed, audit_line = audits.run_all(audit_results)

    _step('writing output', started)
    # The career formula's pas2 base is read from the dataset here: the
    # money test proves the derivation reproduces those figures to the
    # cent from the bulk files, so the base is verified input, not a
    # shortcut around the derivation. The counts above use the rollup
    # directly and never touch the dataset.
    pas2_per_cycle, pas2_career = variants.load_pas2_base(root / 'congress-money-tracker.json')
    career = {
        person['person_key']: variants.corrected_career_for_person(
            corrected, pas2_per_cycle, pas2_career, person['person_key']
        )
        for person in money_data['people']
    }
    output = {
        'snapshot': settings().data_as_of,
        'counts': all_counts,
        'audits_passed': audit_passed,
        'audits_line': audit_line,
        'audit_results': audit_results,
        'career': career,
        'corrected_per_cycle': {
            f'{key}|{cycle}': entry for (key, cycle), entry in corrected.items()
        },
        'transfer_dedup': money_data['transfer_report'],
        'transfers_from_corrected': {
            f'{key}|{cycle}': entry['transfers_from_auth']
            for (key, cycle), entry in money_data['rollup_transfers'].items()
        },
        'ryan_election_attributed': {
            f'{cid}|{cycle}': cents for (cid, cycle), cents in ryan_attributed.items()
        },
        'ryan_pas2_net_2026_cents': ryan_net,
        'merge_report': {
            key: (sorted(value) if key == 'resolved_keys' else value)
            for key, value in merge_report.items()
            if key not in ('unmatched', 'ambiguous')
        },
        'merge_unmatched': merge_report['unmatched'],
        'merge_ambiguous': merge_report['ambiguous'],
        'cm_stats': money_data['cm_stats'],
        'ie_stats': ie_stats,
        'dedup_differing': money_data['differing'],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=1, sort_keys=True, default=str))
    _step(f'wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)', started)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=repo_root())
    parser.add_argument(
        '--out',
        type=Path,
        default=None,
        help='output path (default data/intermediate/square_one/derived.json)',
    )
    parser.add_argument('--smoke', action='store_true', help='2026 cycle only, for a wiring check')
    args = parser.parse_args()
    root = args.root
    out_path = args.out or root / 'data' / 'intermediate' / 'square_one' / 'derived.json'
    if args.smoke:
        cycles = [2026]
        ie_cycles = [2026]
    else:
        span = settings().cycles
        cycles = list(range(span.career_start, span.career_end + 1, 2))
        ie_cycles = list(span.udp)
    output = run(root, out_path, cycles, ie_cycles)
    print('counts:', json.dumps(output['counts'], indent=1))
    print('audits:', output['audits_line'])
    if not output['audits_passed']:
        raise SystemExit('audits failed')


if __name__ == '__main__':
    main()

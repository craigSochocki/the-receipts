"""Conduit merge: earmark rules and the by_recipient classifier, validated on evidence."""

import json
from pathlib import Path

from receipts.square_one import conduit, roster

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / 'data' / 'raw'
EVIDENCE = ROOT / 'data' / 'evidence' / 'jfc-variants'
SQUARE_ONE = ROOT / 'data' / 'evidence' / 'square-one'
JFC_DIR = Path('/home/hatch/workspace/tmp-jfc')


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def test_is_earmark_signals():
    assert conduit.is_earmark(
        'EARMARK OF LEV GRZHONKO. TRANSMITTED BY CHECK/EFT', None, 'EARMARK OF LEV GRZHONKO'
    )
    assert conduit.is_earmark(
        'VOID: REFUNDED EARMARK OF HOWARD WELINSKY', None, 'EARMARK OF HOWARD WELINSKY'
    )
    assert conduit.is_earmark('EARMARKED BY JANE DOE', None, 'CONDUIT CONTRIBUTION')
    assert conduit.is_earmark('', None, 'EARMARKED DONATIONS')
    assert conduit.is_earmark('', None, 'SMITH CONDUIT DONATION TO JONES FOR CONGRESS')
    assert conduit.is_earmark('', 'X', 'EARMARKED CONTRIBUTION ACTBLUE-SMITH, JANE')
    assert not conduit.is_earmark('', None, 'CONTRIBUTION TO COMMITTEE')
    assert not conduit.is_earmark('', None, 'PAC DONATION TO JONES FOR CONGRESS')
    assert not conduit.is_earmark('', None, 'DIRECT CAMPAIGN CONTRIBUTION')
    assert not conduit.is_earmark('', None, 'IN-KIND CONTRIBUTION MADE: POLLING')


def test_bell_2026_aipac_earmarks():
    rows = _load_json(SQUARE_ONE / 'schedb_aipac_to_bell_2026.json')
    summary = conduit.summarize_schedule_b(rows)
    assert summary['line23_rows'] == 2180
    assert summary['earmark_gross_cents'] == 229364458
    assert summary['earmark_void_cents'] == -168116
    assert summary['earmark_net_cents'] == 229196342
    assert summary['own_money_cents'] == 1000000
    assert summary['total_cents'] == 230196342  # API total; merged with pas2 is $2,303,644.58


def test_fetterman_conduit_spot_checks():
    jstreet_2022 = _load_json(SQUARE_ONE / 'schedb_jstreet_to_fetterman_2022_C00765800.json')
    assert conduit.summarize_schedule_b(jstreet_2022)['earmark_net_cents'] == 21462526
    jstreet_2024 = _load_json(SQUARE_ONE / 'schedb_jstreet_to_fetterman_2024_C00765800.json')
    assert conduit.summarize_schedule_b(jstreet_2024)['earmark_net_cents'] == 138600
    jacpac_2022 = _load_json(SQUARE_ONE / 'schedb_jacpac_to_fetterman_2022_C00765800.json')
    summary = conduit.summarize_schedule_b(jacpac_2022)
    assert summary['earmark_net_cents'] == 1075700
    assert summary['own_money_cents'] == 750000
    norpac_2026 = _load_json(SQUARE_ONE / 'schedb_norpac_2026.json')
    victory = [
        r
        for r in norpac_2026
        if (r.get('beneficiary_committee_name') or '') == 'FETTERMAN VICTORY FUND'
    ]
    assert len(victory) == 1
    assert victory[0]['recipient_committee_id'] == 'C00815134'
    assert conduit.summarize_schedule_b(victory)['earmark_net_cents'] == 2500000


def test_classifier_reproduces_per_person_api3():
    """The classifier + collision resolutions reproduce the JFC agent's direct figures."""
    people = roster.load_roster(ROOT / 'congress-money-tracker.json')
    cand_to_person = roster.person_of(people)
    surnames = conduit.person_surnames(people)
    cm_by_cycle = {}
    cm_multi_by_cycle = {}
    for cycle in (2022, 2024, 2026):
        cm_by_cycle[cycle], cm_multi_by_cycle[cycle] = conduit.load_cm_maps(BULK, cycle)
    pas2_names = conduit.build_pas2_name_map(BULK, [2024, 2026])
    committees = conduit.listed_committees(ROOT / 'data' / 'source' / 'pro_israel_pacs.csv')
    resolutions = _load_json(JFC_DIR / 'collision_resolutions.json')
    direct, report = conduit.direct_from_by_recipient(
        EVIDENCE,
        committees,
        [2022, 2024, 2026],
        cm_by_cycle,
        cm_multi_by_cycle,
        pas2_names,
        cand_to_person,
        surnames,
        resolutions,
    )
    # The collision fix moves $1,149,551.63 that the last-wins classifier
    # had put in the wrong bucket: fixed figures minus the pre-fix v3 file.
    fixed = _load_json(JFC_DIR / 'per_person_api3.json')
    v3 = _load_json(JFC_DIR / 'per_person_api3.json.v3.json')
    moved_cents = sum(
        round((dollars - v3.get(person_key, {}).get(key, 0.0)) * 100)
        for person_key, values in fixed.items()
        for key, dollars in values.items()
        if round((dollars - v3.get(person_key, {}).get(key, 0.0)) * 100) > 0
    )
    assert moved_cents == 114955163
    fixes = _load_json(SQUARE_ONE / 'collision_fixes.json')['fixes']
    # Only the three AIPAC Vargas fixes apply: every other fix's row
    # already has a resolution (the resolution moved that money).
    assert conduit.apply_collision_fixes(direct, fixes, report['resolved_keys']) == 35155999
    # Every ambiguous row left without a resolution touches no roster
    # person (or is $0), or is covered by a Schedule B-verified fix:
    # nothing attributable is dropped silently.
    fix_people = {(fix['committee'], int(fix['cycle']), fix['person_key']) for fix in fixes}
    for committee, cycle, name, cents in report['ambiguous']:
        cands = {c for _, _, c, _ in cm_multi_by_cycle[cycle].get(conduit.norm_name(name), []) if c}
        persons = {cand_to_person.get(c) for c in cands}
        covered_by_fix = any(
            (committee, cycle, person) in fix_people for person in persons if person
        )
        assert persons <= {None} or cents == 0 or covered_by_fix, (
            committee,
            cycle,
            name,
            cents,
            persons,
        )

    expected = fixed
    expected_direct = {}
    for person_key, values in expected.items():
        for key, dollars in values.items():
            committee, cycle, _kind = key.rsplit('_', 2)
            expected_direct[(person_key, committee, int(cycle))] = round(dollars * 100)
    assert set(direct) == set(expected_direct), (
        'only-in-mine',
        sorted(set(direct) - set(expected_direct))[:5],
        'only-in-expected',
        sorted(set(expected_direct) - set(direct))[:5],
    )
    mismatches = [
        (key, direct[key], expected_direct[key])
        for key in expected_direct
        if direct[key] != expected_direct[key]
    ]
    assert mismatches == [], mismatches[:10]

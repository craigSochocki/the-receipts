"""JFC variants: recombination matches the pilot, and the corrected career totals match the report."""

import json
from pathlib import Path

from receipts.square_one import conduit, roster, variants

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / 'data' / 'raw'
EVIDENCE = ROOT / 'data' / 'evidence' / 'jfc-variants'
SQUARE_ONE = ROOT / 'data' / 'evidence' / 'square-one'
JFC_DIR = ROOT / 'data' / 'source'


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def _direct_figures():
    """The conduit direct derivation, as in the conduit test."""
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
    fixes = _load_json(SQUARE_ONE / 'collision_fixes.json')['fixes']
    conduit.apply_collision_fixes(direct, fixes, report['resolved_keys'])
    return people, direct


def test_combine_jfc_reproduces_pilot():
    mine = variants.combine_jfc(
        JFC_DIR / 'jfc_attribution4.json', JFC_DIR / 'jfc_outflow_shares4.json'
    )
    expected = _load_json(JFC_DIR / 'jfc_per_person.json')
    assert set(mine) == set(expected)
    worst = 0
    for person_key, cycles in expected.items():
        for cycle, values in cycles.items():
            for field in ('aipac', 'other'):
                diff = abs(mine[person_key][int(cycle)][field] - round(values[field] * 100))
                worst = max(worst, diff)
    assert worst <= 1, worst


def test_corrected_career_totals_match_jfc_report():
    people, direct = _direct_figures()
    jfc = variants.combine_jfc(
        JFC_DIR / 'jfc_attribution4.json', JFC_DIR / 'jfc_outflow_shares4.json'
    )
    figures = variants.corrected_figures(direct, jfc)
    seated = {p['person_key'] for p in people if p.get('chamber_120')}
    pas2_per_cycle, pas2_career = variants.load_pas2_base(ROOT / 'congress-money-tracker.json')
    totals = variants.corrected_career_totals(figures, pas2_per_cycle, pas2_career, seated)
    # JFC variants report, the 535 seated in the 120th, career 2022+2024+2026.
    assert totals['aipac_a_cents'] == 8185005624
    assert totals['aipac_b_cents'] == 8128542483
    assert totals['pro_israel_a_cents'] == 11316401418
    assert totals['pro_israel_b_cents'] == 10951984964

    # Spot cases from the report: Jeffries, Collins, Fetterman career JFC.
    def career_jfc(person_key):
        return (
            sum(v['aipac'] for v in jfc.get(person_key, {}).values()),
            sum(v['other'] for v in jfc.get(person_key, {}).values()),
        )

    jeffries = [p for p in people if p['full_name'].startswith('Hakeem')][0]
    aipac_jfc, other_jfc = career_jfc(jeffries['person_key'])
    assert aipac_jfc == 49065000
    assert aipac_jfc + other_jfc == 57795000
    collins = [p for p in people if p['full_name'].startswith('Susan M. Collins')][0]
    aipac_jfc, other_jfc = career_jfc(collins['person_key'])
    assert aipac_jfc + other_jfc == 9060632
    fetterman = [p for p in people if p['full_name'].startswith('John Fetterman')][0]
    aipac_jfc, other_jfc = career_jfc(fetterman['person_key'])
    assert aipac_jfc == 0
    assert other_jfc == 2550000

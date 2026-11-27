"""Completeness audits: they pass on the corrected derivation and fire on the old gap."""

import csv
import json
from pathlib import Path

import pytest

from receipts.square_one import audits, conduit, ie, money, opposition, roster, variants

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / 'data' / 'raw'
EVIDENCE = ROOT / 'data' / 'evidence' / 'jfc-variants'
SQUARE_ONE = ROOT / 'data' / 'evidence' / 'square-one'
JFC_DIR = ROOT / 'data' / 'source'
SPOT_CHECKS = SQUARE_ONE / 'spot_checks.json'


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def _full_derivation():
    """Conduit direct + JFC + IE + pas2 base, as the derive CLI will run them."""
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
    jfc = variants.combine_jfc(
        JFC_DIR / 'jfc_attribution4.json', JFC_DIR / 'jfc_outflow_shares4.json'
    )
    figures = variants.corrected_figures(direct, jfc)
    pas2_per_cycle, pas2_career = variants.load_pas2_base(ROOT / 'congress-money-tracker.json')
    weball = money.derive_weball(BULK, list(range(1980, 2027, 2)))
    ie_rows, _stats = ie.derive_ie(BULK, [2022, 2024, 2026], people, weball)
    ie_by_candidate = ie.per_candidate_cycle(ie_rows)
    return people, figures, pas2_per_cycle, pas2_career, ie_by_candidate


@pytest.fixture(scope='module')
def full_derivation():
    """The full derivation, run once and shared by every test that reads it.

    Deriving re-parses the pinned bulk files and dominates this file's
    runtime; the tests only read the result, so it is built once.
    """
    return _full_derivation()


def test_no_zero_columns_passes_and_fires(full_derivation):
    people, figures, _pc, _career, _ie = full_derivation
    results = audits.audit_no_zero_columns(
        figures,
        [2022, 2024, 2026],
        ['aipac_a_cents', 'aipac_b_cents', 'pro_israel_a_cents', 'pro_israel_b_cents'],
    )
    assert all(r['passed'] for r in results), [r for r in results if not r['passed']]
    # A column that is zero everywhere in a cycle must FAIL LOUDLY.
    zeroed = {key: {**entry, 'aipac_b_cents': 0} for key, entry in figures.items()}
    failed = audits.audit_no_zero_columns(zeroed, [2026], ['aipac_b_cents'])
    assert not failed[0]['passed']
    assert 'ZERO' in failed[0]['detail']


def test_earmark_share_passes_corrected_and_fails_pas2():
    summaries = {
        'C00797670': conduit.summarize_schedule_b(
            _load_json(SQUARE_ONE / 'schedb_aipac_to_bell_2026.json')
        ),
        'C00139659': conduit.summarize_schedule_b(
            _load_json(SQUARE_ONE / 'schedb_jacpac_2024.json')
        ),
        'C00247403': conduit.summarize_schedule_b(
            _load_json(SQUARE_ONE / 'schedb_norpac_2024.json')
        ),
        'C00710848': conduit.summarize_schedule_b(_load_json(SQUARE_ONE / 'schedb_dmfi_2024.json')),
    }
    # Pilot-grounded minimums: AIPAC and NORPAC are near-total conduits,
    # JACPAC mixes direct and conduit money (~37% earmark in 2024), DMFI
    # has no earmarks by every rule tried.
    minimums = {'C00797670': 0.9, 'C00139659': 0.3, 'C00247403': 0.9, 'C00710848': 0.0}
    results = audits.audit_earmark_share(summaries, minimums)
    assert all(r['passed'] for r in results), [r for r in results if not r['passed']]
    # The old gap, in the audit's own terms: pas2's AIPAC earmark share was 2.5%.
    baseline = _load_json(ROOT / 'data' / 'source' / 'baseline.json')
    direct = round(baseline['methodology_totals.aipac_pac_direct_career'] * 100)
    earmark = round(baseline['methodology_totals.aipac_earmark_transmitted_career'] * 100)
    pas2_summary = {
        'C00797670': {
            'total_cents': direct + earmark,
            'earmark_net_cents': earmark,
            'earmark_gross_cents': earmark,
            'earmark_void_cents': 0,
            'own_money_cents': direct,
            'line23_rows': 0,
        }
    }
    failed = audits.audit_earmark_share(pas2_summary, {'C00797670': 0.5})
    assert not failed[0]['passed']


def test_live_spot_checks_and_headline_claim(full_derivation):
    people, figures, pas2_per_cycle, _career, _ie = full_derivation
    corrected_2026 = {
        person_key: entry['aipac_b_cents']
        for (person_key, cycle), entry in figures.items()
        if cycle == 2026
    }
    results = audits.audit_live_spot_checks(corrected_2026, SPOT_CHECKS)
    assert all(r['passed'] for r in results), [r for r in results if not r['passed']]
    pas2_2026 = {
        person_key: entry['aipac']
        for (person_key, cycle), entry in pas2_per_cycle.items()
        if cycle == 2026
    }
    live_2026 = {
        person_key: round(dollars * 100)
        for person_key, dollars in _load_json(SPOT_CHECKS)['live_aipac_2026'].items()
    }
    results = audits.audit_headline_includes_earmarks(corrected_2026, pas2_2026, live_2026)
    assert all(r['passed'] for r in results), [r for r in results if not r['passed']]
    passed, line = audits.run_all(results)
    assert passed, line


def test_ta_comparison(full_derivation):
    people, figures, pas2_per_cycle, pas2_career, ie_by_candidate = full_derivation
    person_of = roster.person_of(people)
    with open(ROOT / 'data' / 'source' / 'pro_israel_pacs.csv', newline='') as f:
        listed = sorted({row['committee_id'] for row in csv.DictReader(f)})
    # Re-derive the IE rows for the pro-Israel layer (TA counts pro-Israel
    # IE only, not all IE — Boafo's UDP money is not TA money).
    weball = money.derive_weball(BULK, list(range(1980, 2027, 2)))
    ie_rows, _stats = ie.derive_ie(BULK, [2022, 2024, 2026], people, weball)
    pi_support, pi_credit = opposition.pro_israel_support_and_credits(
        ie_rows, listed, people, person_of
    )
    corrected_career = {}
    for person in people:
        person_key = person['person_key']
        career = variants.corrected_career_for_person(
            figures, pas2_per_cycle, pas2_career, person_key
        )
        pi_ie = sum(cents for (key, _cycle), cents in pi_support.items() if key == person_key)
        pi_opp = sum(cents for (key, _cycle), cents in pi_credit.items() if key == person_key)
        # TA's total is the tracker-comparable: pro-Israel direct +
        # pro-Israel IE support + pro-Israel opposition credit.
        corrected_career[person_key] = career['pro_israel_b_cents'] + pi_ie + pi_opp
    results = audits.audit_ta_comparison(corrected_career, SPOT_CHECKS)
    assert all(r['passed'] for r in results), [r for r in results if not r['passed']]

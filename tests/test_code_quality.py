"""Complexity and maintainability limits for receipts/, as a ratchet.

New code must stay within the limits. The functions and files listed
below were over them when the limits were set; each may only get
better than its recorded score. Improve one, then tighten or remove
its entry.
"""

from radon.complexity import cc_visit
from radon.metrics import mi_visit

from receipts.common.settings import repo_root

MAX_COMPLEXITY = 10  # radon grade B or better
MIN_MAINTAINABILITY = 20  # radon grade A

COMPLEXITY_DEBT = {
    'common/fec_api.py:scan_filings': 12,
    'common/settings.py:_build_record': 13,
    'ingest/pull_freshness.py:person_summary': 13,
    'rebuild.py:main': 11,
    'site/checks/counts.py:composition': 12,
    'site/checks/data.py:data_round_trip': 12,
    'site/checks/page.py:values_equal': 12,
    'square_one/conduit.py:_cm_lookup': 11,
    'square_one/conduit.py:direct_from_by_recipient': 20,
    'square_one/corrected.py:kept_candidate_id': 11,
    'square_one/corrected.py:substitute_aipac': 20,
    'square_one/corrected.py:substitute_transfers': 19,
    'square_one/counts.py:build_person_lists': 17,
    'square_one/counts.py:count_results': 11,
    'square_one/derive.py:derive_ie_data': 12,
    'square_one/derive.py:run': 11,
    'square_one/ie.py:derive_ie': 11,
    'square_one/money.py:_dedup_groups_for_person': 15,
    'square_one/money.py:derive_committee_money': 13,
    'square_one/transfers.py:apply_transfer_dedup': 15,
    'square_one/transfers.py:shared_committee_groups': 13,
    'square_one/variants.py:combine_jfc': 12,
    'store/all_ie_report.py:bogus_examples': 11,
    'store/all_ie_report.py:file_exclusions': 18,
    'store/all_ie_report.py:roster_career_totals': 17,
    'store/other_committees.py:per_cycle_record': 11,
    'store/pro_israel.py:per_cycle': 13,
    'store/self_funding.py:person_summary': 12,
    'transform/assemble.py:data_notes': 11,
    'transform/build_roster.py:RosterBuilder.note_successors': 13,
    'transform/build_roster.py:senate_class': 14,
    'transform/compute_2026.py:money_in': 13,
    'transform/fec_lookup.py:matching_candidates': 13,
    'validate/audits/clean.py:clean_count_values': 16,
    'validate/audits/clean.py:unopposed': 14,
    'validate/audits/columns_2026.py:cycle_records': 13,
    'validate/audits/columns_2026.py:headline_verdicts': 11,
    'validate/audits/columns_2026.py:term_verdict': 13,
    'validate/audits/money.py:all_ie': 13,
    'validate/audits/ranks.py:ranks_and_dirty': 14,
    'validate/audits/rows.py:csv_matches_json': 18,
    'validate/audits/senate.py:SeatClasses': 11,
    'validate/audits/senate.py:SeatClasses.of': 16,
    'validate/run_history.py:main': 12,
}
# Scored without docstrings, so prose cannot lift a file over the line.
MAINTAINABILITY_DEBT = {}

PACKAGE = repo_root() / 'receipts'


def modules():
    for path in sorted(PACKAGE.rglob('*.py')):
        yield path.relative_to(PACKAGE).as_posix(), path.read_text()


def blocks(code):
    for block in cc_visit(code):
        yield block
        yield from getattr(block, 'methods', [])
        yield from getattr(block, 'closures', [])


def complexity_scores():
    return {
        f'{name}:{block.fullname}': block.complexity
        for name, code in modules()
        for block in blocks(code)
    }


def maintainability_scores():
    return {name: mi_visit(code, multi=False) for name, code in modules()}


def test_functions_stay_within_the_complexity_limit():
    scores = complexity_scores()
    over = {
        name: score
        for name, score in scores.items()
        if score > COMPLEXITY_DEBT.get(name, MAX_COMPLEXITY)
    }
    assert not over, f'too complex (limit {MAX_COMPLEXITY}, or the recorded debt): {over}'


def test_files_stay_above_the_maintainability_limit():
    scores = maintainability_scores()
    under = {
        name: round(score, 2)
        for name, score in scores.items()
        if score < MAINTAINABILITY_DEBT.get(name, MIN_MAINTAINABILITY)
    }
    assert not under, f'hard to maintain (limit {MIN_MAINTAINABILITY}): {under}'


def test_every_recorded_debt_still_exists():
    complexity, maintainability = complexity_scores(), maintainability_scores()
    gone = [name for name in COMPLEXITY_DEBT if name not in complexity]
    gone += [name for name in MAINTAINABILITY_DEBT if name not in maintainability]
    assert not gone, f'remove these entries, the code they name is gone: {gone}'

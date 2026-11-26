"""Weball + pas2 derivation, checked against the committed baseline totals."""

import json
import time
from pathlib import Path

from receipts.square_one import money, parsers, roster, transfers, variants
from receipts.square_one.derive import derive_conduit

ROOT = Path(__file__).resolve().parents[1]
BULK = ROOT / 'data' / 'raw'
AIPAC = 'C00797670'
OVERRIDES = {'C00003251': 'labor', 'C00468314': 'other_unclassified'}
CAREER = list(range(1980, 2027, 2))


def test_classify_committee():
    def row(cid, ctype, org, dsgn=''):
        return parsers.CommitteeRow(
            cid, 'N', 'T', '', '', '', '', '', dsgn, ctype, '', '', org, '', ''
        )

    assert money.classify_committee(row(AIPAC, 'Q', 'M'), AIPAC, OVERRIDES) == 'aipac'
    assert money.classify_committee(row('C00003251', 'Q', 'C'), AIPAC, OVERRIDES) == 'labor'
    assert money.classify_committee(row('C00468314', 'Q', 'C'), AIPAC, OVERRIDES) == (
        'other_unclassified'
    )
    assert money.classify_committee(row('CX', 'Q', 'C'), AIPAC, OVERRIDES) == 'corporate'
    assert money.classify_committee(row('CX', 'N', 'W'), AIPAC, OVERRIDES) == 'corporate'
    assert money.classify_committee(row('CX', 'Q', 'T'), AIPAC, OVERRIDES) == 'trade'
    assert money.classify_committee(row('CX', 'Q', 'L'), AIPAC, OVERRIDES) == 'labor'
    assert money.classify_committee(row('CX', 'Q', 'M'), AIPAC, OVERRIDES) == 'membership'
    assert money.classify_committee(row('CX', 'Q', 'V'), AIPAC, OVERRIDES) == 'cooperative'
    assert money.classify_committee(row('CX', 'Q', ''), AIPAC, OVERRIDES) == 'other_unclassified'
    assert money.classify_committee(row('CX', 'X', ''), AIPAC, OVERRIDES) == 'party'
    assert money.classify_committee(row('CX', 'Y', ''), AIPAC, OVERRIDES) == 'party'
    assert money.classify_committee(row('CX', 'H', '', 'D'), AIPAC, OVERRIDES) == 'leadership'
    assert money.classify_committee(row('CX', 'H', ''), AIPAC, OVERRIDES) == 'other_unclassified'


def test_full_derivation_matches_baseline_totals():
    people = roster.load_roster(ROOT / 'congress-money-tracker.json')
    weball = money.derive_weball(BULK, CAREER)
    records = roster.load_dedup_applied(ROOT / 'data' / 'source' / 'dedup-applied.json')
    problems = money.check_dedup_record(weball, records)
    assert problems == []
    adjusted, differing = money.apply_dedup(weball, records)
    committee_money, stats = money.derive_committee_money(BULK, CAREER, AIPAC, OVERRIDES)
    rolled = money.rollup_person_cycle(adjusted, committee_money, people, CAREER)

    # The double-count decisions the files themselves produce match the record.
    derived = money.derive_dedup_candidates(weball, people)
    recorded = {(r['person_key'], r['cycle']) for r in records}
    assert {(d['person_key'], d['cycle']) for d in derived} == recorded
    for d in derived:
        match = [
            r for r in records if (r['person_key'], r['cycle']) == (d['person_key'], d['cycle'])
        ][0]
        assert d['amount_cents'] == round(float(match['amount']) * 100)
        if d['kept_id'] is not None:
            assert d['kept_id'] == match['kept_id']

    baseline = json.loads((ROOT / 'data' / 'source' / 'baseline.json').read_text())
    totals = {
        key.removeprefix('methodology_totals.'): value
        for key, value in baseline.items()
        if key.startswith('methodology_totals.')
    }
    known = {p['person_key'] for p in people if p['fec_candidate_ids']}

    # The corrected families no longer equal the pas2 base, so they are
    # checked against the derivation's own corrected figures instead:
    # AIPAC direct from the API conduit merge (variant A), transfers
    # from the shared-committee dedup. Both are re-derived here from the
    # bulk files and the committed evidence, never read from derived.json.
    # (Pro-Israel has no pas2 base in this rollup — it is not a committee
    # class here — so it stays unchecked by this test.)
    corrected, _merge_report = derive_conduit(
        ROOT, BULK, people, roster.person_of(people), [2022, 2024, 2026], time.time()
    )
    pas2_per_cycle = {}
    pas2_career = {}
    for (key, cycle), entry in rolled.items():
        pas2_per_cycle[(key, cycle)] = {'aipac': int(entry.get('aipac', 0) or 0), 'pro_israel': 0}
        career = pas2_career.setdefault(key, {'aipac': 0, 'pro_israel': 0})
        career['aipac'] += pas2_per_cycle[(key, cycle)]['aipac']
    corrected_totals = variants.corrected_career_totals(
        corrected, pas2_per_cycle, pas2_career, known
    )
    principal = transfers.principal_committees(BULK, [2022, 2024, 2026])
    offices = transfers.candidate_offices(BULK, [2022, 2024, 2026])
    groups = transfers.shared_committee_groups(people, principal, offices)
    weball_transfers, _transfer_report = transfers.apply_transfer_dedup(adjusted, groups, records)
    rollup_transfers = money.rollup_person_cycle(weball_transfers, committee_money, people, CAREER)

    def corrected_career_total(field):
        total = 0
        for (key, _cycle), entry in rollup_transfers.items():
            if key not in known:
                continue
            total += int(entry.get(field, 0) or 0)
        return total

    def career_total(field):
        total = 0
        for (key, _cycle), entry in rolled.items():
            if key not in known:
                continue
            total += int(entry.get(field, 0) or 0)
        return total

    def stock_total(field):
        total = 0
        for person in people:
            if not person['fec_candidate_ids']:
                continue
            cycles = [c for c in CAREER if rolled[(person['person_key'], c)]['has_weball']]
            if not cycles:
                continue
            latest = max(cycles)
            total += int(rolled[(person['person_key'], latest)][field] or 0)
        return total

    assert career_total('individual') == round(totals['individual_contribution_total_career'] * 100)
    assert corrected_totals['aipac_a_cents'] == round(totals['aipac_pac_direct_career'] * 100)
    assert career_total('aipac_earmark') == round(totals['aipac_earmark_transmitted_career'] * 100)
    assert career_total('corporate') == round(totals['corporate_pac_career'] * 100)
    assert career_total('corporate_earmark') == round(
        totals['corporate_earmark_transmitted_career'] * 100
    )
    for stem in money.OTHER_CLASSES:
        key = 'party_committees_career' if stem == 'party' else f'{stem}_pacs_career'
        assert career_total(stem) == round(totals[key] * 100), stem
    assert career_total('other_unclassified') == round(totals['other_unclassified_career'] * 100)
    assert career_total('total_receipts') == round(totals['total_receipts_career'] * 100)
    assert career_total('total_disbursements') == round(totals['total_disbursements_career'] * 100)
    assert corrected_career_total('transfers_from_auth') == round(
        totals['transfers_from_auth_career'] * 100
    )
    assert corrected_career_total('transfers_to_auth') == round(
        totals['transfers_to_auth_career'] * 100
    )
    assert career_total('cand_contrib') == round(totals['cand_contrib_career'] * 100)
    assert career_total('cand_loans') == round(totals['cand_loans_career'] * 100)
    assert career_total('loan_repayments') == round(totals['loan_repayments_career'] * 100)
    assert stock_total('cash_on_hand') == round(totals['cash_on_hand_career'] * 100)
    assert stock_total('debts_owed_by') == round(totals['debts_owed_by_career'] * 100)

    # Spot cases: Latimer's 2024 pro-Israel direct is the C00144170 row, not the misfiled row.
    latimer_2024 = rolled[('L000606', 2024)]
    assert int(latimer_2024['aipac']) == 1000000
    # Ryan 2026 AIPAC is the pas2 net (-$15,000) before the election-attributed fix.
    ryan_2026 = rolled[('R000579', 2026)]
    assert int(ryan_2026['aipac']) == -1500000
    assert int(ryan_2026['corporate']) == 0
    # Barr 2026 transfers double-count reproduces (the fix is a separate step).
    barr_2026 = rolled[('B001282', 2026)]
    assert int(barr_2026['transfers_from_auth']) == 560908344


def test_committee_money_exclusion_stats_are_small():
    _, stats = money.derive_committee_money(BULK, [2024, 2026], AIPAC, OVERRIDES)
    assert stats['rows_24k'] > 800000
    assert stats['voided_earmark_rows'] > 0
    assert stats['unregistered_committee_rows'] == 0
    # Blank-candidate 24K rows exist in the files (3,660 in 2024+2026) and
    # never attach to a person — the store holds them under candidate_id ''.
    assert stats['blank_candidate_rows'] == 3660

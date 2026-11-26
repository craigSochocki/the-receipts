"""Completeness audits: the checks that would have caught the AIPAC earmark gap.

Every audit returns a result dict (name, passed, detail) and never raises
on a failed check — a failed audit is a finding, reported loudly, not a
crash. The suite runs on the square-one derivation's own figures plus the
independent-source expectations in data/evidence/square-one/spot_checks.json.

(a) No zero columns: any money column that is zero (or near-zero) for
    every record in a cycle FAILS. This is the audit the old pipeline
    lacked: the AIPAC earmark column sat near-zero while the headline
    claimed to include earmarks.
(b) Plausibility ratios: the earmark share of conduit money must look
    like conduit money. OpenSecrets' 2024 split shows Bell's AIPAC money
    nearly all earmarked individuals; the row-level pilot pulls show the
    same shape.
(c) Independent-source spot checks: the corrected 2026 AIPAC figures for
    the 10 comparison members must equal the live FEC Schedule B pulls,
    and the corrected career totals must sit near Track AIPAC's totals
    (within the comparison doc's own residual band) with the two known
    residuals flagged, never silently absorbed.
(d) Method claims in practice: 'headline includes earmarks' must be true
    for the cycle presented, not just in the definition — the corrected
    2026 headline must exceed the pas2 2026 direct by the earmarks the
    live pull shows.
"""

import json
from pathlib import Path


def result(name: str, passed: bool, detail: str) -> dict:
    return {'name': name, 'passed': passed, 'detail': detail}


def audit_no_zero_columns(figures: dict, cycles: list[int], columns: list[str]) -> list[dict]:
    """(a) Every column must have a non-zero total in every cycle."""
    results = []
    for cycle in cycles:
        for column in columns:
            values = [
                entry[column]
                for (person_key, entry_cycle), entry in figures.items()
                if entry_cycle == cycle and column in entry
            ]
            total = sum(values)
            nonzero = sum(1 for value in values if value)
            passed = total != 0 and nonzero > 0
            results.append(
                result(
                    f'nonzero:{column}:{cycle}',
                    passed,
                    f'total ${total / 100:,.2f} across {nonzero} non-zero records'
                    if passed
                    else f'COLUMN IS ZERO in {cycle}: total ${total / 100:,.2f}, {nonzero} non-zero records',
                )
            )
    return results


def audit_earmark_share(summaries: dict, minimums: dict) -> list[dict]:
    """(b) Earmark share of conduit money must look like conduit money.

    `summaries` maps committee_id -> conduit.summarize_schedule_b output;
    `minimums` maps committee_id -> the lowest plausible earmark share.
    AIPAC's share is nearly all earmark (Bell 2026 pilot pull, OS 2024
    split); DMFI's is none by every rule tried (pilot) and is expected none.
    """
    results = []
    for committee_id, summary in sorted(summaries.items()):
        total = summary['total_cents']
        share = summary['earmark_net_cents'] / total if total else 0.0
        minimum = minimums.get(committee_id, 0.5)
        passed = share >= minimum
        results.append(
            result(
                f'earmark-share:{committee_id}',
                passed,
                f'earmark {share:.1%} of ${total / 100:,.2f} line-23 total (min {minimum:.0%})'
                if passed
                else f'EARMARK SHARE {share:.1%} for {committee_id} (min {minimum:.0%}) — conduit money that is not mostly earmark is suspect',
            )
        )
    return results


def audit_live_spot_checks(corrected_aipac_2026: dict, expectations_path: Path) -> list[dict]:
    """(c) Corrected 2026 AIPAC direct must equal the live FEC pulls for the 10."""
    with open(expectations_path) as f:
        expected = json.load(f)
    results = []
    for person_key, dollars in sorted(expected['live_aipac_2026'].items()):
        cents = round(dollars * 100)
        mine = corrected_aipac_2026.get(person_key, 0)
        # The comparison doc's live figures are whole-dollar roundings.
        passed = abs(mine - cents) <= 100
        results.append(
            result(
                f'live-2026:{person_key}',
                passed,
                f'${mine / 100:,.2f} == live FEC ${dollars:,.2f}'
                if passed
                else f'${mine / 100:,.2f} != live FEC ${dollars:,.2f} (diff ${(mine - cents) / 100:,.2f})',
            )
        )
    return results


def audit_ta_comparison(corrected_career: dict, expectations_path: Path) -> list[dict]:
    """(c) Corrected career totals must sit near Track AIPAC's, residuals flagged.

    `corrected_career` maps person_key -> the tracker-comparable total
    (pro-Israel direct + pro-Israel IE support + pro-Israel opposition
    credit, variant B) in cents. TA is an independent count of the same
    money plus a donor-network layer, so the two should agree to within
    the comparison doc's own residual band (most members reconcile within
    it, and the largest open residual, Latimer's, sets the band). A member
    outside the band fails loudly. The two known residuals (Latimer,
    Collins) are reported as known-open items.
    """
    with open(expectations_path) as f:
        expected = json.load(f)
    results = []
    known = {item['person_key']: item for item in expected['known_residuals']}
    band_cents = 65000000
    for person_key, dollars in sorted(expected['ta_career_total'].items()):
        cents = round(dollars * 100)
        mine = corrected_career.get(person_key, 0)
        diff_cents = mine - cents
        if person_key in known:
            results.append(
                result(
                    f'ta-career:{person_key}',
                    True,
                    f'${mine / 100:,.2f} vs TA ${dollars:,.2f} (diff '
                    f'${diff_cents / 100:+,.2f}) — KNOWN-OPEN residual '
                    f'${known[person_key]["dollars"]:,.2f}: {known[person_key]["note"]}',
                )
            )
        else:
            passed = abs(diff_cents) <= band_cents
            results.append(
                result(
                    f'ta-career:{person_key}',
                    passed,
                    f'${mine / 100:,.2f} vs TA ${dollars:,.2f} '
                    f'(diff ${diff_cents / 100:+,.2f}, band ±$650,000)'
                    if passed
                    else f'${mine / 100:,.2f} vs TA ${dollars:,.2f} '
                    f'(diff ${diff_cents / 100:+,.2f}) — OUTSIDE the ±$650,000 band',
                )
            )
    return results


def audit_headline_includes_earmarks(
    corrected_2026: dict, pas2_2026: dict, live_2026: dict
) -> list[dict]:
    """(d) 'Headline includes earmarks' must be true for 2026 in practice.

    For each comparison member with live earmark money, the corrected
    headline must exceed the pas2 direct by at least the live earmarks
    (live total minus pas2 direct), i.e. the correction actually added
    the earmarks instead of re-labeling the pas2 figure.
    """
    results = []
    for person_key, live_cents in sorted(live_2026.items()):
        pas2_cents = pas2_2026.get(person_key, 0)
        mine = corrected_2026.get(person_key, 0)
        if live_cents <= pas2_cents:
            continue
        # The live figures are whole-dollar roundings; allow a dollar of slack.
        passed = mine >= live_cents - 100
        results.append(
            result(
                f'headline-earmarks:{person_key}',
                passed,
                f'corrected ${mine / 100:,.2f} covers live ${live_cents / 100:,.2f} '
                f'(pas2 was ${pas2_cents / 100:,.2f})'
                if passed
                else f'corrected ${mine / 100:,.2f} below live ${live_cents / 100:,.2f} '
                f'(pas2 was ${pas2_cents / 100:,.2f}) — earmarks still missing',
            )
        )
    return results


def run_all(results: list[dict]) -> tuple[bool, str]:
    """Summarize a run: (all passed, one-line report)."""
    failed = [item for item in results if not item['passed']]
    line = f'{len(results) - len(failed)}/{len(results)} audits passed'
    if failed:
        line += '; FAILING: ' + '; '.join(item['name'] for item in failed)
    return not failed, line

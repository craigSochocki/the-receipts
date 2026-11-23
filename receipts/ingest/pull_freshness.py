#!/usr/bin/env python3
"""Freshness refresh driver: new money since bulk coverage, never merged into the dataset.

Writes data/intermediate/freshness_snapshot.json, labeled by source and
date (methodology.md §16, research/freshness-research.md). Legs per
roster person, all through the FEC API:

1. Totals refresh: /candidate/{id}/totals/?cycle=2026, flagged when its
   coverage_end_date is past the bulk cutoff.
2. Form 6 (48-Hour Notices): pull_f6.pull_committee on each principal
   campaign committee (designation P) since the window start.
3. 24/48-hour IE: pull_f24.sweep for --f24-committee x --f24-candidate
   pairs. --all also sweeps the config-listed spender committees
   committee-wide and attributes rows to roster people by candidate_id.

--all is gated by pull_gate.py (one /filings/ check per family; a gate
error falls back to the full run); --no-gate forces the full run. --all
and --f24-committee-sweep refuse DEMO_KEY: a full run is ~2,200-2,350
keyed calls.

Usage:
    python3 receipts/ingest/pull_freshness.py --person anthonyconstantinonyhouse \\
        --f24-committee C00799031 --f24-candidate abdulelsayedmisenate
    python3 receipts/ingest/pull_freshness.py --f24-committee-sweep
    FEC_API_KEY=<registered key> python3 receipts/ingest/pull_freshness.py --all
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone

from receipts.common.fec_api import client
from receipts.common.files import read_json
from receipts.common.settings import settings
from receipts.ingest import pull_f6, pull_f24, pull_gate


def bulk_coverage_end():
    return settings().verification.coverage_end


CADENCE_NOTE = (
    'Final 20 days before an election: daily. '
    'Cycle in progress outside final 20 days: weekly. '
    'After each deadline: event-driven. Reconcile '
    'against the next bulk re-pull; never blend into '
    'the dataset totals.'
)


def principal_committees(candidate_id, cycle=2026):
    """Principal campaign committee IDs (designation P) for a candidate."""
    data = client().get(f'/candidate/{candidate_id}/committees/', {'cycle': cycle, 'per_page': 100})
    return [c['committee_id'] for c in data.get('results', []) if c.get('designation') == 'P']


def totals_refresh(candidate_id, cycle=2026):
    """Latest processed totals for one candidate/cycle, with coverage.

    Returns the per-cycle row (cycle == requested) with its
    coverage_end_date, plus a flag for whether it is newer than bulk.
    election_full=true is NOT used here: it returns only the aggregate
    row (cycle null), which conflates 2024 and 2026.
    """
    data = client().get(f'/candidate/{candidate_id}/totals/', {'cycle': cycle, 'per_page': 100})
    rows = [r for r in data.get('results', []) if r.get('cycle') == cycle]
    if not rows:
        return {'candidate_id': candidate_id, 'cycle': cycle, 'found': False}
    row = rows[0]
    coverage_end = row.get('coverage_end_date')
    # coverage_end_date comes back as a timestamp ('2026-10-14T00:00:00');
    # compare the date part only, or the longer string always wins.
    coverage_date = (coverage_end or '')[:10]
    return {
        'candidate_id': candidate_id,
        'cycle': cycle,
        'found': True,
        'coverage_end_date': coverage_end,
        'newer_than_bulk': bool(coverage_date and coverage_date > bulk_coverage_end().weball),
        'total_receipts': row.get('receipts'),
        'total_disbursements': row.get('disbursements'),
        'candidate_contributions': row.get('candidate_contribution'),
        'candidate_loans': row.get('candidate_loans'),
        'cash_on_hand': row.get('cash_on_hand_end_period'),
        'debts_owed_by': row.get('debts_owed_by_committee'),
        'debts_owed_to': row.get('last_debts_owed_to_committee'),
        'last_report_year': row.get('last_report_year'),
        'last_report_type_full': row.get('last_report_type_full'),
    }


def new_entry(person):
    return {
        'person_key': person['person_key'],
        'full_name': person['full_name'],
        'fec_candidate_ids': person.get('fec_candidate_ids'),
        'totals': [],
        'f6': [],
        'f24': [],
    }


def candidate_ids(person):
    return person.get('fec_candidate_ids') or []


def totals_leg(person):
    return [totals_refresh(cid) for cid in candidate_ids(person)]


def f6_leg(person):
    return [
        pull_f6.pull_committee(cmte, since=bulk_coverage_end().freshness_window_start)
        for cid in candidate_ids(person)
        for cmte in principal_committees(cid)
    ]


def refresh_person(person, f24_committees):
    """All three legs for one roster person: the snapshot entry."""
    entry = new_entry(person)
    for cid in candidate_ids(person):
        entry['totals'].append(totals_refresh(cid))
        for cmte in principal_committees(cid):
            entry['f6'].append(
                pull_f6.pull_committee(cmte, since=bulk_coverage_end().freshness_window_start)
            )
    entry['f24'] = [
        pull_f24.sweep(cmte, cid) for cmte in f24_committees for cid in candidate_ids(person)
    ]
    return entry


def gated_entry(person, decision):
    """Only the legs the gate found new filings for (a new F6 alone gets no totals call)."""
    entry = new_entry(person)
    legs = []
    if person['person_key'] in decision['totals_person_keys']:
        legs.append('totals')
        entry['totals'] = totals_leg(person)
    if person['person_key'] in decision['f6_person_keys']:
        legs.append('f6')
        entry['f6'] = f6_leg(person)
    entry['gate_legs_run'] = legs
    return entry


class Tally:
    """F24 dollars by support/oppose indicator; any other indicator is unclassified."""

    def __init__(self):
        self.support = self.oppose = self.unclassified = self.total = 0.0
        self.n_rows = 0

    def add(self, amount, indicator):
        if indicator == 'S':
            self.support += amount
        elif indicator == 'O':
            self.oppose += amount
        else:
            self.unclassified += amount
        self.total += amount
        self.n_rows += 1

    def rounded(self):
        return {
            'support': round(self.support, 2),
            'oppose': round(self.oppose, 2),
            'unclassified': round(self.unclassified, 2),
            'total': round(self.total, 2),
            'n_rows': self.n_rows,
        }


def attribute_f24_rows(rows, by_candidate):
    """F24 rows split to roster people by candidate_id.

    Returns (attributed, non_roster, unclassified_total, unclassified_n_rows):
    one tally per roster candidate with rows, sorted by candidate_id, and one
    for everything off the roster (blank candidate_id included). Every row
    lands in exactly one tally and one of support / oppose / unclassified.
    """
    per_candidate = {}
    non_roster = Tally()
    unclassified_total, unclassified_n = 0.0, 0
    for r in rows:
        amount = float(r.get('expenditure_amount') or 0)
        indicator = r.get('support_oppose_indicator')
        cid = r.get('candidate_id')
        on_roster = bool(cid) and cid in by_candidate
        tally = per_candidate.setdefault(cid, Tally()) if on_roster else non_roster
        tally.add(amount, indicator)
        if indicator not in ('S', 'O'):
            unclassified_total += amount
            unclassified_n += 1
    attributed = [
        {
            'person_key': by_candidate[cid]['person_key'],
            'candidate_id': cid,
            **per_candidate[cid].rounded(),
        }
        for cid in sorted(per_candidate)
    ]
    return attributed, non_roster.rounded(), round(unclassified_total, 2), unclassified_n


def sweep_committee_f24(committee_id, committee_name, cycle, by_candidate):
    """One committee-wide F24 sweep, attributed to the roster.

    Raw rows stay out of the snapshot (a sweep can run to thousands);
    `pull_f24.py --committee <id> --cycle 2026` reproduces them.
    """
    result = pull_f24.sweep(committee_id, candidate_id=None, cycle=cycle)
    rows = result.get('f24_rows') or []
    attributed, non_roster, unc_total, unc_n = attribute_f24_rows(rows, by_candidate)
    return {
        'committee_id': committee_id,
        'committee_name': committee_name,
        'cycle': cycle,
        'f24_n_rows': result['f24_n_rows'],
        'f24_total': result['f24_total'],
        'support': round(sum(a['support'] for a in attributed) + non_roster['support'], 2),
        'oppose': round(sum(a['oppose'] for a in attributed) + non_roster['oppose'], 2),
        'unclassified_total': unc_total,
        'unclassified_n_rows': unc_n,
        'latest_expenditure_date': result['latest_expenditure_date'],
        'residual_unexplained': result['residual_unexplained'],
        'residual_explained': result['residual_explained'],
        'attributed': attributed,
        'non_roster_total': non_roster['total'],
        'non_roster_n_rows': non_roster['n_rows'],
    }


def committee_sweeps(committees, by_candidate):
    return [
        sweep_committee_f24(
            c['committee_id'],
            c['committee_name'],
            settings().freshness.f24_committee_sweep_cycle,
            by_candidate,
        )
        for c in committees
    ]


def snapshot_gate_record(decision):
    """The gate decision for the snapshot, with new filings cut to their file_numbers."""
    if not decision:
        return {'gated': False, 'reason': 'gate did not run', 'gate_error': None}
    record = {k: v for k, v in decision.items() if k != 'new_state'}
    record['families'] = {
        fam: {
            **{k: v for k, v in r.items() if k != 'new_filings'},
            'new_filing_file_numbers': [f.get('file_number') for f in r.get('new_filings', [])],
        }
        for fam, r in decision.get('families', {}).items()
    }
    return record


def gate_summary_fields(gate):
    """Gate fields for the summary. A gate that ran and failed still counts as applied."""
    if not gate or not gate.get('gated'):
        return {
            'gate_applied': False,
            'gate_calls_used': 0,
            'gate_skipped_all': False,
            'gate_affected_persons': 0,
            'gate_error': (gate or {}).get('gate_error'),
        }
    return {
        'gate_applied': True,
        'gate_calls_used': gate.get('calls_used', 0),
        'gate_skipped_all': bool(gate.get('all_skipped')),
        'gate_affected_persons': len(gate.get('affected_person_keys') or []),
        'gate_error': gate.get('gate_error'),
    }


def person_summary(entries):
    f6 = [f for e in entries for f in e['f6']]
    f24 = [(e['person_key'], s) for e in entries for s in e['f24']]
    return {
        'n_persons': len(entries),
        'new_f6_candidate_loans': round(sum(f.get('total_candidate_loans', 0) for f in f6), 2),
        'new_f6_contributions': round(sum(f.get('total_contributions', 0) for f in f6), 2),
        'new_f24_ie': round(sum(s.get('f24_total', 0) for _, s in f24), 2),
        'open_f24_residuals': [
            {
                'person_key': person_key,
                'committee_id': s.get('committee_id'),
                'candidate_id': s.get('candidate_id'),
                'residual_unexplained': s.get('residual_unexplained'),
            }
            for person_key, s in f24
            if s.get('residual_unexplained')
        ],
        'totals_newer_than_bulk': [
            t['candidate_id'] for e in entries for t in e['totals'] if t.get('newer_than_bulk')
        ],
    }


def sweep_summary(sweeps):
    return {
        'committee_sweeps_n': len(sweeps),
        'committee_sweeps_f24_ie': round(sum(s.get('f24_total', 0) for s in sweeps), 2),
        'committee_sweeps_by_committee': [
            {
                'committee_id': s.get('committee_id'),
                'committee_name': s.get('committee_name'),
                'f24_total': s.get('f24_total'),
                'f24_n_rows': s.get('f24_n_rows'),
            }
            for s in sweeps
        ],
        'committee_sweeps_open_residuals': [
            {
                'committee_id': s.get('committee_id'),
                'residual_unexplained': s.get('residual_unexplained'),
            }
            for s in sweeps
            if s.get('residual_unexplained')
        ],
    }


def summarize(entries, committee_sweeps=None, gate=None):
    return {
        **person_summary(entries),
        **sweep_summary(committee_sweeps or []),
        **gate_summary_fields(gate),
    }


def parse_args():
    ap = argparse.ArgumentParser(description='Freshness refresh driver.')
    ap.add_argument(
        '--person', action='append', default=[], help='roster person_key to refresh (repeatable)'
    )
    ap.add_argument(
        '--all', action='store_true', help='refresh every roster person (registered key required)'
    )
    ap.add_argument(
        '--no-gate',
        action='store_true',
        help='force the full run, ignoring the pre-flight gate '
        '(default with --all is gated: only legs with new '
        'filings run — see receipts/ingest/pull_gate.py)',
    )
    ap.add_argument(
        '--f24-committee',
        action='append',
        default=[],
        help='spender committee ID for the F24 sweeps (repeatable)',
    )
    ap.add_argument(
        '--f24-candidate',
        action='append',
        default=[],
        help='roster person_key as F24 target (repeatable; defaults to the --person list)',
    )
    ap.add_argument(
        '--f24-committee-sweep',
        action='store_true',
        help='run ONLY the six config-listed committee F24 sweeps '
        '(cycle 2026), no per-person refresh; registered key '
        'required — DEMO_KEY is refused (six committee sweeps '
        'are ~12-94+ keyed calls, production-scale, not a '
        'spot check). For a DEMO_KEY test use the '
        'single-committee CLI instead: pull_f24.py '
        '--committee <id> --cycle 2026.',
    )
    ap.add_argument(
        '--out',
        default=None,
        help='snapshot path (default data/intermediate/freshness_snapshot.json)',
    )
    return ap, ap.parse_args()


def refuse_demo_key(flag, workload, alternative=''):
    if client().is_demo_key:
        sys.exit(
            f'ERROR: {flag} needs a registered api.data.gov key '
            f'(FEC_API_KEY env var). DEMO_KEY (~30/hr) cannot run {workload}.{alternative}'
        )


class Roster:
    def __init__(self, dataset):
        self.people = dataset
        self.by_key = {r['person_key']: r for r in dataset}
        self.by_candidate = pull_gate.candidate_index(dataset)

    def lookup(self, person_keys):
        missing = next((pk for pk in person_keys if pk not in self.by_key), None)
        if missing is not None:
            sys.exit(f'ERROR: no roster person {missing!r}')
        return [self.by_key[pk] for pk in person_keys]


def run_gate(dataset, by_candidate):
    """The gate decision; a gate error means a full run, never a skip."""
    decision = pull_gate.gate_run(dataset, by_candidate)
    if decision['run_full']:
        print(
            'GATE ERROR — falling back to the FULL freshness run '
            '(see gate_error in the snapshot); state NOT advanced.',
            file=sys.stderr,
            flush=True,
        )
    return decision


def gated_refresh(decision, roster):
    entries = [gated_entry(roster.by_key[pk], decision) for pk in decision['affected_person_keys']]
    return entries, committee_sweeps(decision['f24_sweep_committees'], roster.by_candidate)


def full_refresh(args, persons, f24_persons, roster):
    """Every leg for the requested people; F24 targets not in --person get entries too."""
    f24_targets = args.f24_candidate or args.person
    entries = [
        refresh_person(p, args.f24_committee if p['person_key'] in f24_targets else [])
        for p in persons
    ]
    entries += [
        refresh_person(p, args.f24_committee)
        for p in f24_persons
        if p['person_key'] not in args.person
    ]
    sweeps = committee_sweeps(pull_gate.sweep_committees(), roster.by_candidate) if args.all else []
    return entries, sweeps


def ungated_record(reason):
    return {'gated': False, 'reason': reason, 'gate_error': None}


def build_snapshot(entries, sweeps, gate_record, summary):
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'window_start': bulk_coverage_end().freshness_window_start,
        'bulk_coverage': asdict(bulk_coverage_end()),
        'api_key_type': client().key_type,
        'cadence_note': CADENCE_NOTE,
        'entries': entries,
        'committee_sweeps': sweeps,
        'gate': gate_record,
        'gate_error': gate_record.get('gate_error'),
        'summary': summary,
    }


def write_snapshot(out, snapshot):
    out = out or str(settings().paths.freshness_snapshot)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(snapshot, f, indent=1)
    print(f'wrote {out}')


def advance_gate_state(decision):
    """Save the gate's new state after a gated run that found something."""
    if decision['run_full'] or decision['all_skipped'] or decision.get('new_state') is None:
        return
    try:
        pull_gate.save_state(decision['new_state'])
    except Exception as e:
        print(
            f'WARNING: could not save freshness state: {e} — '
            f'next run re-gates from the previous state.',
            file=sys.stderr,
            flush=True,
        )


def sweeps_only(args, roster):
    sweeps = committee_sweeps(pull_gate.sweep_committees(), roster.by_candidate)
    record = ungated_record('--f24-committee-sweep mode: the gate applies to --all only')
    snapshot = build_snapshot([], sweeps, record, summarize([], sweeps))
    write_snapshot(args.out, snapshot)
    s = snapshot['summary']
    print(
        f'committee F24 sweeps: {s["committee_sweeps_n"]} committee(s); '
        f'F24 IE ${s["committee_sweeps_f24_ie"]:,.2f}; '
        f'open sweep residuals: {s["committee_sweeps_open_residuals"] or "none"}'
    )


def report(s, gated):
    print(
        f'freshness: {s["n_persons"]} person(s); '
        f'F6 candidate loans ${s["new_f6_candidate_loans"]:,.2f}, '
        f'F6 contributions ${s["new_f6_contributions"]:,.2f}, '
        f'F24 IE ${s["new_f24_ie"]:,.2f}; '
        f'totals newer than bulk: {s["totals_newer_than_bulk"] or "none"}; '
        f'open F24 residuals: {s["open_f24_residuals"] or "none"}; '
        f'committee F24 sweeps: {s["committee_sweeps_n"]} committee(s), '
        f'${s["committee_sweeps_f24_ie"]:,.2f}'
    )
    if gated:
        print(
            f'gate: {s["gate_calls_used"]} calls; affected persons: '
            f'{s["gate_affected_persons"]}; skipped all: '
            f'{s["gate_skipped_all"]}; gate error: '
            f'{s["gate_error"] or "none"}'
        )


def main():
    ap, args = parse_args()
    if args.all:
        refuse_demo_key('--all', 'the ~2,200-2,350 calls a full refresh needs')
    roster = Roster(read_json(settings().paths.dataset_json))
    if args.f24_committee_sweep:
        refuse_demo_key(
            '--f24-committee-sweep',
            'the six committee sweeps (~12-94+ keyed calls)',
            ' Single-committee spot check instead: '
            'python3 receipts/ingest/pull_f24.py --committee <id> --cycle 2026.',
        )
        return sweeps_only(args, roster)
    gated = args.all and not args.no_gate
    decision = run_gate(roster.people, roster.by_candidate) if gated else None
    if not args.all and not args.person:
        ap.error('need --person (repeatable) or --all')
    persons = roster.people if args.all else roster.lookup(args.person)
    f24_persons = roster.lookup(args.f24_candidate or args.person)
    if gated and not decision['run_full']:
        entries, sweeps = gated_refresh(decision, roster)
    else:
        entries, sweeps = full_refresh(args, persons, f24_persons, roster)
    if not gated:
        decision = ungated_record(
            '--no-gate: full run forced'
            if args.no_gate
            else 'explicit --person mode: the gate applies to --all only'
        )
    snapshot = build_snapshot(
        entries, sweeps, snapshot_gate_record(decision), summarize(entries, sweeps, gate=decision)
    )
    write_snapshot(args.out, snapshot)
    if gated:
        advance_gate_state(decision)
    report(snapshot['summary'], gated)


if __name__ == '__main__':
    main()

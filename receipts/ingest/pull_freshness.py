#!/usr/bin/env python3
"""Freshness driver: money filed since the bulk cutoff, never merged into the dataset."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone

from receipts.common.fec_api import client
from receipts.common.files import read_json
from receipts.common.log import log, run
from receipts.common.settings import settings
from receipts.domain.money import exact_sum
from receipts.ingest import pull_f6, pull_f24


def bulk_coverage_end():
    return settings().verification.coverage_end


CADENCE_NOTE = (
    'Final 20 days before an election: daily. '
    'Cycle in progress outside final 20 days: weekly. '
    'After each deadline: event-driven. Reconcile '
    'against the next bulk re-pull; never blend into '
    'the dataset totals.'
)


def principal_committees(candidate_id, cycle=None):
    """Principal campaign committee IDs (designation P) for a candidate."""
    cycle = cycle or settings().cycles.current
    data = client().get(f'/candidate/{candidate_id}/committees/', {'cycle': cycle, 'per_page': 100})
    return [c['committee_id'] for c in data.get('results', []) if c.get('designation') == 'P']


def totals_refresh(candidate_id, cycle=None):
    """One candidate's per-cycle API totals; election_full would mix cycles, so it is unused."""
    cycle = cycle or settings().cycles.current
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
    entry['totals'] = totals_leg(person)
    entry['f6'] = f6_leg(person)
    entry['f24'] = [
        pull_f24.sweep(cmte, cid) for cmte in f24_committees for cid in candidate_ids(person)
    ]
    return entry


DIRECTION = {'S': 'support', 'O': 'oppose'}


class Tally:
    """F24 dollars by support/oppose indicator; any other indicator is unclassified."""

    def __init__(self):
        self.amounts = {'support': [], 'oppose': [], 'unclassified': []}

    def add(self, amount, indicator):
        self.amounts[DIRECTION.get(indicator, 'unclassified')].append(amount)

    def rounded(self):
        every = [a for amounts in self.amounts.values() for a in amounts]
        return {
            **{k: exact_sum(amounts, 0.0) for k, amounts in self.amounts.items()},
            'total': exact_sum(every, 0.0),
            'n_rows': len(every),
        }


def attribute_f24_rows(rows, by_candidate):
    """(per roster candidate tallies sorted by ID, the off-roster tally, unclassified $ and rows)."""
    per_candidate, non_roster, unclassified = {}, Tally(), []
    for r in rows:
        amount = float(r.get('expenditure_amount') or 0)
        indicator = r.get('support_oppose_indicator')
        cid = r.get('candidate_id')
        on_roster = bool(cid) and cid in by_candidate
        tally = per_candidate.setdefault(cid, Tally()) if on_roster else non_roster
        tally.add(amount, indicator)
        if indicator not in DIRECTION:
            unclassified.append(amount)
    attributed = [
        {
            'person_key': by_candidate[cid]['person_key'],
            'candidate_id': cid,
            **per_candidate[cid].rounded(),
        }
        for cid in sorted(per_candidate)
    ]
    return attributed, non_roster.rounded(), exact_sum(unclassified, 0.0), len(unclassified)


def sweep_committee_f24(committee_id, committee_name, cycle, by_candidate):
    """One committee-wide F24 sweep, attributed to the roster; raw rows stay out."""
    result = pull_f24.sweep(committee_id, candidate_id=None, cycle=cycle)
    rows = result.get('f24_rows') or []
    attributed, non_roster, unc_total, unc_n = attribute_f24_rows(rows, by_candidate)
    return {
        'committee_id': committee_id,
        'committee_name': committee_name,
        'cycle': cycle,
        'f24_n_rows': result['f24_n_rows'],
        'f24_total': result['f24_total'],
        'support': exact_sum([*(a['support'] for a in attributed), non_roster['support']]),
        'oppose': exact_sum([*(a['oppose'] for a in attributed), non_roster['oppose']]),
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
            settings().cycles.current,
            by_candidate,
        )
        for c in committees
    ]


def person_summary(entries):
    f6 = [f for e in entries for f in e['f6']]
    f24 = [(e['person_key'], s) for e in entries for s in e['f24']]
    return {
        'n_persons': len(entries),
        'new_f6_candidate_loans': exact_sum(f.get('total_candidate_loans', 0) for f in f6),
        'new_f6_contributions': exact_sum(f.get('total_contributions', 0) for f in f6),
        'new_f24_ie': exact_sum(s.get('f24_total', 0) for _, s in f24),
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
        'committee_sweeps_f24_ie': exact_sum(s.get('f24_total', 0) for s in sweeps),
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


def summarize(entries, committee_sweeps=None):
    return {**person_summary(entries), **sweep_summary(committee_sweeps or [])}


def parse_args():
    ap = argparse.ArgumentParser(description='Freshness refresh driver.')
    ap.add_argument(
        '--person', action='append', default=[], help='roster person_key to refresh (repeatable)'
    )
    ap.add_argument(
        '--all', action='store_true', help='refresh every roster person (registered key required)'
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
        help='run only the config-listed committee F24 sweeps (registered key required)',
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


def candidate_index(dataset):
    return {cid: r for r in dataset for cid in (r.get('fec_candidate_ids') or [])}


def sweep_committees():
    return [
        {'committee_id': c.committee_id, 'committee_name': c.committee_name}
        for c in settings().freshness.f24_committee_sweep
    ]


class Roster:
    def __init__(self, dataset):
        self.people = dataset
        self.by_key = {r['person_key']: r for r in dataset}
        self.by_candidate = candidate_index(dataset)

    def lookup(self, person_keys):
        missing = next((pk for pk in person_keys if pk not in self.by_key), None)
        if missing is not None:
            sys.exit(f'ERROR: no roster person {missing!r}')
        return [self.by_key[pk] for pk in person_keys]


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
    sweeps = committee_sweeps(sweep_committees(), roster.by_candidate) if args.all else []
    return entries, sweeps


def build_snapshot(entries, sweeps, summary):
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'window_start': bulk_coverage_end().freshness_window_start,
        'bulk_coverage': asdict(bulk_coverage_end()),
        'api_key_type': client().key_type,
        'cadence_note': CADENCE_NOTE,
        'entries': entries,
        'committee_sweeps': sweeps,
        'summary': summary,
    }


def write_snapshot(out, snapshot):
    out = out or str(settings().paths.freshness_snapshot)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(snapshot, f, indent=1)
    log.info(f'wrote {out}')


def sweeps_only(args, roster):
    sweeps = committee_sweeps(sweep_committees(), roster.by_candidate)
    snapshot = build_snapshot([], sweeps, summarize([], sweeps))
    write_snapshot(args.out, snapshot)
    s = snapshot['summary']
    log.info(
        f'committee F24 sweeps: {s["committee_sweeps_n"]} committee(s); '
        f'F24 IE ${s["committee_sweeps_f24_ie"]:,.2f}; '
        f'open sweep residuals: {s["committee_sweeps_open_residuals"] or "none"}'
    )


def report(s):
    log.info(
        f'freshness: {s["n_persons"]} person(s); '
        f'F6 candidate loans ${s["new_f6_candidate_loans"]:,.2f}, '
        f'F6 contributions ${s["new_f6_contributions"]:,.2f}, '
        f'F24 IE ${s["new_f24_ie"]:,.2f}; '
        f'totals newer than bulk: {s["totals_newer_than_bulk"] or "none"}; '
        f'open F24 residuals: {s["open_f24_residuals"] or "none"}; '
        f'committee F24 sweeps: {s["committee_sweeps_n"]} committee(s), '
        f'${s["committee_sweeps_f24_ie"]:,.2f}'
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
            'python3 receipts/ingest/pull_f24.py --committee <id>.',
        )
        return sweeps_only(args, roster)
    if not args.all and not args.person:
        ap.error('need --person (repeatable) or --all')
    persons = roster.people if args.all else roster.lookup(args.person)
    f24_persons = roster.lookup(args.f24_candidate or args.person)
    entries, sweeps = full_refresh(args, persons, f24_persons, roster)
    snapshot = build_snapshot(entries, sweeps, summarize(entries, sweeps))
    write_snapshot(args.out, snapshot)
    report(snapshot['summary'])


if __name__ == '__main__':
    run(main)

#!/usr/bin/env python3
"""Freshness refresh driver: new money since bulk coverage (Oct 14).

Runs the three freshness legs for a set of roster persons and writes
work/freshness_snapshot.json — new money found since bulk coverage,
labeled by source and date, NEVER merged into the dataset totals.
See methodology.md §16 and work/freshness-research.md.

Legs, per person (all through the FEC API, DEMO_KEY for spot checks):
1. Candidate totals refresh — /v1/candidate/{id}/totals/?cycle=2026.
   Only as fresh as the latest processed report; if its
   coverage_end_date is still the bulk cutoff (2026-10-14) there is
   nothing new. If a newer report has been processed, the new
   receipts/loans/cash are recorded here, for reconciliation against
   the next bulk re-pull — never blended into the dataset.
2. Form 6 (48-Hour Notices) — pull_f6.pull_committee() on the person's
   principal campaign committee(s), since the window start
   (2026-10-15). Candidate loans (CAN) split from contributions.
3. 24/48-hour IE — pull_f24.sweep() for (--f24-committees x
   --f24-candidates) pairs, F24-only filtered, with the deduped
   reconciliation and residual rows.

Committee IDs come from /v1/candidate/{id}/committees/?cycle=2026
(designation P = principal campaign committee).

Usage:
    # Limited spot check (DEMO_KEY-friendly, ~5 calls):
    python3 work/pull_freshness.py --person anthonyconstantinonyhouse \\
        --f24-committee C00799031 --f24-candidate abdul-elsayed-misenate
    # Full refresh (registered key REQUIRED — ~1,300+ calls):
    FEC_API_KEY=<registered key> python3 work/pull_freshness.py --all

Cadence: final 20 days before an election daily; cycle in progress
outside the final 20 days weekly; after each filing deadline
(Dec 3 post-general, Jan 31 year-end) event-driven. After each bulk
re-pull, reconcile the snapshot sums against the new report and
start a fresh snapshot — never carry freshness figures forward into
the dataset.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Imported as a script from work/ (sys.path[0] is work/); the pulls live
# next to this driver.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pull_f24
import pull_f6
from config import load_config

CFG = load_config()
ROOT = CFG['_root']
API_KEY = os.environ.get(CFG['fec_api']['api_key_env'], CFG['fec_api']['api_key_default'])
API_BASE = 'https://api.open.fec.gov/v1'
SLEEP = max(CFG['fec_api']['sleep_between_requests_seconds'], 1.0)
WINDOW_START = CFG['verification']['coverage_end']['freshness_window_start']
BULK_WEBALL_END = str(CFG['verification']['coverage_end']['weball'])


def api_get(path, params):
    params = dict(params)
    params['api_key'] = API_KEY
    url = API_BASE + path + '?' + urllib.parse.urlencode(params)
    time.sleep(SLEEP)
    try:
        with urllib.request.urlopen(url, timeout=CFG['fec_api']['request_timeout_seconds']) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f'FEC API {path} failed: HTTP {e.code} {e.reason} (url {url})')


def principal_committees(candidate_id, cycle=2026):
    """Principal campaign committee IDs (designation P) for a candidate."""
    data = api_get(f'/candidate/{candidate_id}/committees/',
                   {'cycle': cycle, 'per_page': 100})
    return [c['committee_id'] for c in data.get('results', [])
            if c.get('designation') == 'P']


def totals_refresh(candidate_id, cycle=2026):
    """Latest processed totals for one candidate/cycle, with coverage.

    Returns the per-cycle row (cycle == requested) with its
    coverage_end_date, plus a flag for whether it is newer than bulk.
    election_full=true is NOT used here: it returns only the aggregate
    row (cycle null), which conflates 2024 and 2026.
    """
    data = api_get(f'/candidate/{candidate_id}/totals/',
                   {'cycle': cycle, 'per_page': 100})
    rows = [r for r in data.get('results', []) if r.get('cycle') == cycle]
    if not rows:
        return {'candidate_id': candidate_id, 'cycle': cycle, 'found': False}
    row = rows[0]
    coverage_end = row.get('coverage_end_date')
    # coverage_end_date comes back as a timestamp ('2026-10-14T00:00:00');
    # compare the date part only, or the longer string always wins.
    coverage_date = (coverage_end or '')[:10]
    return {
        'candidate_id': candidate_id, 'cycle': cycle, 'found': True,
        'coverage_end_date': coverage_end,
        'newer_than_bulk': bool(coverage_date and coverage_date > BULK_WEBALL_END),
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


def refresh_person(person, f24_committees):
    """Run all three legs for one roster person. Returns the snapshot entry."""
    entry = {'person_key': person['person_key'], 'full_name': person['full_name'],
             'fec_candidate_ids': person.get('fec_candidate_ids'),
             'totals': [], 'f6': [], 'f24': []}
    for cid in person.get('fec_candidate_ids') or []:
        entry['totals'].append(totals_refresh(cid))
        for cmte in principal_committees(cid):
            entry['f6'].append(pull_f6.pull_committee(cmte, since=WINDOW_START))
    for cmte in f24_committees:
        for cid in person.get('fec_candidate_ids') or []:
            entry['f24'].append(pull_f24.sweep(cmte, cid))
    return entry


def summarize(entries):
    loans = round(sum(f.get('total_candidate_loans', 0) for e in entries
                      for f in e['f6']), 2)
    contrib = round(sum(f.get('total_contributions', 0) for e in entries
                        for f in e['f6']), 2)
    ie = round(sum(s.get('f24_total', 0) for e in entries for s in e['f24']), 2)
    residuals = [{'person_key': e['person_key'],
                  'committee_id': s.get('committee_id'),
                  'candidate_id': s.get('candidate_id'),
                  'residual': s.get('residual')}
                 for e in entries for s in e['f24'] if s.get('residual')]
    newer = [t['candidate_id'] for e in entries for t in e['totals']
             if t.get('newer_than_bulk')]
    return {'n_persons': len(entries), 'new_f6_candidate_loans': loans,
            'new_f6_contributions': contrib, 'new_f24_ie': ie,
            'open_f24_residuals': residuals,
            'totals_newer_than_bulk': newer}


def main():
    ap = argparse.ArgumentParser(description='Freshness refresh driver.')
    ap.add_argument('--person', action='append', default=[],
                    help='roster person_key to refresh (repeatable)')
    ap.add_argument('--all', action='store_true',
                    help='refresh every roster person (registered key required)')
    ap.add_argument('--f24-committee', action='append', default=[],
                    help='spender committee ID for the F24 sweeps (repeatable)')
    ap.add_argument('--f24-candidate', action='append', default=[],
                    help='roster person_key as F24 target (repeatable; '
                         'defaults to the --person list)')
    ap.add_argument('--out', default=None,
                    help='snapshot path (default work/freshness_snapshot.json)')
    args = ap.parse_args()
    if args.all and API_KEY == CFG['fec_api']['api_key_default']:
        sys.exit('ERROR: --all needs a registered api.data.gov key '
                 '(FEC_API_KEY env var). DEMO_KEY (~30/hr) cannot run '
                 'the ~1,300+ calls a full refresh needs.')
    dataset = json.load(open(ROOT / CFG['paths']['dataset_json']))
    by_key = {r['person_key']: r for r in dataset}
    if args.all:
        persons = dataset
    else:
        if not args.person:
            ap.error('need --person (repeatable) or --all')
        persons = []
        for pk in args.person:
            if pk not in by_key:
                sys.exit(f'ERROR: no roster person {pk!r}')
            persons.append(by_key[pk])
    f24_targets = args.f24_candidate or args.person
    f24_persons = []
    for pk in f24_targets:
        if pk not in by_key:
            sys.exit(f'ERROR: no roster person {pk!r}')
        f24_persons.append(by_key[pk])
    entries = []
    for person in persons:
        cmtes = args.f24_committee if person['person_key'] in f24_targets else []
        entries.append(refresh_person(person, cmtes))
    # F24 sweeps for the explicit target list (which may differ from
    # --person); totals + F6 run for those persons too.
    for person in f24_persons:
        if person['person_key'] in args.person:
            continue
        entries.append(refresh_person(person, args.f24_committee))
    snapshot = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'window_start': WINDOW_START,
        'bulk_coverage': {k: str(v) for k, v in
                          CFG['verification']['coverage_end'].items()},
        'api_key_type': ('demo' if API_KEY == CFG['fec_api']['api_key_default']
                         else 'registered'),
        'cadence_note': ('Final 20 days before an election: daily. '
                         'Cycle in progress outside final 20 days: weekly. '
                         'After each deadline: event-driven. Reconcile '
                         'against the next bulk re-pull; never blend into '
                         'the dataset totals.'),
        'entries': entries,
        'summary': summarize(entries),
    }
    out = args.out or str(ROOT / 'work' / 'freshness_snapshot.json')
    with open(out, 'w') as f:
        json.dump(snapshot, f, indent=1)
    s = snapshot['summary']
    print(f'wrote {out}')
    print(f"freshness: {s['n_persons']} person(s); "
          f"F6 candidate loans ${s['new_f6_candidate_loans']:,.2f}, "
          f"F6 contributions ${s['new_f6_contributions']:,.2f}, "
          f"F24 IE ${s['new_f24_ie']:,.2f}; "
          f"totals newer than bulk: {s['totals_newer_than_bulk'] or 'none'}; "
          f"open F24 residuals: {s['open_f24_residuals'] or 'none'}")


if __name__ == '__main__':
    main()

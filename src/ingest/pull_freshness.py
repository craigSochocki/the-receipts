#!/usr/bin/env python3
"""Freshness refresh driver: new money since bulk coverage (Oct 14).

Runs the three freshness legs for a set of roster persons and writes
data/intermediate/freshness_snapshot.json — new money found since bulk
coverage, labeled by source and date, NEVER merged into the dataset totals.
See methodology.md §16 and research/freshness-research.md.

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
   reconciliation and residual rows. With --all, the driver ALSO runs
   committee-only sweeps for the six spender committees listed in
   config.yaml (freshness.f24_committee_sweep), cycle 2026 only — one
   sweep per committee, attributed to roster people by candidate_id
   (rows for non-roster candidates are summed separately, never
   attributed to anyone). See sweep_committee_f24().

Committee IDs come from /v1/candidate/{id}/committees/?cycle=2026
(designation P = principal campaign committee).

Usage:
    # Limited spot check (DEMO_KEY-friendly, ~5 calls):
    python3 src/ingest/pull_freshness.py --person anthonyconstantinonyhouse \\
        --f24-committee C00799031 --f24-candidate abdulelsayedmisenate
    # Committee sweeps only, no per-person refresh (registered key
    # required — DEMO_KEY is refused; see the guard below):
    python3 src/ingest/pull_freshness.py --f24-committee-sweep
    # Full refresh (registered key REQUIRED — ~2,200-2,350 keyed API calls):
    FEC_API_KEY=<registered key> python3 src/ingest/pull_freshness.py --all

Pre-flight gate (src/ingest/pull_gate.py, default with --all): before
the per-person legs, one global /filings/ check per family (F6, F24,
F3) decides who gets refreshed — legs run only for people (or sweep
committees) with new filings since the last run, and the snapshot is
still written when the gate skips everything (n_persons=0, gate-only).
State lives in data/source/freshness_state.json (committed). A gate
error NEVER reads as "nothing new": it logs loudly and falls back to
the full run. --no-gate forces the full run, ignoring the gate.
--person runs and --f24-committee-sweep are explicit requests and are
not gated; the gate applies to --all only.

Call count for --all (recounted Nov 12, 2026; the old "~1,300+" predates
the sweeps and undercounted the per-person legs). Per-person legs, for
the 664 roster persons' 754 candidate IDs: 754 candidate-totals calls
+ 754 committee-lookup calls = 1,508, plus one F6 discovery call per
principal campaign committee (~664-754 keyed calls; the docquery CSV
fetches that follow need no key and are not counted here). Committee
sweeps: 6 committees x 2 paginated fetches each (F24-only + unfiltered
reconciliation) = 12 calls minimum; upper bound 94, from each
committee's 2026 bulk IE row count at 100 rows/page (18+5+19+1+2+2
pages per fetch x 2) — realistically near the low end, since F24 rows
are a small subset of a committee's IE rows (the candidate-scoped
UDP-vs-El-Sayed sweep was 2 calls for 34 rows; the committee-wide UDP
sweep is ~6). Total: ~2,200-2,350 keyed API calls. At the 1.0 s
effective sleep that is ~37-39 min of sleep alone; a realistic --all
run is ~45-60+ min. The scheduled workflow allows 90 min, ~1.5x
headroom.

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
from datetime import datetime, timezone

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.ingest import pull_f24, pull_f6, pull_gate
from src.common.api_retry import open_with_retry, retry_settings, sanitize_url
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
API_KEY = os.environ.get(CFG['fec_api']['api_key_env'], CFG['fec_api']['api_key_default'])
API_BASE = 'https://api.open.fec.gov/v1'
SLEEP = max(CFG['fec_api']['sleep_between_requests_seconds'], 1.0)
RETRY = retry_settings(CFG)
WINDOW_START = CFG['verification']['coverage_end']['freshness_window_start']
BULK_WEBALL_END = str(CFG['verification']['coverage_end']['weball'])
F24_SWEEP_CYCLE = CFG['freshness']['f24_committee_sweep_cycle']
F24_SWEEP_COMMITTEES = CFG['freshness']['f24_committee_sweep']


def api_get(path, params):
    params = dict(params)
    params['api_key'] = API_KEY
    url = API_BASE + path + '?' + urllib.parse.urlencode(params)
    time.sleep(SLEEP)
    try:
        with open_with_retry(url, timeout=CFG['fec_api']['request_timeout_seconds'],
                             retry=RETRY, label=f'FEC API {path}') as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f'FEC API {path} failed: HTTP {e.code} {e.reason} (url {sanitize_url(url)})')


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


def attribute_f24_rows(rows, by_candidate):
    """Attribute F24 rows to roster people by candidate_id.

    by_candidate maps FEC candidate ID -> roster person dict (built from
    the dataset; candidate IDs are unique across roster persons).
    Returns (attributed, non_roster, unclassified_total,
    unclassified_n_rows), where attributed is one dict per roster person
    with >= 1 row ({person_key, candidate_id, support, oppose,
    unclassified, total, n_rows}) and non_roster is {support, oppose,
    unclassified, total, n_rows} for rows whose candidate_id is not on
    the roster (blank candidate_id included). Support/oppose split uses
    the API row's support_oppose_indicator ('S'/'O'); rows with any
    other indicator are summed as unclassified, never folded into
    support/oppose — so f24_total == support + oppose + unclassified
    and == sum(attributed totals) + non_roster total, exactly.
    """
    per_person = {}
    non_roster = {'support': 0.0, 'oppose': 0.0, 'unclassified': 0.0,
                  'total': 0.0, 'n_rows': 0}
    unclassified_total = 0.0
    unclassified_n = 0
    for r in rows:
        amt = float(r.get('expenditure_amount') or 0)
        ind = r.get('support_oppose_indicator')
        cid = r.get('candidate_id')
        person = by_candidate.get(cid) if cid else None
        if person is None:
            bucket = non_roster
        else:
            bucket = per_person.setdefault(
                cid, {'person_key': person['person_key'], 'candidate_id': cid,
                      'support': 0.0, 'oppose': 0.0, 'unclassified': 0.0,
                      'total': 0.0, 'n_rows': 0})
        if ind == 'S':
            bucket['support'] += amt
        elif ind == 'O':
            bucket['oppose'] += amt
        else:
            bucket['unclassified'] += amt
            unclassified_total += amt
            unclassified_n += 1
        bucket['total'] += amt
        bucket['n_rows'] += 1
    attributed = []
    for cid in sorted(per_person):
        b = per_person[cid]
        attributed.append({
            'person_key': b['person_key'], 'candidate_id': cid,
            'support': round(b['support'], 2), 'oppose': round(b['oppose'], 2),
            'unclassified': round(b['unclassified'], 2),
            'total': round(b['total'], 2), 'n_rows': b['n_rows']})
    non_roster = {k: (round(v, 2) if isinstance(v, float) else v)
                  for k, v in non_roster.items()}
    return attributed, non_roster, round(unclassified_total, 2), unclassified_n


def sweep_committee_f24(committee_id, committee_name, cycle, by_candidate):
    """One committee-only F24 sweep (cycle 2026), attributed to the roster.

    Reuses pull_f24.sweep(committee_id, candidate_id=None, cycle) — the
    F24-only fetch, the deduped reconciliation and the residual
    classification live there, not here. Raw rows are NOT embedded in
    the snapshot (a committee sweep can run to thousands of rows); the
    attribution aggregates below are the record, reproducible with
    pull_f24.py --committee <id> --cycle 2026. The sweep total is an
    overlay: labeled by source and date, never merged into dataset totals.
    """
    result = pull_f24.sweep(committee_id, candidate_id=None, cycle=cycle)
    rows = result.get('f24_rows') or []
    attributed, non_roster, unc_total, unc_n = attribute_f24_rows(
        rows, by_candidate)
    support = round(sum(a['support'] for a in attributed)
                    + non_roster['support'], 2)
    oppose = round(sum(a['oppose'] for a in attributed)
                   + non_roster['oppose'], 2)
    return {
        'committee_id': committee_id, 'committee_name': committee_name,
        'cycle': cycle,
        'f24_n_rows': result['f24_n_rows'],
        'f24_total': result['f24_total'],
        'support': support, 'oppose': oppose,
        'unclassified_total': unc_total, 'unclassified_n_rows': unc_n,
        'latest_expenditure_date': result['latest_expenditure_date'],
        'residual_unexplained': result['residual_unexplained'],
        'residual_explained': result['residual_explained'],
        'attributed': attributed,
        'non_roster_total': non_roster['total'],
        'non_roster_n_rows': non_roster['n_rows'],
    }


def snapshot_gate_record(decision):
    """Gate decision as embedded in the snapshot: the full new_filings
    rows (whole API rows) are replaced by their file_numbers, so the
    snapshot stays a small artifact — the gate's working record is
    the decision itself (see pull_gate.gate_run)."""
    if not decision:
        return {'gated': False, 'reason': 'gate did not run',
                'gate_error': None}
    rec = {k: v for k, v in decision.items() if k != 'new_state'}
    fams = {}
    for fam, r in decision.get('families', {}).items():
        fams[fam] = {k: v for k, v in r.items() if k != 'new_filings'}
        fams[fam]['new_filing_file_numbers'] = [
            f.get('file_number') for f in r.get('new_filings', [])]
    rec['families'] = fams
    return rec


def gate_summary_fields(gate):
    """Gate fields for summarize(): a stable shape whether or not a
    gate ran. A gate that ran and failed (gate_error set, full run
    taken) still counts as applied — it spent gate calls."""
    if not gate or not gate.get('gated'):
        return {'gate_applied': False, 'gate_calls_used': 0,
                'gate_skipped_all': False, 'gate_affected_persons': 0,
                'gate_error': (gate or {}).get('gate_error')}
    return {'gate_applied': True, 'gate_calls_used': gate.get('calls_used', 0),
            'gate_skipped_all': bool(gate.get('all_skipped')),
            'gate_affected_persons': len(
                gate.get('affected_person_keys') or []),
            'gate_error': gate.get('gate_error')}


def summarize(entries, committee_sweeps=None, gate=None):
    loans = round(sum(f.get('total_candidate_loans', 0) for e in entries
                      for f in e['f6']), 2)
    contrib = round(sum(f.get('total_contributions', 0) for e in entries
                        for f in e['f6']), 2)
    ie = round(sum(s.get('f24_total', 0) for e in entries for s in e['f24']), 2)
    residuals = [{'person_key': e['person_key'],
                  'committee_id': s.get('committee_id'),
                  'candidate_id': s.get('candidate_id'),
                  'residual_unexplained': s.get('residual_unexplained')}
                 for e in entries for s in e['f24']
                 if s.get('residual_unexplained')]
    newer = [t['candidate_id'] for e in entries for t in e['totals']
             if t.get('newer_than_bulk')]
    out = {'n_persons': len(entries), 'new_f6_candidate_loans': loans,
           'new_f6_contributions': contrib, 'new_f24_ie': ie,
           'open_f24_residuals': residuals,
           'totals_newer_than_bulk': newer}
    sweeps = committee_sweeps or []
    out['committee_sweeps_n'] = len(sweeps)
    out['committee_sweeps_f24_ie'] = round(
        sum(s.get('f24_total', 0) for s in sweeps), 2)
    out['committee_sweeps_by_committee'] = [
        {'committee_id': s.get('committee_id'),
         'committee_name': s.get('committee_name'),
         'f24_total': s.get('f24_total'),
         'f24_n_rows': s.get('f24_n_rows')} for s in sweeps]
    out['committee_sweeps_open_residuals'] = [
        {'committee_id': s.get('committee_id'),
         'residual_unexplained': s.get('residual_unexplained')}
        for s in sweeps if s.get('residual_unexplained')]
    out.update(gate_summary_fields(gate))
    return out


def main():
    ap = argparse.ArgumentParser(description='Freshness refresh driver.')
    ap.add_argument('--person', action='append', default=[],
                    help='roster person_key to refresh (repeatable)')
    ap.add_argument('--all', action='store_true',
                    help='refresh every roster person (registered key required)')
    ap.add_argument('--no-gate', action='store_true',
                    help='force the full run, ignoring the pre-flight gate '
                         '(default with --all is gated: only legs with new '
                         'filings run — see src/ingest/pull_gate.py)')
    ap.add_argument('--f24-committee', action='append', default=[],
                    help='spender committee ID for the F24 sweeps (repeatable)')
    ap.add_argument('--f24-candidate', action='append', default=[],
                    help='roster person_key as F24 target (repeatable; '
                         'defaults to the --person list)')
    ap.add_argument('--f24-committee-sweep', action='store_true',
                    help='run ONLY the six config-listed committee F24 sweeps '
                         '(cycle 2026), no per-person refresh; registered key '
                         'required — DEMO_KEY is refused (six committee sweeps '
                         'are ~12-94+ keyed calls, production-scale, not a '
                         'spot check). For a DEMO_KEY test use the '
                         'single-committee CLI instead: pull_f24.py '
                         '--committee <id> --cycle 2026.')
    ap.add_argument('--out', default=None,
                    help='snapshot path (default data/intermediate/freshness_snapshot.json)')
    args = ap.parse_args()
    if args.all and API_KEY == CFG['fec_api']['api_key_default']:
        sys.exit('ERROR: --all needs a registered api.data.gov key '
                 '(FEC_API_KEY env var). DEMO_KEY (~30/hr) cannot run '
                 'the ~2,200-2,350 calls a full refresh needs.')
    dataset = json.load(open(ROOT / CFG['paths']['dataset_json']))
    by_key = {r['person_key']: r for r in dataset}
    by_candidate = {cid: r for r in dataset
                    for cid in (r.get('fec_candidate_ids') or [])}
    if args.f24_committee_sweep and API_KEY == CFG['fec_api']['api_key_default']:
        sys.exit('ERROR: --f24-committee-sweep needs a registered api.data.gov key '
                 '(FEC_API_KEY env var). DEMO_KEY (~30/hr) cannot run '
                 'the six committee sweeps (~12-94+ keyed calls). '
                 'Single-committee spot check instead: '
                 'python3 src/ingest/pull_f24.py --committee <id> --cycle 2026.')
    if args.f24_committee_sweep:
        # Standalone mode: sweeps only, no per-person refresh.
        sweeps = [sweep_committee_f24(c['committee_id'], c['committee_name'],
                                      F24_SWEEP_CYCLE, by_candidate)
                  for c in F24_SWEEP_COMMITTEES]
        entries = []
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
            'committee_sweeps': sweeps,
            'gate': {'gated': False,
                     'reason': '--f24-committee-sweep mode: the gate '
                               'applies to --all only',
                     'gate_error': None},
            'gate_error': None,
            'summary': summarize(entries, sweeps),
        }
        out = args.out or str(ROOT / CFG['paths']['freshness_snapshot'])
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, 'w') as f:
            json.dump(snapshot, f, indent=1)
        s = snapshot['summary']
        print(f'wrote {out}')
        print(f"committee F24 sweeps: {s['committee_sweeps_n']} committee(s); "
              f"F24 IE ${s['committee_sweeps_f24_ie']:,.2f}; "
              f"open sweep residuals: {s['committee_sweeps_open_residuals'] or 'none'}")
        return
    gate_decision = None
    use_gate = args.all and not args.no_gate
    if use_gate:
        # Pre-flight gate (src/ingest/pull_gate.py): one global
        # /filings/ check per family, then legs only for affected
        # people / sweep committees. A gate error returns run_full —
        # the full run below, never a skip.
        gate_decision = pull_gate.gate_run(dataset, by_candidate)
        if gate_decision['run_full']:
            print('GATE ERROR — falling back to the FULL freshness run '
                  '(see gate_error in the snapshot); state NOT advanced.',
                  file=sys.stderr, flush=True)
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
    if use_gate and not gate_decision['run_full']:
        # Gated --all: run each leg ONLY for the people the gate
        # found new activity for (leg-level, not person-level — a
        # person with only a new F6 gets the F6 leg, not a totals
        # call). Entries list only the legs that ran; 'gate_legs_run'
        # records which. The six-committee sweeps run only for
        # committees with new F24 filings.
        entries = []
        for pk in gate_decision['affected_person_keys']:
            person = by_key[pk]
            entry = {'person_key': pk, 'full_name': person['full_name'],
                     'fec_candidate_ids': person.get('fec_candidate_ids'),
                     'totals': [], 'f6': [], 'f24': []}
            legs = []
            if pk in gate_decision['totals_person_keys']:
                legs.append('totals')
                for cid in person.get('fec_candidate_ids') or []:
                    entry['totals'].append(totals_refresh(cid))
            if pk in gate_decision['f6_person_keys']:
                legs.append('f6')
                for cid in person.get('fec_candidate_ids') or []:
                    for cmte in principal_committees(cid):
                        entry['f6'].append(
                            pull_f6.pull_committee(cmte, since=WINDOW_START))
            entry['gate_legs_run'] = legs
            entries.append(entry)
        sweeps = [sweep_committee_f24(c['committee_id'], c['committee_name'],
                                      F24_SWEEP_CYCLE, by_candidate)
                  for c in gate_decision['f24_sweep_committees']]
    else:
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
        # Committee-only F24 sweeps (cycle 2026): run with --all so the
        # scheduled refresh covers the F24 leg. No workflow flag change —
        # the workflow already runs bare --all.
        sweeps = []
        if args.all:
            sweeps = [sweep_committee_f24(c['committee_id'], c['committee_name'],
                                          F24_SWEEP_CYCLE, by_candidate)
                      for c in F24_SWEEP_COMMITTEES]
        if not use_gate:
            gate_decision = {
                'gated': False,
                'reason': ('--no-gate: full run forced'
                           if args.no_gate else
                           'explicit --person mode: the gate applies '
                           'to --all only'),
                'gate_error': None}
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
        'committee_sweeps': sweeps,
        'gate': snapshot_gate_record(gate_decision),
        'gate_error': gate_decision.get('gate_error'),
        'summary': summarize(entries, sweeps, gate=gate_decision),
    }
    out = args.out or str(ROOT / CFG['paths']['freshness_snapshot'])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(snapshot, f, indent=1)
    if use_gate and not gate_decision['run_full'] \
            and not gate_decision['all_skipped']:
        # Advance the gate state only after a gated run completes.
        # A skipped run leaves state unchanged (nothing new to
        # record); a gate-error run never reaches here (run_full).
        new_state = gate_decision.get('new_state')
        if new_state is not None:
            try:
                pull_gate.save_state(new_state)
            except Exception as e:
                print(f'WARNING: could not save freshness state: {e} — '
                      f'next run re-gates from the previous state.',
                      file=sys.stderr, flush=True)
    s = snapshot['summary']
    print(f'wrote {out}')
    print(f"freshness: {s['n_persons']} person(s); "
          f"F6 candidate loans ${s['new_f6_candidate_loans']:,.2f}, "
          f"F6 contributions ${s['new_f6_contributions']:,.2f}, "
          f"F24 IE ${s['new_f24_ie']:,.2f}; "
          f"totals newer than bulk: {s['totals_newer_than_bulk'] or 'none'}; "
          f"open F24 residuals: {s['open_f24_residuals'] or 'none'}; "
          f"committee F24 sweeps: {s['committee_sweeps_n']} committee(s), "
          f"${s['committee_sweeps_f24_ie']:,.2f}")
    if use_gate:
        print(f"gate: {s['gate_calls_used']} calls; affected persons: "
              f"{s['gate_affected_persons']}; skipped all: "
              f"{s['gate_skipped_all']}; gate error: "
              f"{s['gate_error'] or 'none'}")


if __name__ == '__main__':
    main()

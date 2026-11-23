#!/usr/bin/env python3
"""FEC freshness pre-flight gate: skip legs with nothing new to find.

One global ``/v1/filings/`` check per form family (``config.yaml``
``freshness.gate.families``) decides which freshness legs
``pull_freshness.py --all`` runs: F6 gates the Form 6 leg, F24 the six
committee F24 sweeps, F3 the candidate-totals leg. The rules — why F3X
is not a family, the boundary-day re-scan, the seeding, the known
limits — are in methodology.md §16.

FEC quirks the code relies on (verified live Nov 12, 2026):

* ``min_date`` is silently ignored on ``/v1/filings/``, so the scan
  pages ``sort=-receipt_date`` and stops client-side.
* ``/filings/`` rows carry ``candidate_id: null``, so a filing reaches a
  roster person through the bulk committee master's CAND_ID.
* An F24 filer is the spending committee itself; it needs no map.

Safety property: a gate error is never "nothing new". Any failure —
429 exhaustion, network error, unexpected response shape, page guard,
missing committee master — returns ``run_full=True`` with
``gate_error`` set and no ``new_state``; the driver runs everything and
does not advance ``data/source/freshness_state.json``.

Usage:
    python3 receipts/ingest/pull_gate.py [--families F6 F3] [--out decision.json]
    # dry run: prints the decision JSON; the driver gates --all by default.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from itertools import takewhile
from pathlib import Path

from receipts.common.config import load_config
from receipts.common.fec_api import fec_api
from receipts.common.files import read_json
from receipts.fec.committees import committees

CFG = load_config()
ROOT = CFG['_root']
WINDOW_START = CFG['verification']['coverage_end']['freshness_window_start']
GATE_CFG = CFG['freshness']['gate']
GATE_FAMILIES = GATE_CFG['families']
GATE_PER_PAGE = int(GATE_CFG['per_page'])
GATE_MAX_PAGES = int(GATE_CFG['max_pages_per_family'])
COMMITTEE_MASTER_CYCLE = GATE_CFG['committee_master_cycle']
STATE_PATH = ROOT / CFG['paths']['freshness_state']
F24_SWEEP_COMMITTEES = CFG['freshness']['f24_committee_sweep']
CANDIDATE_FAMILIES = ('F6', 'F3')


def receipt_day(row):
    """Date part (YYYY-MM-DD) of a /filings/ row's receipt_date."""
    return (row.get('receipt_date') or '')[:10]


def filings_page(api, form_type, page, per_page):
    data = api.get(
        '/filings/',
        {'form_type': form_type, 'per_page': per_page, 'page': page, 'sort': '-receipt_date'},
    )
    if not isinstance(data, dict) or not isinstance(data.get('results'), list):
        keys = sorted(data.keys()) if isinstance(data, dict) else type(data).__name__
        raise ValueError(
            f'gate {form_type}: unexpected /filings/ response shape '
            f'(keys: {keys}); refusing to read it as "nothing new"'
        )
    return data['results']


def scan_filings(api, form_type, since_date, per_page, max_pages):
    """(rows received on/after since_date newest first, newest receipt day, calls used)."""
    rows, newest = [], None
    for page in range(1, max_pages + 1):
        results = filings_page(api, form_type, page, per_page)
        if not results:
            return rows, newest, page
        newest = newest or receipt_day(results[0]) or None
        in_window = list(takewhile(lambda r: receipt_day(r) >= since_date, results))
        rows.extend(in_window)
        if len(in_window) < len(results) or len(results) < per_page:
            return rows, newest, page
    raise RuntimeError(
        f'gate {form_type}: exceeded max_pages={max_pages} scanning back to {since_date}; '
        'refusing to continue (fall back to a full run)'
    )


def check_family(
    form_type, since_date, seen_file_numbers=(), api=None, per_page=None, max_pages=None
):
    """Global /filings/ check for one form family.

    A filing is new when received after ``since_date``, or on it with a
    file_number not in ``seen_file_numbers`` (the boundary-day re-scan).
    Raises on any failure; the caller treats that as a gate error.
    """
    if not since_date:
        raise ValueError(
            f'gate {form_type}: since_date is required (YYYY-MM-DD); '
            'pass the window start when there is no baseline'
        )
    seen = set(seen_file_numbers or ())
    rows, newest, calls = scan_filings(
        api or fec_api,
        form_type,
        since_date,
        per_page or GATE_PER_PAGE,
        max_pages or GATE_MAX_PAGES,
    )
    new_filings = [
        r
        for r in rows
        if receipt_day(r) > since_date
        or (receipt_day(r) == since_date and r.get('file_number') not in seen)
    ]
    boundary = {
        r.get('file_number')
        for r in rows
        if newest and receipt_day(r) == newest and r.get('file_number') is not None
    }
    return {
        'form_type': form_type,
        'since_date': since_date,
        'newest_seen': newest,
        'new_filings': new_filings,
        'n_new_filings': len(new_filings),
        'calls_used': calls,
        'skipped': not new_filings,
        'boundary_file_numbers': sorted(boundary),
        'n_rows_scanned': len(rows),
    }


def empty_family_state():
    return {'last_seen': None, 'seen_file_numbers': []}


def default_state(families=None):
    """Fresh state: every family at "no baseline" (last_seen null)."""
    return {
        'version': 1,
        'families': {f: empty_family_state() for f in families or GATE_FAMILIES},
    }


def load_state(state_path=None):
    """The committed state file, or a fresh default when absent.

    A present but unreadable or misshapen file raises ValueError: the
    baseline is never silently reset.
    """
    path = Path(state_path) if state_path else STATE_PATH
    if not path.exists():
        return default_state()
    try:
        state = read_json(path)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(
            f'freshness state file {path} is not readable '
            f'as JSON ({e}); refusing to reset the baseline'
        ) from e
    if not isinstance(state, dict) or not isinstance(state.get('families'), dict):
        raise ValueError(
            f'freshness state file {path} has an unexpected '
            'shape (need {"families": {...}}); refusing to '
            'reset the baseline'
        )
    for fam in GATE_FAMILIES:
        entry = state['families'].get(fam)
        if isinstance(entry, dict):
            entry.setdefault('last_seen', None)
            entry.setdefault('seen_file_numbers', [])
        else:
            state['families'][fam] = empty_family_state()
    return state


def save_state(state, state_path=None):
    path = Path(state_path) if state_path else STATE_PATH
    os.makedirs(path.parent, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(state, f, indent=1)


def advanced_family_state(family_state, since, result):
    """The family's state after this check: moved to the newest day seen, if any."""
    newest = result['newest_seen']
    if newest is None or newest < since:
        return {
            'last_seen': family_state.get('last_seen'),
            'seen_file_numbers': list(family_state.get('seen_file_numbers') or []),
        }
    return {'last_seen': newest, 'seen_file_numbers': result['boundary_file_numbers']}


def load_committee_map(bulk_dir=None, cycle=COMMITTEE_MASTER_CYCLE):
    """{committee_id: {candidate_id, designation}} from the staged committee master, and stats.

    A missing file raises: with no attribution source, no leg may be skipped.
    """
    master = committees(Path(bulk_dir) if bulk_dir else ROOT / CFG['paths']['bulk'], cycle)
    if not master.path.exists():
        raise FileNotFoundError(
            f'gate attribution: committee master not found at {master.path} '
            '(run ./fetch_snapshot.sh); cannot attribute filings, so no leg may be skipped'
        )
    cmap = {
        c.committee_id: {'candidate_id': c.candidate_id or None, 'designation': c.designation}
        for c in master
        if c.committee_id
    }
    return cmap, {'source': str(master.path), 'n_committees': len(cmap)}


class CommitteeMap:
    """The committee master, read on first use (only F6 and F3 need it)."""

    def __init__(self, entries=None):
        self._entries = entries
        self.stats = None

    @property
    def entries(self):
        if self._entries is None:
            self._entries, self.stats = load_committee_map()
        return self._entries


def map_filing_to_person(row, committee_map, by_candidate):
    """(roster person_key, None) for one /filings/ row, or (None, reason).

    Reasons: 'unknown_committee', 'no_candidate_id' (e.g. a PAC),
    'candidate_not_on_roster'.
    """
    cmte = row.get('committee_id')
    entry = committee_map.get(cmte) if cmte else None
    if entry is None:
        return None, 'unknown_committee'
    cid = entry.get('candidate_id')
    if not cid:
        return None, 'no_candidate_id'
    person = by_candidate.get(cid)
    if person is None:
        return None, 'candidate_not_on_roster'
    return person['person_key'], None


def sweep_committees():
    return [
        {'committee_id': c['committee_id'], 'committee_name': c['committee_name']}
        for c in F24_SWEEP_COMMITTEES
    ]


class Attribution:
    """Who the new filings belong to: roster people per leg, sweep committees, the rest."""

    def __init__(self, by_candidate, sweep):
        self.by_candidate = by_candidate
        self.sweep = sweep
        self.sweep_ids = {c['committee_id'] for c in sweep}
        self.person_keys = {fam: set() for fam in CANDIDATE_FAMILIES}
        self.sweep_hits = set()
        self.non_sweep = {}
        self.unattributed = []
        self.non_principal = []

    def add(self, family, filings, committee_map):
        if family in CANDIDATE_FAMILIES:
            cmap = committee_map.entries
            for row in filings:
                self.add_candidate_filing(family, row, cmap)
        elif family == 'F24':
            for row in filings:
                self.add_f24_filing(row)

    def add_candidate_filing(self, family, row, cmap):
        committee = cmap.get(row.get('committee_id')) or {}
        designation = committee.get('designation')
        filing = {
            'form_type': family,
            'file_number': row.get('file_number'),
            'committee_id': row.get('committee_id'),
            'receipt_date': row.get('receipt_date'),
        }
        if designation and designation != 'P':
            self.non_principal.append(
                {
                    **filing,
                    'designation': designation,
                    'candidate_id': committee.get('candidate_id'),
                }
            )
        person_key, reason = map_filing_to_person(row, cmap, self.by_candidate)
        if person_key is None:
            self.unattributed.append({**filing, 'reason': reason})
        else:
            self.person_keys[family].add(person_key)

    def add_f24_filing(self, row):
        cmte = row.get('committee_id')
        if cmte in self.sweep_ids:
            self.sweep_hits.add(cmte)
            return
        bucket = self.non_sweep.setdefault(
            cmte, {'n_filings': 0, 'file_numbers': [], 'latest_receipt_date': None}
        )
        bucket['n_filings'] += 1
        bucket['file_numbers'].append(row.get('file_number'))
        latest, day = bucket['latest_receipt_date'], receipt_day(row)
        bucket['latest_receipt_date'] = day if latest is None else max(latest, day)

    def fill(self, decision):
        f6, totals = self.person_keys['F6'], self.person_keys['F3']
        decision['f6_person_keys'] = sorted(f6)
        decision['totals_person_keys'] = sorted(totals)
        decision['affected_person_keys'] = sorted(f6 | totals)
        decision['f24_sweep_committees'] = [
            c for c in self.sweep if c['committee_id'] in self.sweep_hits
        ]
        decision['f24_sweeps_skipped'] = [
            c for c in self.sweep if c['committee_id'] not in self.sweep_hits
        ]
        decision['non_sweep_f24_committees'] = self.non_sweep
        decision['unattributed_filings'] = self.unattributed
        decision['non_principal_committee_filings'] = self.non_principal


def new_decision():
    return {
        'gated': True,
        'run_full': False,
        'gate_error': None,
        'families': {},
        'affected_person_keys': [],
        'f6_person_keys': [],
        'totals_person_keys': [],
        'f24_sweep_committees': [],
        'f24_sweeps_skipped': [],
        'non_sweep_f24_committees': {},
        'unattributed_filings': [],
        'non_principal_committee_filings': [],
        'calls_used': 0,
        'all_skipped': False,
        'new_state': None,
    }


def candidate_index(dataset):
    return {cid: r for r in dataset for cid in (r.get('fec_candidate_ids') or [])}


def gate_run(
    dataset=None,
    by_candidate=None,
    state=None,
    api=None,
    committee_map=None,
    families=None,
    per_page=None,
    max_pages=None,
):
    """The gate decision over the configured families.

    ``run_full`` with ``gate_error`` set means the gate failed and the
    driver must run everything without saving state. Otherwise
    ``new_state`` is the state to save once the gated run completes.
    """
    families = list(families or GATE_FAMILIES)
    if dataset is None and by_candidate is None:
        dataset = read_json(ROOT / CFG['paths']['dataset_json'])
    if by_candidate is None:
        by_candidate = candidate_index(dataset)
    if state is None:
        state = load_state()
    decision = new_decision()
    attribution = Attribution(by_candidate, sweep_committees())
    cmap = CommitteeMap(committee_map)
    new_families = {}
    family = None
    try:
        for family in families:
            family_state = (state.get('families') or {}).get(family) or {}
            since = family_state.get('last_seen') or WINDOW_START
            result = check_family(
                family,
                since,
                family_state.get('seen_file_numbers') or [],
                api=api,
                per_page=per_page,
                max_pages=max_pages,
            )
            decision['families'][family] = result
            decision['calls_used'] += result['calls_used']
            new_families[family] = advanced_family_state(family_state, since, result)
            attribution.add(family, result['new_filings'], cmap)
    except (Exception, SystemExit) as e:
        return gate_failed(decision, attribution, family or families[0], e)
    attribution.fill(decision)
    decision['all_skipped'] = all(r['skipped'] for r in decision['families'].values())
    decision['new_state'] = {
        **state,
        'families': new_families,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    if cmap.stats is not None:
        decision['committee_map'] = cmap.stats
    return decision


def gate_failed(decision, attribution, family, error):
    print(
        f'GATE ERROR in family {family}: {error} — falling '
        f'back to the FULL freshness run; state NOT advanced.',
        file=sys.stderr,
        flush=True,
    )
    decision['run_full'] = True
    decision['gate_error'] = {'family': family, 'error': str(error)}
    attribution.fill(decision)
    return decision


def describe(decision):
    families = ', '.join(
        f'{fam}: {"SKIP" if r["skipped"] else str(r["n_new_filings"]) + " new"} '
        f'(newest {r["newest_seen"]}, {r["calls_used"]} calls)'
        for fam, r in decision['families'].items()
    )
    sweeps = [c['committee_id'] for c in decision['f24_sweep_committees']]
    return (
        f'gate: {families}; affected persons: '
        f'{decision["affected_person_keys"] or "none"}; '
        f'F24 sweeps to run: {sweeps or "none"}; '
        f'total gate calls: {decision["calls_used"]}'
    )


def main():
    ap = argparse.ArgumentParser(
        description='Freshness pre-flight gate (dry run): global '
        '/filings/ check per family; prints the decision JSON.'
    )
    ap.add_argument(
        '--families',
        nargs='+',
        default=None,
        help='form families to check (default: config gate.families)',
    )
    ap.add_argument('--out', default=None, help='write the decision JSON here (default: stdout)')
    args = ap.parse_args()
    decision = gate_run(families=args.families)
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(decision, f, indent=1)
        print(f'wrote {args.out}')
    else:
        json.dump(decision, sys.stdout, indent=1)
        print()
    print(describe(decision), file=sys.stderr)


if __name__ == '__main__':
    main()

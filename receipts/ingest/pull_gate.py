#!/usr/bin/env python3
"""Freshness gate: skip legs with nothing new; a gate error means a full run, never a skip."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from receipts.common.fec_api import client, receipt_day, scan_filings
from receipts.common.files import emit_json, read_json
from receipts.common.settings import settings
from receipts.fec.committees import committees

CANDIDATE_FAMILIES = ('F6', 'F3')


def gate_settings():
    return settings().freshness.gate


def check_family(
    form_type, since_date, seen_file_numbers=(), api=None, per_page=None, max_pages=None
):
    """One family's new filings: after `since_date`, or on it with an unseen file number."""
    if not since_date:
        raise ValueError(
            f'gate {form_type}: since_date is required (YYYY-MM-DD); '
            'pass the window start when there is no baseline'
        )
    seen = set(seen_file_numbers or ())
    rows, newest, calls = scan_filings(
        api or client(),
        form_type,
        since_date,
        per_page or gate_settings().per_page,
        max_pages or gate_settings().max_pages_per_family,
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
        'families': {f: empty_family_state() for f in families or gate_settings().families},
    }


def load_state(state_path=None):
    """The committed gate state, or a fresh default; an unreadable file raises, never resets."""
    path = Path(state_path) if state_path else settings().paths.freshness_state
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
    for fam in gate_settings().families:
        entry = state['families'].get(fam)
        if isinstance(entry, dict):
            entry.setdefault('last_seen', None)
            entry.setdefault('seen_file_numbers', [])
        else:
            state['families'][fam] = empty_family_state()
    return state


def save_state(state, state_path=None):
    path = Path(state_path) if state_path else settings().paths.freshness_state
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


def load_committee_map(bulk_dir=None, cycle=None):
    """{committee_id: {candidate_id, designation}} from the committee master; missing raises."""
    cycle = cycle or gate_settings().committee_master_cycle
    master = committees(Path(bulk_dir) if bulk_dir else settings().paths.bulk, cycle)
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
    """(person_key, None) for a /filings/ row, or (None, why it maps to nobody)."""
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
        {'committee_id': c.committee_id, 'committee_name': c.committee_name}
        for c in settings().freshness.f24_committee_sweep
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
    """The gate decision; run_full with gate_error set means run everything, save no state."""
    families = list(families or gate_settings().families)
    if dataset is None and by_candidate is None:
        dataset = read_json(settings().paths.dataset_json)
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
            since = (
                family_state.get('last_seen')
                or settings().verification.coverage_end.freshness_window_start
            )
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
    emit_json(decision, args.out)
    print(describe(decision), file=sys.stderr)


if __name__ == '__main__':
    main()

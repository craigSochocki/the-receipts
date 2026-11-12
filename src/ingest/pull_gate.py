#!/usr/bin/env python3
"""FEC freshness pre-flight gate: skip legs with nothing new to find.

A full freshness ``--all`` costs ~2,200-2,350 keyed API calls, most of
which return nothing — 754 candidate IDs x ~3 legs plus six F24
committee sweeps (see ``src/ingest/pull_freshness.py``). The gate runs
ONE global ``/v1/filings/`` check per money-moving form family before
the per-person legs, and the driver then runs each leg ONLY for the
roster people (or sweep committees) the gate found new activity for.

Families (``config.yaml``, ``freshness.gate.families``): F6, F24, F3.

* F6 gates the Form 6 leg (``pull_f6`` per principal committee).
* F24 gates the six committee F24 sweeps (``pull_f24`` committee-wide).
* F3 gates the candidate-totals leg: a new F3 is the report that moves
  a candidate's totals row (``/candidate/{id}/totals/`` coverage_end_date).
* F3X is deliberately NOT a gate family. F3X is filed by non-candidate
  committees (PACs, parties); no freshness leg is driven by F3X
  filings, so gating on it would either skip nothing or gate nothing.
  Verified live Nov 12, 2026 (DEMO_KEY): the global newest filing was
  2026-11-11 in every family (F6, F24, F3, F3X alike).

How a family is checked (``check_family``): ``GET /v1/filings/
?form_type=<F>&sort=-receipt_date&per_page=<N>``, page 1 first (the
newest ``receipt_date``), then paging until a row's ``receipt_date``
falls before the comparison date. ``min_date`` is SILENTLY IGNORED
server-side on ``/v1/filings/`` (asked F6 ``min_date=2026-11-12``, got
count 221,791 starting 2026-11-11), so the filter is client-side,
exactly like ``discover_f6`` in ``pull_f6.py``. The newest filing
overall is NOT a usable tripwire — on Nov 12 it was an F99 (free-text)
and an F2 (candidacy statement), neither of which moves money — hence
one check per family, not one global check.

Attribution costs no API call per roster person. ``/filings/`` rows
carry ``committee_id`` but ``candidate_id`` is null on every row
(verified live Nov 12 for F6, F24, F3 and F3X — the brief's "F6 filing
metadata carries candidate_id" is wrong for this endpoint; the
candidate_id lives in the F6 docquery CSV header, not the API row).
So a new filing maps committee -> candidate through the staged bulk
committee master ``data/raw/cm/2026/cm.txt`` (field 15 = CAND_ID,
field 9 = designation; verified against C00902668 -> S6MI00418,
C00892737 -> H6NY21157, UDP C00799031 -> blank), then candidate ->
roster person through the dataset's ``fec_candidate_ids``. A filing
for a committee with no candidate, or a candidate not on the roster,
is recorded in the decision as unattributed — never crashed on, never
attributed to anyone. F24 filings need no map at all: the filer IS the
spending committee, so a new F24 either names one of the six sweep
committees (run that sweep) or it does not (recorded as a coverage
note, see below).

Boundary-day rule. ``receipt_date`` is when the FEC received a filing,
not when it became visible via the API, so a filing with
``receipt_date == last_seen`` can become visible AFTER the last run.
The gate therefore re-scans the boundary day on every run: the
comparison is ``receipt_date >= last_seen`` (inclusive), and a
boundary-day filing counts as new unless its ``file_number`` is in the
previous run's ``seen_file_numbers`` for that family (stored in the
state file). Assumption, stated plainly: filings become API-visible in
``receipt_date`` order with lag shorter than the run interval
(weekly), so a filing not yet visible at run time has ``receipt_date``
on the boundary day, not an older day. A filing that became visible
more than one run-interval late would be missed by the gate; the
bulk re-pull (mid-Dec post-general, Feb year-end) is the backstop for
that case, as it is for totals-processing lag (see below).

State (``data/source/freshness_state.json``, committed; path in
``config.yaml`` ``paths.freshness_state``). Per family: ``last_seen``
(newest ``receipt_date`` observed) and ``seen_file_numbers`` (the
``file_number``s seen on the boundary day, i.e. with
``receipt_date == last_seen``). Rules: a skipped run leaves state
unchanged; a run that finds activity advances it (``last_seen`` =
newest seen, ``seen_file_numbers`` = that day's file numbers). A
``last_seen`` of null means "no baseline" and is treated as the
freshness window start (``verification.coverage_end.
freshness_window_start``, 2026-10-15): the next run scans the whole
window. Seeding (Nov 12, 2026): every family seeded at 2026-10-15
with an empty seen set — NOT at the Nov 12 evidence snapshot's F6
latest (2026-11-01). The snapshot
(``data/evidence/freshness_snapshot-2026-11-12.json``) covered only
two persons' committees (Constantino C00892737, El-Sayed C00902668),
so it is not a roster-wide baseline: seeding F6 at 2026-11-01 would
falsely claim roster-wide capture through Nov 1 and silently skip
Oct 15-Nov 1 activity for the other 662 people. No full ``--all`` has
ever run, so there is no roster-wide baseline to seed from; the first
gated run scans the whole freshness window and refreshes everyone
with activity since the bulk cutoff. The live global newest
(2026-11-11, verified Nov 12 with DEMO_KEY for F6/F24/F3/F3X) is
"newest seen", not "captured", and is not used as the seed.

Safety property (most important). A gate ERROR is never read as
"nothing new". On any gate query failure — 429 exhaustion after the
shared retry, network error, unexpected response shape, page-guard
trip, missing committee master — the gate logs loudly to stderr and
``gate_run`` returns ``run_full=True`` with ``gate_error`` set, and
the driver falls back to the FULL ``--all`` run. State is not
advanced on a gate error. ``open_with_retry`` handles 429s (see
``src/common/api_retry.py``); the api_key is never logged —
``sanitize_url`` strips it from every error/log URL (commit 28b390f).

F24 coverage note. The global F24 check sees F24 activity from
committees OUTSIDE the six sweeps. That is surfaced in the decision
as ``non_sweep_f24_committees`` (committee_id, filing count, file
numbers, latest receipt_date). The sweep list is NOT silently
expanded and the rows are NOT dropped. The six-committee sweep
behavior itself is unchanged.

Known limitation — totals-processing lag. The F3 gate triggers on a
filing's receipt; if the FEC has not yet processed that report into
the totals endpoint, ``totals_refresh`` sees no new coverage and the
gate will not revisit that candidate unless a newer F3 arrives. The
gate is receipt-driven, not processing-driven; the bulk re-pull is
the backstop. Same for F24: a sweep runs when its F24 filing is
visible in ``/filings/``; if the Schedule E rows are not queryable
yet, the sweep simply finds zero rows that run.

Interface contract (kept stable for the validation harness):
``check_family(form_type, since_date, ...)`` ->
``{form_type, since_date, newest_seen, new_filings, n_new_filings,
calls_used, skipped, boundary_file_numbers, n_rows_scanned}``;
``load_state()`` / ``save_state()`` for the state file;
``gate_run(...)`` -> the gate decision dict (``gated``, ``run_full``,
``gate_error``, per-family records, ``affected_person_keys``,
``f6_person_keys``, ``totals_person_keys``,
``f24_sweep_committees``, ``f24_sweeps_skipped``,
``non_sweep_f24_committees``, ``unattributed_filings``,
``non_principal_committee_filings``, ``calls_used``,
``all_skipped``, ``new_state``).

Usage:
    python3 src/ingest/pull_gate.py [--out decision.json]
    # dry-run the gate only; prints the decision JSON to stdout.
    # The driver (pull_freshness.py --all) runs this by default;
    # --no-gate forces the full run, ignoring the gate.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import zipfile

from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.api_retry import open_with_retry, retry_settings, sanitize_url
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
API_KEY = os.environ.get(CFG['fec_api']['api_key_env'], CFG['fec_api']['api_key_default'])
API_BASE = 'https://api.open.fec.gov/v1'
SLEEP = max(CFG['fec_api']['sleep_between_requests_seconds'], 1.0)
RETRY = retry_settings(CFG)
WINDOW_START = CFG['verification']['coverage_end']['freshness_window_start']
GATE_CFG = (CFG.get('freshness') or {}).get('gate') or {}
GATE_FAMILIES = GATE_CFG.get('families') or ['F6', 'F24', 'F3']
GATE_PER_PAGE = int(GATE_CFG.get('per_page', 100))
GATE_MAX_PAGES = int(GATE_CFG.get('max_pages_per_family', 200))
STATE_PATH = ROOT / (CFG['paths'].get('freshness_state')
                     or 'data/source/freshness_state.json')
CM_PATH = ROOT / (GATE_CFG.get('committee_master_path')
                  or 'data/raw/cm/2026/cm.txt')
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


def _receipt_day(row):
    """Date part (YYYY-MM-DD) of a /filings/ row's receipt_date."""
    return (row.get('receipt_date') or '')[:10]


def check_family(form_type, since_date, seen_file_numbers=(), api_get=None,
                 per_page=None, max_pages=None):
    """Global /filings/ check for one form family.

    ``since_date`` (YYYY-MM-DD, required) is the comparison date: the
    family's ``last_seen`` from the state file, or the freshness
    window start when there is no baseline. Pages
    ``/filings/?form_type=<F>&sort=-receipt_date`` until a row's
    receipt_date falls before ``since_date`` (``min_date`` is ignored
    server-side, so this is client-side, like ``discover_f6``). A
    filing counts as new when its receipt_date is AFTER ``since_date``,
    or ON ``since_date`` with a file_number not in
    ``seen_file_numbers`` (the boundary-day re-scan; see the module
    docstring). Returns the record described in the module docstring.
    Raises on any query failure (``SystemExit`` from ``api_get`` on
    HTTP errors after retry, ``ValueError`` on an unexpected response
    shape, ``RuntimeError`` on the page guard) — the caller must treat
    that as a gate error and fall back to a full run, never as "no
    new filings". ``api_get`` is injectable for testing; it must take
    (path, params) and return the parsed JSON.
    """
    if not since_date:
        raise ValueError(f'gate {form_type}: since_date is required '
                         '(YYYY-MM-DD); pass the window start when '
                         'there is no baseline')
    get = api_get or globals()['api_get']
    per_page = int(per_page or GATE_PER_PAGE)
    max_pages = int(max_pages or GATE_MAX_PAGES)
    seen = set(seen_file_numbers or ())
    collected = []
    newest_seen = None
    calls_used = 0
    page = 1
    while True:
        data = get('/filings/', {'form_type': form_type, 'per_page': per_page,
                                 'page': page, 'sort': '-receipt_date'})
        calls_used += 1
        if not isinstance(data, dict) or not isinstance(data.get('results'), list):
            keys = sorted(data.keys()) if isinstance(data, dict) else type(data).__name__
            raise ValueError(
                f'gate {form_type}: unexpected /filings/ response shape '
                f'(keys: {keys}); refusing to read it as "nothing new"')
        results = data['results']
        if not results:
            break
        if newest_seen is None:
            newest_seen = _receipt_day(results[0]) or None
        stop = False
        for r in results:
            if _receipt_day(r) < since_date:
                stop = True
                break
            collected.append(r)
        if stop or len(results) < per_page:
            break
        page += 1
        if page > max_pages:
            raise RuntimeError(
                f'gate {form_type}: exceeded max_pages={max_pages} '
                f'scanning back to {since_date}; refusing to continue '
                '(fall back to a full run)')
    new_filings = [r for r in collected
                   if _receipt_day(r) > since_date
                   or (_receipt_day(r) == since_date
                       and r.get('file_number') not in seen)]
    boundary_file_numbers = sorted(
        {r.get('file_number') for r in collected
         if newest_seen and _receipt_day(r) == newest_seen
         and r.get('file_number') is not None})
    return {
        'form_type': form_type, 'since_date': since_date,
        'newest_seen': newest_seen, 'new_filings': new_filings,
        'n_new_filings': len(new_filings), 'calls_used': calls_used,
        'skipped': not new_filings,
        'boundary_file_numbers': boundary_file_numbers,
        'n_rows_scanned': len(collected),
    }


def default_state(families=None):
    """Fresh state: every family at "no baseline" (last_seen null)."""
    fams = families or GATE_FAMILIES
    return {'version': 1,
            'families': {f: {'last_seen': None, 'seen_file_numbers': []}
                         for f in fams}}


def load_state(state_path=None):
    """Read the committed state file, or a fresh default when absent.

    A present-but-malformed file (bad JSON, wrong shape) raises
    ValueError — the caller must treat that as a gate error and fall
    back to a full run, never silently reset the baseline. Families
    missing from the file get default (null) entries.
    """
    path = Path(state_path) if state_path else STATE_PATH
    if not path.exists():
        return default_state()
    try:
        state = json.load(open(path))
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f'freshness state file {path} is not readable '
                         f'as JSON ({e}); refusing to reset the baseline')
    if not isinstance(state, dict) or not isinstance(state.get('families'), dict):
        raise ValueError(f'freshness state file {path} has an unexpected '
                         'shape (need {"families": {...}}); refusing to '
                         'reset the baseline')
    for fam in GATE_FAMILIES:
        entry = state['families'].get(fam)
        if not isinstance(entry, dict):
            state['families'][fam] = {'last_seen': None,
                                      'seen_file_numbers': []}
        else:
            entry.setdefault('last_seen', None)
            entry.setdefault('seen_file_numbers', [])
    return state


def save_state(state, state_path=None):
    """Write the state file (creates parent dirs)."""
    path = Path(state_path) if state_path else STATE_PATH
    os.makedirs(path.parent, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(state, f, indent=1)


def load_committee_map(cm_path=None):
    """Committee -> candidate map from the staged committee master.

    Reads ``data/raw/cm/2026/cm.txt`` (15 pipe-delimited fields;
    field 1 = committee_id, field 9 = designation, field 15 =
    candidate_id), falling back to ``cm26.zip`` beside it when the
    extracted file is absent. Returns (map, stats) where map is
    {committee_id: {'candidate_id': str|None, 'designation': str}}
    and stats carries the source path, committee count and malformed
    line count. Raises FileNotFoundError when neither the extracted
    file nor the zip exists — the caller must treat that as a gate
    error (no attribution source, so no leg may be skipped).
    """
    path = Path(cm_path) if cm_path else CM_PATH
    lines = None
    source = str(path)
    if path.exists():
        lines = open(path, errors='replace')
    else:
        cycle_dir = path.parent.name
        zip_path = path.parent.parent / f"cm{cycle_dir[-2:]}.zip"
        if not zip_path.exists():
            raise FileNotFoundError(
                f'gate attribution: committee master not found at '
                f'{path} or {zip_path} (run ./download_bulk.sh); '
                'cannot attribute filings, so no leg may be skipped')
        source = f'{zip_path}!cm.txt'
        lines = (l.decode('utf-8', errors='replace') for l in
                 zipfile.ZipFile(zip_path).open('cm.txt'))
    cmap = {}
    n_bad = 0
    for line in lines:
        p = line.rstrip('\n').split('|')
        if len(p) != 15 or not p[0].strip():
            n_bad += 1
            continue
        cmap[p[0].strip()] = {'candidate_id': p[14].strip() or None,
                              'designation': p[8].strip()}
    stats = {'source': source, 'n_committees': len(cmap),
             'n_malformed_lines': n_bad}
    return cmap, stats


def map_filing_to_person(row, committee_map, by_candidate):
    """Map one /filings/ row to a roster person_key, or (None, reason).

    committee_id -> committee master CAND_ID -> dataset
    fec_candidate_ids. Reasons: 'unknown_committee' (not in the
    master), 'no_candidate_id' (master row has a blank CAND_ID, e.g.
    a PAC), 'candidate_not_on_roster'.
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


def gate_run(dataset=None, by_candidate=None, state=None, api_get=None,
             committee_map=None, families=None, per_page=None,
             max_pages=None):
    """Run the pre-flight gate over the configured families.

    Returns the gate decision dict (see the module docstring). On ANY
    gate failure the decision has ``run_full=True`` and ``gate_error``
    set, and ``new_state`` is None — the driver must then run the
    FULL refresh and must not advance state. A decision with
    ``run_full=False`` means every family was checked successfully;
    ``all_skipped`` means no family found anything new. ``new_state``
    is the state to save AFTER the gated run completes (skipped
    families write back identical values; the driver skips the save
    entirely when ``all_skipped``).
    """
    fams = list(families or GATE_FAMILIES)
    if dataset is None:
        dataset = json.load(open(ROOT / CFG['paths']['dataset_json']))
    if by_candidate is None:
        by_candidate = {cid: r for r in dataset
                        for cid in (r.get('fec_candidate_ids') or [])}
    if state is None:
        state = load_state()
    sweep = [{'committee_id': c['committee_id'],
              'committee_name': c['committee_name']}
             for c in F24_SWEEP_COMMITTEES]
    sweep_ids = {c['committee_id'] for c in sweep}
    decision = {
        'gated': True, 'run_full': False, 'gate_error': None,
        'families': {}, 'affected_person_keys': [],
        'f6_person_keys': [], 'totals_person_keys': [],
        'f24_sweep_committees': [], 'f24_sweeps_skipped': [],
        'non_sweep_f24_committees': {}, 'unattributed_filings': [],
        'non_principal_committee_filings': [], 'calls_used': 0,
        'all_skipped': False, 'new_state': None,
    }
    f6_persons, totals_persons = set(), set()
    f24_sweep_hit = set()
    non_sweep = {}
    unattributed = []
    non_principal = []
    new_families = {}
    cmap_holder = {'map': committee_map, 'stats': None}
    current_family = None

    def get_map():
        if cmap_holder['map'] is None:
            cmap_holder['map'], cmap_holder['stats'] = load_committee_map()
        return cmap_holder['map']

    try:
        for fam in fams:
            current_family = fam
            fam_state = (state.get('families') or {}).get(fam) or {}
            since = fam_state.get('last_seen') or WINDOW_START
            seen = fam_state.get('seen_file_numbers') or []
            result = check_family(fam, since, seen_file_numbers=seen,
                                  api_get=api_get, per_page=per_page,
                                  max_pages=max_pages)
            decision['families'][fam] = result
            decision['calls_used'] += result['calls_used']
            newest = result['newest_seen']
            if newest is None or newest < since:
                new_families[fam] = {'last_seen': fam_state.get('last_seen'),
                                     'seen_file_numbers': list(seen)}
            else:
                new_families[fam] = {
                    'last_seen': newest,
                    'seen_file_numbers': result['boundary_file_numbers']}
            if fam in ('F6', 'F3'):
                target = f6_persons if fam == 'F6' else totals_persons
                cmap = get_map()
                for row in result['new_filings']:
                    person_key, reason = map_filing_to_person(
                        row, cmap, by_candidate)
                    designation = (cmap.get(row.get('committee_id')) or {}
                                   ).get('designation')
                    if designation and designation != 'P':
                        non_principal.append({
                            'form_type': fam,
                            'file_number': row.get('file_number'),
                            'committee_id': row.get('committee_id'),
                            'receipt_date': row.get('receipt_date'),
                            'designation': designation,
                            'candidate_id': (cmap.get(
                                row.get('committee_id')) or {}
                            ).get('candidate_id')})
                    if person_key is None:
                        unattributed.append({
                            'form_type': fam,
                            'file_number': row.get('file_number'),
                            'committee_id': row.get('committee_id'),
                            'receipt_date': row.get('receipt_date'),
                            'reason': reason})
                    else:
                        target.add(person_key)
            elif fam == 'F24':
                for row in result['new_filings']:
                    cmte = row.get('committee_id')
                    if cmte in sweep_ids:
                        f24_sweep_hit.add(cmte)
                    else:
                        bucket = non_sweep.setdefault(
                            cmte, {'n_filings': 0, 'file_numbers': [],
                                   'latest_receipt_date': None})
                        bucket['n_filings'] += 1
                        bucket['file_numbers'].append(row.get('file_number'))
                        rd = _receipt_day(row)
                        if (bucket['latest_receipt_date'] is None
                                or rd > bucket['latest_receipt_date']):
                            bucket['latest_receipt_date'] = rd
    except (Exception, SystemExit) as e:
        # SAFETY PROPERTY: a gate error is never "nothing new".
        # Log loudly; the driver falls back to the FULL run.
        failed_family = current_family or fams[0]
        print(f'GATE ERROR in family {failed_family}: {e} — falling '
              f'back to the FULL freshness run; state NOT advanced.',
              file=sys.stderr, flush=True)
        decision['run_full'] = True
        decision['gate_error'] = {'family': failed_family,
                                  'error': str(e)}
        decision['new_state'] = None
        decision['f6_person_keys'] = sorted(f6_persons)
        decision['totals_person_keys'] = sorted(totals_persons)
        decision['affected_person_keys'] = sorted(
            f6_persons | totals_persons)
        decision['f24_sweep_committees'] = [
            c for c in sweep if c['committee_id'] in f24_sweep_hit]
        decision['f24_sweeps_skipped'] = [
            c for c in sweep if c['committee_id'] not in f24_sweep_hit]
        decision['non_sweep_f24_committees'] = non_sweep
        decision['unattributed_filings'] = unattributed
        decision['non_principal_committee_filings'] = non_principal
        return decision

    decision['f6_person_keys'] = sorted(f6_persons)
    decision['totals_person_keys'] = sorted(totals_persons)
    decision['affected_person_keys'] = sorted(f6_persons | totals_persons)
    decision['f24_sweep_committees'] = [
        c for c in sweep if c['committee_id'] in f24_sweep_hit]
    decision['f24_sweeps_skipped'] = [
        c for c in sweep if c['committee_id'] not in f24_sweep_hit]
    decision['non_sweep_f24_committees'] = non_sweep
    decision['unattributed_filings'] = unattributed
    decision['non_principal_committee_filings'] = non_principal
    decision['all_skipped'] = all(
        r['skipped'] for r in decision['families'].values())
    new_state = dict(state)
    new_state['families'] = new_families
    new_state['updated_at'] = datetime.now(timezone.utc).isoformat()
    decision['new_state'] = new_state
    if cmap_holder['stats'] is not None:
        decision['committee_map'] = cmap_holder['stats']
    return decision


def main():
    ap = argparse.ArgumentParser(
        description='Freshness pre-flight gate (dry run): global '
                    '/filings/ check per family; prints the decision JSON.')
    ap.add_argument('--families', nargs='+', default=None,
                    help='form families to check (default: config gate.families)')
    ap.add_argument('--out', default=None,
                    help='write the decision JSON here (default: stdout)')
    args = ap.parse_args()
    decision = gate_run(families=args.families)
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(decision, f, indent=1)
        print(f"wrote {args.out}")
    else:
        json.dump(decision, sys.stdout, indent=1)
        print()
    fams = ', '.join(
        f"{fam}: {'SKIP' if r['skipped'] else f'{r['n_new_filings']} new'} "
        f"(newest {r['newest_seen']}, {r['calls_used']} calls)"
        for fam, r in decision['families'].items())
    print(f"gate: {fams}; affected persons: "
          f"{decision['affected_person_keys'] or 'none'}; "
          f"F24 sweeps to run: "
          f"{[c['committee_id'] for c in decision['f24_sweep_committees']] or 'none'}; "
          f"total gate calls: {decision['calls_used']}",
          file=sys.stderr)


if __name__ == '__main__':
    main()

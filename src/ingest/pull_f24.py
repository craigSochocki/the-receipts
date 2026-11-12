#!/usr/bin/env python3
"""24/48-hour independent-expenditure freshness pull (Schedule E, F24).

The freshness layer's route to independent expenditures filed in the
last 20 days before an election, before any bulk file carries them
(see research/freshness-research.md §3).

Route: GET /v1/schedules/schedule_e/?filing_form=F24&committee_id=
&candidate_id=&cycle= — with the F24-only filter. The filter matters:
the Schedule E endpoint DOUBLE-RETURNS — the same expenditure appears
once under its original F3X filing and again under the F24 — so the
unfiltered sum roughly doubles the true amount (UDP vs El-Sayed 2026:
naive $41.04M vs true $20.90M). The F24-only sum matches the deduped
sum to within one unexplained $1,004.53 residual row (Nov 12, 2026);
see the reconciliation in this script's output and methodology.md §16.

Form 5 covers only unregistered spenders; registered committees (UDP
included) file zero F5s, so no F5 leg is needed for the roster.

The output is a JSON report only — NEVER merged into the dataset
totals; the freshness driver (src/ingest/pull_freshness.py) folds it into
data/intermediate/freshness_snapshot.json.

Usage:
    python3 src/ingest/pull_f24.py --committee C00799031 --candidate S6MI00418 --cycle 2026
    python3 src/ingest/pull_f24.py --committee C00799031 --cycle 2026   # committee-only sweep

API key: FEC_API_KEY env var, else DEMO_KEY (spot checks only, ~30/hr).
Sleeps >=1s between API calls.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.api_retry import open_with_retry, retry_settings, sanitize_url
from src.common.config import load_config

CFG = load_config()
API_KEY = os.environ.get(CFG['fec_api']['api_key_env'], CFG['fec_api']['api_key_default'])
API_BASE = 'https://api.open.fec.gov/v1'
SLEEP = max(CFG['fec_api']['sleep_between_requests_seconds'], 1.0)
RETRY = retry_settings(CFG)


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


def fetch_schedule_e(committee_id=None, candidate_id=None, cycle=None, filing_form=None):
    """All Schedule E rows matching the filters, paginated.

    Cursor pagination: the Schedule E endpoint IGNORES the `page`
    query parameter and advertises its cursor in
    `pagination.last_indexes` (observed live Nov 12, 2026: keys
    `last_index` + `last_expenditure_date`). The first fetch sends no
    cursor; each later fetch passes the previous response's
    `last_indexes` entries as query params. A page returning fewer
    than `per_page` rows (or zero) ends the sweep. Same-page safety
    net: if a page's rows are identical (by sub_id, falling back to
    the dedup key) to the previous page's, abort with a clear error
    naming the filters — the endpoint is repeating instead of
    advancing, and must never be looped to the page guard.
    """
    rows = []
    cursor = {}
    page = 1
    prev_page_key = None
    while True:
        params = {'per_page': 100}
        params.update(cursor)
        if committee_id:
            params['committee_id'] = committee_id
        if candidate_id:
            params['candidate_id'] = candidate_id
        if cycle:
            params['cycle'] = cycle
        if filing_form:
            params['filing_form'] = filing_form
        data = api_get('/schedules/schedule_e/', params)
        results = data.get('results', [])
        if not results:
            break
        sub_ids = [r.get('sub_id') for r in results]
        page_key = (tuple(sub_ids) if all(s is not None for s in sub_ids)
                    else tuple(dedup_key(r) for r in results))
        if page_key == prev_page_key:
            raise SystemExit(
                'Schedule E sweep: endpoint repeated the same page '
                f'(committee={committee_id} candidate={candidate_id} '
                f'cycle={cycle} filing_form={filing_form} page {page}); '
                'refusing to continue')
        prev_page_key = page_key
        rows.extend(results)
        if len(results) < 100:
            break
        cursor = dict(data.get('pagination', {}).get('last_indexes') or {})
        if not cursor:
            raise SystemExit(
                'Schedule E sweep: full page returned but no '
                'pagination.last_indexes cursor to advance with '
                f'(committee={committee_id} candidate={candidate_id} '
                f'cycle={cycle} filing_form={filing_form} page {page}); '
                'refusing to continue')
        page += 1
        if page > 100:
            raise SystemExit('Schedule E sweep: too many pages (over 100); refusing to continue')
    return rows


def dedup_key(row):
    """The research's dedup key: (expenditure_date, amount, payee)."""
    return (row.get('expenditure_date'), row.get('expenditure_amount'),
            row.get('payee_name'))


def dedup_rows(rows):
    seen = {}
    for r in rows:
        seen.setdefault(dedup_key(r), r)
    return list(seen.values())


def row_sum(rows):
    return round(sum(float(r.get('expenditure_amount') or 0) for r in rows), 2)


def sweep(committee_id=None, candidate_id=None, cycle=None):
    """F24-only sweep + the unfiltered reconciliation.

    Returns a dict with: f24_rows (the trustworthy set), f24_total,
    naive_total (unfiltered S+O rows), deduped_total (unfiltered,
    deduped on date/amount/payee), residual = deduped − F24-only,
    residual_rows (the deduped rows not present in the F24 set), and
    latest_expenditure_date.
    """
    f24_rows = fetch_schedule_e(committee_id, candidate_id, cycle, filing_form='F24')
    all_rows = fetch_schedule_e(committee_id, candidate_id, cycle)
    deduped = dedup_rows(all_rows)
    f24_keys = {dedup_key(r) for r in f24_rows}
    residual_rows = [r for r in deduped if dedup_key(r) not in f24_keys]
    # Residual classification (Nov 12, 2026): a residual row filed on a
    # regular report (filing_form F3X, e.g. the UDP $1,004.53 GOTV
    # expenditure of Aug 3, filed Sep 19 on an M9) is EXPECTED — it
    # predates the 24/48-hour window and was never an F24. Only a
    # residual row whose filing_form IS F24 would be a real
    # discrepancy (the F24-only set should contain every F24 row).
    explained = [r for r in residual_rows if r.get('filing_form') != 'F24']
    unexplained = [r for r in residual_rows if r.get('filing_form') == 'F24']
    return {
        'committee_id': committee_id, 'candidate_id': candidate_id, 'cycle': cycle,
        'f24_n_rows': len(f24_rows),
        'f24_total': row_sum(f24_rows),
        'naive_n_rows': len(all_rows),
        'naive_total': row_sum(all_rows),
        'deduped_n_rows': len(deduped),
        'deduped_total': row_sum(deduped),
        'residual': round(row_sum(deduped) - row_sum(f24_rows), 2),
        'residual_explained': row_sum(explained),
        'residual_unexplained': row_sum(unexplained),
        'residual_rows': residual_rows,
        'latest_expenditure_date': max((r.get('expenditure_date') or ''
                                        for r in f24_rows), default=None),
        'f24_rows': f24_rows,
    }


def main():
    ap = argparse.ArgumentParser(description='F24 (24/48-hour IE) freshness pull.')
    ap.add_argument('--committee', help='spending committee ID (e.g. C00799031 = UDP)')
    ap.add_argument('--candidate', help='target candidate ID (e.g. S6MI00418)')
    ap.add_argument('--cycle', type=int, default=2026, help='election cycle (default 2026)')
    ap.add_argument('--out', default=None, help='write the JSON report here (default: stdout)')
    args = ap.parse_args()
    if not args.committee and not args.candidate:
        ap.error('need --committee and/or --candidate')
    result = sweep(args.committee, args.candidate, args.cycle)
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(result, f, indent=1)
        print(f"wrote {args.out}")
    else:
        json.dump(result, sys.stdout, indent=1)
        print()
    print(f"F24 {args.committee or ''} vs {args.candidate or ''} cycle {args.cycle}: "
          f"{result['f24_n_rows']} rows, ${result['f24_total']:,.2f}; "
          f"naive ${result['naive_total']:,.2f} ({result['naive_n_rows']} rows), "
          f"deduped ${result['deduped_total']:,.2f} ({result['deduped_n_rows']} rows); "
          f"residual ${result['residual']:,.2f} "
          f"(explained ${result['residual_explained']:,.2f} non-F24, "
          f"unexplained ${result['residual_unexplained']:,.2f}); "
          f"latest expenditure {result['latest_expenditure_date']}")


if __name__ == '__main__':
    main()

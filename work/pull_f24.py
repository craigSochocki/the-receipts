#!/usr/bin/env python3
"""24/48-hour independent-expenditure freshness pull (Schedule E, F24).

The freshness layer's route to independent expenditures filed in the
last 20 days before an election, before any bulk file carries them
(see work/freshness-research.md §3).

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
totals; the freshness driver (work/pull_freshness.py) folds it into
work/freshness_snapshot.json.

Usage:
    python3 work/pull_f24.py --committee C00799031 --candidate S6MI00418 --cycle 2026
    python3 work/pull_f24.py --committee C00799031 --cycle 2026   # committee-only sweep

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
import urllib.request

from config import load_config

CFG = load_config()
API_KEY = os.environ.get(CFG['fec_api']['api_key_env'], CFG['fec_api']['api_key_default'])
API_BASE = 'https://api.open.fec.gov/v1'
SLEEP = max(CFG['fec_api']['sleep_between_requests_seconds'], 1.0)


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


def fetch_schedule_e(committee_id=None, candidate_id=None, cycle=None, filing_form=None):
    """All Schedule E rows matching the filters, paginated."""
    rows = []
    page = 1
    while True:
        params = {'per_page': 100, 'page': page}
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
        rows.extend(results)
        if len(results) < 100:
            break
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
    return {
        'committee_id': committee_id, 'candidate_id': candidate_id, 'cycle': cycle,
        'f24_n_rows': len(f24_rows),
        'f24_total': row_sum(f24_rows),
        'naive_n_rows': len(all_rows),
        'naive_total': row_sum(all_rows),
        'deduped_n_rows': len(deduped),
        'deduped_total': row_sum(deduped),
        'residual': round(row_sum(deduped) - row_sum(f24_rows), 2),
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
          f"residual ${result['residual']:,.2f} ({len(result['residual_rows'])} rows); "
          f"latest expenditure {result['latest_expenditure_date']}")


if __name__ == '__main__':
    main()

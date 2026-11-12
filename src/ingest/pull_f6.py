#!/usr/bin/env python3
"""Form 6 (48-Hour Notice) freshness pull for the Congress money tracker.

Form 6 is filed by candidate committees for contributions/loans of $1,000+
received in the final 20 days before an election. It is the freshness
layer's route to late candidate money that no totals endpoint and no bulk
file can see yet (see research/freshness-research.md §2).

Two steps, two different access routes:
1. Discovery: GET /v1/filings/?form_type=F6&committee_id={id} — returns
   metadata ONLY (file_number, receipt_date, …). No contributor, no
   amount, no candidate_id (null on F6 rows). `min_date` is SILENTLY
   IGNORED on /v1/filings/, so this pages with sort=-receipt_date and
   filters client-side (stops when receipt_date falls before the window).
2. Line items: GET https://docquery.fec.gov/csv/{last3}/{file_number}.csv
   — no API key needed. The CSV carries F6N header records (candidate
   ID, name, office/state/district, treasurer, filing date) and F65
   line-item records (contributor type, name, address, date, amount,
   employer, occupation). There is NO F6 bulk file.

The F65 contributor-type code identifies candidate loans (`CAN`) vs
contributions from others; the amounts are split accordingly and are
NEVER blended into the dataset totals — this script writes a JSON
report only. The freshness driver (src/ingest/pull_freshness.py) folds it
into data/intermediate/freshness_snapshot.json.

Usage:
    python3 src/ingest/pull_f6.py --committee C00892737 [--since 2026-10-15]
                             [--out data/intermediate/f6_<committee>.json]
    python3 src/ingest/pull_f6.py --file-number 2044138   # fetch + parse one filing

API key: FEC_API_KEY env var, else DEMO_KEY (spot checks only, ~30/hr).
Docquery CSV fetches need no key. Sleeps >=1s between API calls.
"""
import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.api_retry import (DOCQUERY_RATE_LIMIT_NOTE, open_with_retry,
                                  retry_settings, sanitize_url)
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
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


def discover_f6(committee_id, since=None):
    """All F6 filings for a committee, newest first.

    `since` is a YYYY-MM-DD date string: paging stops once receipt_date
    falls before it (min_date is ignored server-side, so this is
    client-side). Returns a list of filing metadata dicts.
    """
    filings = []
    page = 1
    while True:
        data = api_get('/filings/', {'form_type': 'F6', 'committee_id': committee_id,
                                     'per_page': 100, 'page': page, 'sort': '-receipt_date'})
        results = data.get('results', [])
        if not results:
            break
        for r in results:
            if since and (r.get('receipt_date') or '') < since:
                return filings
            filings.append(r)
        if len(results) < 100:
            break
        page += 1
        if page > 50:
            raise SystemExit('F6 discovery: too many pages (over 50); refusing to continue')
    return filings


def fetch_f6_csv(file_number):
    """Fetch one filing's docquery CSV (no API key). Returns raw text.

    Same 429 retry as the API paths (src/common/api_retry.py): docquery
    needs no key, so the api.data.gov 1,000/hr limit does not apply
    here, but a 429 from docquery would kill a run the same way.
    """
    last3 = str(file_number)[-3:]
    url = f'https://docquery.fec.gov/csv/{last3}/{file_number}.csv'
    try:
        with open_with_retry(url, timeout=CFG['fec_api']['request_timeout_seconds'],
                             retry=RETRY, label='docquery CSV',
                             limit_note=DOCQUERY_RATE_LIMIT_NOTE) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        raise SystemExit(f'docquery CSV fetch failed: HTTP {e.code} {e.reason} (url {url})')


def parse_f6_csv(text):
    """Parse an F6 docquery CSV into {'header': F6N dict, 'items': [F65 dicts]}.

    F6N (header) fields, by position (counted from the live Constantino
    filing, file 2044138): committee_id 1, committee_name 3, zip 8,
    candidate_id 9, candidate_last 10, candidate_first 11,
    candidate_middle 12, office 15, office_state 16, office_district 17,
    treasurer_last 18, treasurer_first 19, filing_date 23 (YYYYMMDD).
    F65 (line item) fields, by position: committee_id, form_line,
    contributor_type, _, contributor_last, contributor_first,
    contributor_middle, _, _, street, street2, city, state, zip, _,
    date (YYYYMMDD), amount, employer, occupation. Positions are taken
    from the live Constantino filing (file 2044138, Oct 29, 2026) and
    the FEC .fec v8.x layout; unknown slots are kept as raw strings.
    """
    header = None
    items = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row:
            continue
        kind = row[0]
        if kind == 'HDR':
            continue
        if kind == 'F6N' or kind == 'F6A':
            def g(i):
                return row[i] if i < len(row) else ''
            header = {'committee_id': g(1), 'committee_name': g(3),
                      'candidate_id': g(9), 'candidate_last': g(10),
                      'candidate_first': g(11), 'candidate_middle': g(12),
                      'office': g(15), 'office_state': g(16),
                      'office_district': g(17),
                      'treasurer_last': g(18), 'treasurer_first': g(19),
                      'filing_date': g(23)}
        elif kind == 'F65':
            def g(i):
                return row[i] if i < len(row) else ''
            raw_amount = g(17).replace(',', '').strip()
            try:
                amount = float(raw_amount) if raw_amount else 0.0
            except ValueError:
                amount = None
            raw_date = g(16).strip()
            date = (f'{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}'
                    if len(raw_date) == 8 and raw_date.isdigit() else raw_date)
            items.append({'committee_id': g(1), 'form_line': g(2),
                          'contributor_type': g(3),
                          'contributor_last': g(5), 'contributor_first': g(6),
                          'contributor_middle': g(7),
                          'city': g(12), 'state': g(13), 'zip': g(14),
                          'date': date, 'amount': amount,
                          'employer': g(18), 'occupation': g(19),
                          'is_candidate': g(3) == 'CAN'})
    return {'header': header, 'items': items}


def pull_committee(committee_id, since=None):
    """Discover + fetch + parse every F6 for one committee in-window.

    Amendment chains: the filings endpoint returns BOTH the original
    and its amended version (e.g. El-Sayed C00902668: file 2044921 and
    its amendment 2045386 re-list most of the same contributions).
    A filing is superseded if another discovered filing's
    amendment_chain contains its file number; superseded filings are
    dropped and only the latest version of each chain is kept. Without
    this the El-Sayed F6 total overstates by $351,042.26 (the two
    superseded filings' totals).
    """
    filings = discover_f6(committee_id, since=since)
    superseded = set()
    for f in filings:
        chain = f.get('amendment_chain') or []
        for fn in chain[:-1]:
            superseded.add(fn)
    kept = [f for f in filings if f.get('file_number') not in superseded]
    out = {'committee_id': committee_id, 'since': since,
           'n_filings': len(kept), 'n_superseded_dropped': len(filings) - len(kept),
           'superseded_file_numbers': sorted(superseded),
           'filings': []}
    for f in kept:
        file_number = f.get('file_number')
        parsed = parse_f6_csv(fetch_f6_csv(file_number)) if file_number else {'header': None, 'items': []}
        cand_loans = round(sum(i['amount'] for i in parsed['items']
                               if i['is_candidate'] and i['amount'] is not None), 2)
        contrib = round(sum(i['amount'] for i in parsed['items']
                            if not i['is_candidate'] and i['amount'] is not None), 2)
        out['filings'].append({
            'file_number': file_number,
            'receipt_date': f.get('receipt_date'),
            'is_amended': f.get('is_amended'),
            'amendment_chain': f.get('amendment_chain'),
            'candidate_id': (parsed['header'] or {}).get('candidate_id'),
            'candidate_name': ' '.join(x for x in (
                (parsed['header'] or {}).get('candidate_first', ''),
                (parsed['header'] or {}).get('candidate_last', '')) if x),
            'candidate_loans': cand_loans,
            'contributions': contrib,
            'items': parsed['items'],
        })
    out['total_candidate_loans'] = round(sum(f['candidate_loans'] for f in out['filings']), 2)
    out['total_contributions'] = round(sum(f['contributions'] for f in out['filings']), 2)
    return out


def main():
    ap = argparse.ArgumentParser(description='Form 6 (48-Hour Notice) freshness pull.')
    ap.add_argument('--committee', help='FEC committee ID to sweep (e.g. C00892737)')
    ap.add_argument('--file-number', type=int, help='fetch + parse one filing by file number')
    ap.add_argument('--since', default=None, help='YYYY-MM-DD: only filings received on/after this date')
    ap.add_argument('--out', default=None, help='write the JSON report here (default: stdout)')
    args = ap.parse_args()
    if args.file_number:
        parsed = parse_f6_csv(fetch_f6_csv(args.file_number))
        result = {'file_number': args.file_number, **parsed}
    elif args.committee:
        result = pull_committee(args.committee, since=args.since)
    else:
        ap.error('need --committee or --file-number')
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(result, f, indent=1)
        print(f"wrote {args.out}")
    else:
        json.dump(result, sys.stdout, indent=1)
        print()
    if isinstance(result, dict) and 'filings' in result:
        print(f"F6 {args.committee}: {result['n_filings']} filing(s) since {args.since}; "
              f"candidate loans ${result['total_candidate_loans']:,.2f}, "
              f"contributions ${result['total_contributions']:,.2f}")


if __name__ == '__main__':
    main()

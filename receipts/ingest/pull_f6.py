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
report only. The freshness driver (receipts/ingest/pull_freshness.py) folds it
into data/intermediate/freshness_snapshot.json.

Usage:
    python3 receipts/ingest/pull_f6.py --committee C00892737 [--since 2026-10-15]
                             [--out data/intermediate/f6_<committee>.json]
    python3 receipts/ingest/pull_f6.py --file-number 2044138   # fetch + parse one filing

API key: FEC_API_KEY env var, else DEMO_KEY (spot checks only, ~30/hr).
Docquery CSV fetches need no key. Sleeps >=1s between API calls.
"""

import argparse
import csv
import io
import json
import sys

from receipts.common.fec_api import client


def discover_f6(committee_id, since=None):
    """All F6 filings for a committee, newest first.

    `since` is a YYYY-MM-DD date string: paging stops once receipt_date
    falls before it (min_date is ignored server-side, so this is
    client-side). Returns a list of filing metadata dicts.
    """
    filings = []
    page = 1
    while True:
        data = client().get(
            '/filings/',
            {
                'form_type': 'F6',
                'committee_id': committee_id,
                'per_page': 100,
                'page': page,
                'sort': '-receipt_date',
            },
        )
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
    """One filing's docquery CSV as text (no API key needed)."""
    last3 = str(file_number)[-3:]
    return client().fetch_text(f'https://docquery.fec.gov/csv/{last3}/{file_number}.csv')


# Field positions in the docquery CSV records, counted from the live Constantino
# filing (file 2044138, Oct 29, 2026) against the FEC .fec v8.x layout.
HEADER_FIELDS = {
    'committee_id': 1,
    'committee_name': 3,
    'candidate_id': 9,
    'candidate_last': 10,
    'candidate_first': 11,
    'candidate_middle': 12,
    'office': 15,
    'office_state': 16,
    'office_district': 17,
    'treasurer_last': 18,
    'treasurer_first': 19,
    'filing_date': 23,
}
LINE_ITEM_FIELDS = {
    'committee_id': 1,
    'form_line': 2,
    'contributor_type': 3,
    'contributor_last': 5,
    'contributor_first': 6,
    'contributor_middle': 7,
    'city': 12,
    'state': 13,
    'zip': 14,
}
LINE_ITEM_DATE, LINE_ITEM_AMOUNT, LINE_ITEM_EMPLOYER, LINE_ITEM_OCCUPATION = 16, 17, 18, 19
HEADER_RECORDS = ('F6N', 'F6A')
LINE_ITEM_RECORD = 'F65'
CANDIDATE_CONTRIBUTOR = 'CAN'


def field(row, i):
    return row[i] if i < len(row) else ''


def fields(row, positions):
    return {name: field(row, i) for name, i in positions.items()}


def parse_amount(raw):
    """Dollars as a float; 0.0 when blank, None when unreadable."""
    raw = raw.replace(',', '').strip()
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return None


def parse_date(raw):
    """YYYYMMDD as YYYY-MM-DD; anything else as given."""
    raw = raw.strip()
    if len(raw) == 8 and raw.isdigit():
        return f'{raw[0:4]}-{raw[4:6]}-{raw[6:8]}'
    return raw


def line_item(row):
    contributor_type = field(row, LINE_ITEM_FIELDS['contributor_type'])
    return {
        **fields(row, LINE_ITEM_FIELDS),
        'date': parse_date(field(row, LINE_ITEM_DATE)),
        'amount': parse_amount(field(row, LINE_ITEM_AMOUNT)),
        'employer': field(row, LINE_ITEM_EMPLOYER),
        'occupation': field(row, LINE_ITEM_OCCUPATION),
        'is_candidate': contributor_type == CANDIDATE_CONTRIBUTOR,
    }


def parse_f6_csv(text):
    """An F6 docquery CSV as {'header': F6N/F6A fields, 'items': [F65 line items]}."""
    header = None
    items = []
    for row in csv.reader(io.StringIO(text)):
        kind = row[0] if row else None
        if kind in HEADER_RECORDS:
            header = fields(row, HEADER_FIELDS)
        elif kind == LINE_ITEM_RECORD:
            items.append(line_item(row))
    return {'header': header, 'items': items}


def superseded_file_numbers(filings):
    """File numbers replaced by a later amendment in any discovered filing's chain.

    The filings endpoint returns an original and its amendments (El-Sayed
    C00902668: 2044921 and its amendment 2045386); counting both overstated
    his F6 total by $351,042.26.
    """
    return {fn for f in filings for fn in (f.get('amendment_chain') or [])[:-1]}


def sum_amounts(items, from_candidate):
    return round(
        sum(
            i['amount']
            for i in items
            if i['is_candidate'] == from_candidate and i['amount'] is not None
        ),
        2,
    )


def candidate_name(header):
    header = header or {}
    return ' '.join(
        x for x in (header.get('candidate_first', ''), header.get('candidate_last', '')) if x
    )


def filing_report(filing):
    """One F6 filing's metadata, line items, and candidate loans split from contributions."""
    file_number = filing.get('file_number')
    parsed = (
        parse_f6_csv(fetch_f6_csv(file_number)) if file_number else {'header': None, 'items': []}
    )
    return {
        'file_number': file_number,
        'receipt_date': filing.get('receipt_date'),
        'is_amended': filing.get('is_amended'),
        'amendment_chain': filing.get('amendment_chain'),
        'candidate_id': (parsed['header'] or {}).get('candidate_id'),
        'candidate_name': candidate_name(parsed['header']),
        'candidate_loans': sum_amounts(parsed['items'], from_candidate=True),
        'contributions': sum_amounts(parsed['items'], from_candidate=False),
        'items': parsed['items'],
    }


def pull_committee(committee_id, since=None):
    """Every in-window F6 for one committee, latest version of each amendment chain only."""
    filings = discover_f6(committee_id, since=since)
    superseded = superseded_file_numbers(filings)
    kept = [f for f in filings if f.get('file_number') not in superseded]
    reports = [filing_report(f) for f in kept]
    return {
        'committee_id': committee_id,
        'since': since,
        'n_filings': len(kept),
        'n_superseded_dropped': len(filings) - len(kept),
        'superseded_file_numbers': sorted(superseded),
        'filings': reports,
        'total_candidate_loans': round(sum(f['candidate_loans'] for f in reports), 2),
        'total_contributions': round(sum(f['contributions'] for f in reports), 2),
    }


def main():
    ap = argparse.ArgumentParser(description='Form 6 (48-Hour Notice) freshness pull.')
    ap.add_argument('--committee', help='FEC committee ID to sweep (e.g. C00892737)')
    ap.add_argument('--file-number', type=int, help='fetch + parse one filing by file number')
    ap.add_argument(
        '--since', default=None, help='YYYY-MM-DD: only filings received on/after this date'
    )
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
        print(f'wrote {args.out}')
    else:
        json.dump(result, sys.stdout, indent=1)
        print()
    if isinstance(result, dict) and 'filings' in result:
        print(
            f'F6 {args.committee}: {result["n_filings"]} filing(s) since {args.since}; '
            f'candidate loans ${result["total_candidate_loans"]:,.2f}, '
            f'contributions ${result["total_contributions"]:,.2f}'
        )


if __name__ == '__main__':
    main()

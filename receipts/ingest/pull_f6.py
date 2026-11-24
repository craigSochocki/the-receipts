#!/usr/bin/env python3
"""Form 6 (48-hour notice) pull: filings from the API, line items from docquery CSVs."""

import argparse
import csv
import io

from receipts.common.fec_api import client, scan_filings
from receipts.common.files import emit_json
from receipts.common.log import log, run
from receipts.domain.money import exact_sum


def discover_f6(committee_id, since=None):
    """A committee's F6 filings received on or after `since`, newest first."""
    return scan_filings(
        client(), 'F6', since, per_page=100, max_pages=50, committee_id=committee_id
    )[0]


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
    """File numbers a later amendment replaced; counting both would overstate the total."""
    return {fn for f in filings for fn in (f.get('amendment_chain') or [])[:-1]}


def sum_amounts(items, from_candidate):
    return exact_sum(
        i['amount']
        for i in items
        if i['is_candidate'] == from_candidate and i['amount'] is not None
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
        'total_candidate_loans': exact_sum(f['candidate_loans'] for f in reports),
        'total_contributions': exact_sum(f['contributions'] for f in reports),
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
    emit_json(result, args.out)
    if isinstance(result, dict) and 'filings' in result:
        log.info(
            f'F6 {args.committee}: {result["n_filings"]} filing(s) since {args.since}; '
            f'candidate loans ${result["total_candidate_loans"]:,.2f}, '
            f'contributions ${result["total_contributions"]:,.2f}'
        )


if __name__ == '__main__':
    run(main)

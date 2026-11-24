#!/usr/bin/env python3
"""F24 (24/48-hour IE) pull; Schedule E double-returns rows, so only F24 rows count."""

import argparse

from receipts.common.fec_api import client
from receipts.common.files import emit_json
from receipts.domain.money import exact_sum

PER_PAGE = 100
MAX_PAGES = 100


def schedule_e_filters(committee_id, candidate_id, cycle, filing_form):
    named = {
        'committee_id': committee_id,
        'candidate_id': candidate_id,
        'cycle': cycle,
        'filing_form': filing_form,
    }
    return {k: v for k, v in named.items() if v}


def page_identity(results):
    """A page's sub_ids, or its dedup keys when any row lacks one."""
    sub_ids = [r.get('sub_id') for r in results]
    if all(s is not None for s in sub_ids):
        return tuple(sub_ids)
    return tuple(dedup_key(r) for r in results)


def refuse(problem, committee_id, candidate_id, cycle, filing_form, page):
    raise SystemExit(
        f'Schedule E sweep: {problem} '
        f'(committee={committee_id} candidate={candidate_id} '
        f'cycle={cycle} filing_form={filing_form} page {page}); '
        'refusing to continue'
    )


def fetch_schedule_e(committee_id=None, candidate_id=None, cycle=None, filing_form=None):
    """All Schedule E rows matching the filters; the endpoint pages by cursor, not `page`."""
    filters = schedule_e_filters(committee_id, candidate_id, cycle, filing_form)
    where = (committee_id, candidate_id, cycle, filing_form)
    rows, cursor, previous = [], {}, None
    for page in range(1, MAX_PAGES + 1):
        data = client().get('/schedules/schedule_e/', {'per_page': PER_PAGE, **cursor, **filters})
        results = data.get('results', [])
        if not results:
            return rows
        identity = page_identity(results)
        if identity == previous:
            refuse('endpoint repeated the same page', *where, page)
        previous = identity
        rows.extend(results)
        if len(results) < PER_PAGE:
            return rows
        cursor = dict(data.get('pagination', {}).get('last_indexes') or {})
        if not cursor:
            refuse(
                'full page returned but no pagination.last_indexes cursor to advance with',
                *where,
                page,
            )
    raise SystemExit('Schedule E sweep: too many pages (over 100); refusing to continue')


def dedup_key(row):
    """The research's dedup key: (expenditure_date, amount, payee)."""
    return (row.get('expenditure_date'), row.get('expenditure_amount'), row.get('payee_name'))


def dedup_rows(rows):
    seen = {}
    for r in rows:
        seen.setdefault(dedup_key(r), r)
    return list(seen.values())


def row_sum(rows):
    return exact_sum(float(r.get('expenditure_amount') or 0) for r in rows)


def sweep(committee_id=None, candidate_id=None, cycle=None):
    """F24-only rows and totals, reconciled against the deduped unfiltered rows."""
    f24_rows = fetch_schedule_e(committee_id, candidate_id, cycle, filing_form='F24')
    all_rows = fetch_schedule_e(committee_id, candidate_id, cycle)
    deduped = dedup_rows(all_rows)
    f24_keys = {dedup_key(r) for r in f24_rows}
    residual_rows = [r for r in deduped if dedup_key(r) not in f24_keys]
    # A residual row filed on a regular report (filing_form F3X) is
    # expected: it predates the 24/48-hour window and was never an F24. Only a
    # residual row whose filing_form IS F24 would be a real
    # discrepancy (the F24-only set should contain every F24 row).
    explained = [r for r in residual_rows if r.get('filing_form') != 'F24']
    unexplained = [r for r in residual_rows if r.get('filing_form') == 'F24']
    return {
        'committee_id': committee_id,
        'candidate_id': candidate_id,
        'cycle': cycle,
        'f24_n_rows': len(f24_rows),
        'f24_total': row_sum(f24_rows),
        'naive_n_rows': len(all_rows),
        'naive_total': row_sum(all_rows),
        'deduped_n_rows': len(deduped),
        'deduped_total': row_sum(deduped),
        'residual': exact_sum([row_sum(deduped), -row_sum(f24_rows)]),
        'residual_explained': row_sum(explained),
        'residual_unexplained': row_sum(unexplained),
        'residual_rows': residual_rows,
        'latest_expenditure_date': max(
            (r.get('expenditure_date') or '' for r in f24_rows), default=None
        ),
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
    emit_json(result, args.out)
    print(
        f'F24 {args.committee or ""} vs {args.candidate or ""} cycle {args.cycle}: '
        f'{result["f24_n_rows"]} rows, ${result["f24_total"]:,.2f}; '
        f'naive ${result["naive_total"]:,.2f} ({result["naive_n_rows"]} rows), '
        f'deduped ${result["deduped_total"]:,.2f} ({result["deduped_n_rows"]} rows); '
        f'residual ${result["residual"]:,.2f} '
        f'(explained ${result["residual_explained"]:,.2f} non-F24, '
        f'unexplained ${result["residual_unexplained"]:,.2f}); '
        f'latest expenditure {result["latest_expenditure_date"]}'
    )


if __name__ == '__main__':
    main()

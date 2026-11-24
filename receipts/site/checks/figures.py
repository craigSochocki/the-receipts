"""No result figure is typed into the page: every one is computed in the browser."""

import re

from receipts.site.checks.counts import HOUSE_SEATS
from receipts.site.checks.page import num
from receipts.site.expectations import figure_literals

# Counts the browser renders; the current-cycle targets tab's count is written at build
# time, so only the next-cycle tab is scanned for the watchlist phrases.
COUNT_PHRASES = (r'\d+ of \d+ incoming members', r'\d+ House \+ \d+ Senate')
WATCHLIST_PHRASES = (r'\d+ House Democrats', r'\d+ Democratic senators')


def legend(counts):
    return [f'{k.split()[0].capitalize()} {k.split()[1]} {n}' for k, n in counts.items()]


def literals(page):
    charts = page.expected['charts']
    career_dirty = sum(num(r['dirty_career']) for r in page.rows)
    return [
        *figure_literals(page.expected),
        page.expected['career_dirty']['total_compact'],
        f'{career_dirty:,.2f}',
        *legend(charts['house']),
        *legend(charts['senate']),
        f'Uncalled {HOUSE_SEATS - charts["house_named"]}',
    ]


def typed_figures(prose, watchlist, figures):
    return (
        [f for f in figures if f in prose]
        + [p for p in COUNT_PHRASES if re.search(p, prose)]
        + [p for p in WATCHLIST_PHRASES if re.search(p, watchlist)]
    )


def no_typed_figures(audit, page):
    figures = literals(page)
    watchlist = page.html[
        page.html.index('id="tab-targets28"') : page.html.index('id="tab-method"')
    ]
    found = typed_figures(page.prose, watchlist, figures)
    audit.check('no result figure is typed into the page', not found, f'found {found}')
    audit.check(
        'negative test: a typed figure and a typed count trip the check',
        len(typed_figures(page.prose + figures[0], watchlist + ' 999 House Democrats', figures))
        == 2,
    )

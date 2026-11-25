"""No result figure is typed into the page: every one is computed in the browser."""

import re

from receipts.site.checks.counts import HOUSE_SEATS
from receipts.site.checks.page import num
from receipts.site.expectations import figure_literals

# Counts the browser renders, so none may appear in the page's static text.
COUNT_PHRASES = (
    r'\d+ of \d+ incoming members',
    r'\d+ House \+ \d+ Senate',
    r'\d+ incoming members whose seat',
)


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


def typed_figures(prose, figures):
    return [f for f in figures if f in prose] + [p for p in COUNT_PHRASES if re.search(p, prose)]


def no_typed_figures(audit, page):
    figures = literals(page)
    found = typed_figures(page.prose, figures)
    audit.check('no result figure is typed into the page', not found, f'found {found}')
    audit.check(
        'negative test: a typed figure and a typed count trip the check',
        len(typed_figures(page.prose + figures[0] + ' 999 House + 9 Senate', figures)) == 2,
    )

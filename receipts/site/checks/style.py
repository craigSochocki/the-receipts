"""Colour semantics and tabular numerals."""

import re


def colour_semantics(audit, page):
    """Green means clean only; actions and the Dirty badge are ink."""
    audit.check(
        'D4/D5: green is clean-only; actions, selected tab, Dirty badge are ink',
        'button[aria-selected="true"]{background:var(--ink);color:#fff;border-color:var(--ink);font-weight:700;text-decoration:underline'
        in page.html
        and '.badge.dirty{background:var(--ink);color:#fff}' in page.html
        and 'border:1px solid var(--ink);background:var(--ink)' in page.html
        and page.html.count('var(--accent)') == 3
        and page.html.count('var(--accent-soft)') == 3
        and 'Not clean' not in page.html,
    )


def tabular_numerals(audit, page):
    """Tables and display numbers use tabular numerals."""
    audit.check(
        'D10: tabular numerals on tables and display numbers',
        re.search(r'table\{[^}]*font-variant-numeric:tabular-nums', page.html) is not None
        and '.big-number{font-size:2.1rem;font-weight:700;margin:2px 0 0;line-height:1.2;font-variant-numeric:tabular-nums}'
        in page.html
        and page.html.count('font-variant-numeric:tabular-nums') == 8,
    )

"""Colour semantics and tabular numerals."""

import re


def colour_semantics(audit, page):
    """Wave 2 (redesign): D4/D5 colour semantics
    Green means clean and only clean: the only remaining green
    uses are the Clean badge and the two clean boxes (story,
    callout). Actions, the selected tab, the pressed view button
    and the Dirty badge are ink; the selected tab also gets a
    non-colour cue (bold + underline). The "Not clean" label was
    already renamed to "Dirty" (eddcb1c) — verified absent here,
    not duplicated.
    """
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
    """Wave 2 (redesign): D10 tabular numerals now
    Figures align in their columns: tabular numerals on the table
    itself (every cell, not just the .num money columns) and on
    the display numbers (hook, big-number, stat and totals
    figures). The full 6-step type scale + 4-step gray remap stay
    deferred to their own commit with a screenshot review.
    """
    audit.check(
        'D10: tabular numerals on tables and display numbers',
        re.search(r'table\{[^}]*font-variant-numeric:tabular-nums', page.html) is not None
        and '.big-number{font-size:2.1rem;font-weight:700;margin:2px 0 0;line-height:1.2;font-variant-numeric:tabular-nums}'
        in page.html
        and page.html.count('font-variant-numeric:tabular-nums') == 8,
    )

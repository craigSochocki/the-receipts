#!/usr/bin/env python3
"""Verify the generated static site (docs/index.html) against the canonical
dataset (congress-money-tracker.json).

Checks:
 1. docs/index.html exists and contains no unreplaced template placeholders.
 2. The embedded compact payload decodes back to the dataset exactly —
    every field of every row, including nested per-cycle lists.
 3. Headline figures recomputed from the embedded data match the dataset
    and data/source/baseline.json: row count, clean counts by chamber and
    party, the named clean-rule spot cases, unknown money cells, the top
    total-accepted names, primary targets, career-clean members, the
    dirtiest members of 2026, party and outcome derivation, the
    leaderboards and default sort, dirty_career, and the composition
    charts. 2028 primary targets: House (same rule as 2026) and Class 3
    Senate Democrats; the tab's intro is computed at render, never typed;
    the front-door pointer opens it via showTab. Tolerance presets
    (methodology §14): the AIPAC/UDP flag, both presets' tiers and
    not-dirty counts, and the 2028 targets under each preset; the
    front-door story defaults to Balanced not-dirty with the tolerance
    labeled; the Explore tolerance control (Strict / Balanced / Lenient)
    recomputes the counts, badges, and the 2028 tab live.
    Scrollytelling: the front-door chapters in narrative order
    (hook, dirtiest, dirty-definition, clean, chamber, finder, data);
    IntersectionObserver reveals gated on html.js (no-JS shows
    everything); prefers-reduced-motion renders everything visible;
    count-up end values equal the computed figures, components
    reconciling; waffle dots and senate tiles stagger on reveal.
 4. The page's JavaScript parses (node --check on both app scripts).
 5. docs/ serves over HTTP (200 + key strings present).
 6. The generator is deterministic apart from the generation timestamp.
 7. The embedded opposition-credit detail matches
    data/intermediate/opposition-computed.json exactly (race-phase level).

Usage: python3 receipts/site/verify_site.py [--skip-serve]
Exit non-zero on any failure.
"""

import hashlib
import sys

from receipts.common.settings import settings
from receipts.site.checks.charts import (
    composition_charts,
    party_chips_and_outcomes,
    senate_tiles_on_phones,
    stagger_cap,
    tappable_charts,
    tolerance_presets,
)
from receipts.site.checks.data import coverage_stamp, data_round_trip, opposition_detail
from receipts.site.checks.front_door import (
    explore_stats,
    front_door,
    landing_story,
    leaderboards,
    masthead,
    orientation,
    scrollytelling,
)
from receipts.site.checks.navigation import (
    drill_down_on_phones,
    hash_state,
    money_format_toggle,
    prev_next_and_anchors,
    skip_link,
    sticky_tabs_and_finder,
    tab_strip_and_filter_rows,
)
from receipts.site.checks.page import BuiltPage
from receipts.site.checks.runtime import (
    deterministic,
    javascript_parses,
    runtime_smoke_test,
    served_page,
)
from receipts.site.checks.style import colour_semantics, tabular_numerals
from receipts.validate.audit import Audit

SECTIONS = [
    coverage_stamp,
    data_round_trip,
    opposition_detail,
    landing_story,
    front_door,
    hash_state,
    sticky_tabs_and_finder,
    prev_next_and_anchors,
    scrollytelling,
    leaderboards,
    composition_charts,
    party_chips_and_outcomes,
    tolerance_presets,
    masthead,
    orientation,
    colour_semantics,
    tab_strip_and_filter_rows,
    senate_tiles_on_phones,
    drill_down_on_phones,
    tabular_numerals,
    explore_stats,
    money_format_toggle,
    tappable_charts,
    stagger_cap,
    skip_link,
    javascript_parses,
    served_page,
    runtime_smoke_test,
    deterministic,
]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = settings().paths.site / 'index.html'
    if not path.exists():
        raise SystemExit('FAIL docs/index.html does not exist: run build_site.py')
    audit = Audit()
    page = BuiltPage(path)
    audit.check('no unreplaced placeholders', '%%' not in page.html)
    skipped = {served_page} if '--skip-serve' in argv else set()
    for section in SECTIONS:
        if section not in skipped:
            section(audit, page)
    audit.finish(
        'All site checks passed.\n'
        f'dataset md5: {hashlib.md5(settings().paths.dataset_json.read_bytes()).hexdigest()}'
    )


if __name__ == '__main__':
    main()

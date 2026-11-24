"""Navigation: URL state, tabs, the finder, prev/next, anchors and the skip link."""

from receipts.site.checks.page import num
from receipts.site.expectations import figure_literals


def hash_state(audit, page):
    """FE5: the hash carries the whole view (Change 2)"""
    audit.check(
        'FE5: hash serializes/parses/restores the full view',
        'function parseHash' in page.html
        and 'function applyHash' in page.html
        and 'function hashFromState' in page.html
        and 'function syncHash' in page.html
        and 'function writeHash' in page.html,
    )
    audit.check(
        'FE5: hashchange restores state (not just the mode)',
        "addEventListener('hashchange', ()=>applyHash())" in page.html,
    )
    audit.check(
        'FE5: open drill-down lives in the URL (detail=key)',
        "parts.push('detail='+encodeURIComponent(detailKey))" in page.html,
    )
    audit.check(
        'FE5: mode changes push, filter/tab changes replace',
        'syncHash(false)' in page.html and 'syncHash(true)' in page.html,
    )
    audit.check(
        'FE5: Back (hashchange) closes the sheet without a hash write',
        'closeDetail({pop:false})' in page.html,
    )


def sticky_tabs_and_finder(audit, page):
    """U1 leftovers: sticky tab bar + finder in Explore"""
    audit.check(
        'U1: tab bar sticks in Explore (hidden in front-door mode)',
        'position:sticky;top:0;z-index:10;background:var(--bg)' in page.html,
    )
    audit.check(
        'U1: finder reachable from Explore via a slot (one node, moved)',
        'id="finder-slot"' in page.html
        and 'function placeFinder' in page.html
        and 'slot.appendChild(finder)' in page.html
        and 'finderHome.parent.insertBefore(finder, finderHome.next)' in page.html,
    )


def prev_next_and_anchors(audit, page):
    """U10: prev/next, View in Tracker, anchor nav"""
    audit.check(
        'U10: prev/next walk the filtered set, View in Tracker, anchor nav',
        'id="detail-prev"' in page.html
        and 'id="detail-next"' in page.html
        and 'View in Tracker' in page.html
        and 'class="detail-nav"' in page.html
        and 'sortRows(applyFilters())' in page.html
        and 'data-anchor' in page.html,
    )
    audit.check(
        'U10: anchors are buttons, not hash links',
        'data-anchor="sec-career"' in page.html and 'href="#sec-' not in page.html,
    )
    audit.check(
        'U10: sticky sheet header (name + Close + prev/next)',
        '.detail-top{position:sticky' in page.html,
    )
    front = page.html[page.html.index('id="front-door"') : page.html.index('<footer>')]
    audit.check(
        'front door carries no stat cards or totals strip',
        'id="stats"' not in front and 'id="totals"' not in front,
    )
    DIRTY_LITERALS = figure_literals(page.expected)

    def has_dirty_literal(text):
        return any(lit in text for lit in DIRTY_LITERALS)

    audit.check(
        'dirtiest figures are computed, not hardcoded',
        not has_dirty_literal(page.prose),
        'a literal dirtiest figure survives in the built page',
    )
    # Negative test: an injected literal must trip the same detector,
    # proving the clean-page result above is not vacuous.
    audit.check(
        'negative test: injected dirtiest literal trips the check',
        has_dirty_literal(page.prose + 'took $' + DIRTY_LITERALS[0] + '.00'),
    )
    dirty = sorted(
        [r for r in page.rows if num(r['dirty_2026']) > 0], key=lambda r: -num(r['dirty_2026'])
    )[:5]
    top1 = num(dirty[0]['dirty_2026'])
    next4 = sum(num(r['dirty_2026']) for r in dirty[1:])
    audit.check(
        'headline comparison line appears only if #1 exceeds the next four',
        page.expected['headline']['exceeds_next_four'] == (top1 > next4),
    )


def tab_strip_and_filter_rows(audit, page):
    """Wave 2 (redesign): D8 tab strip + labelled filter rows
    The tab bar is one horizontal scroll strip (no wrapping); the
    Tracker filters sit in two labelled rows (Filter / Show only).
    Tabs keep the squared-top radius — never pill-shaped.
    """
    audit.check(
        'D8: tab bar is one horizontal scroll strip, tabs not pill-shaped',
        '.tabs{display:flex;gap:4px;flex-wrap:nowrap;overflow-x:auto' in page.html
        and '.tabs button{flex:none;border:1px solid var(--line);background:var(--bg);border-radius:8px 8px 0 0'
        in page.html,
    )
    audit.check(
        'D8: Tracker filters in two labelled rows',
        'class="controls controls-rows"' in page.html
        and page.html.count('class="controls-row"') == 2
        and 'class="controls-label">Filter<' in page.html
        and 'class="controls-label">Show only<' in page.html,
    )


def drill_down_on_phones(audit, page):
    """Wave 2 (redesign): D9 drill-down collapses on mobile
    The key-value grid is one column on phones, and every cycle
    table in the drill-down is a <details> element (first one
    open) instead of a wall of expanded tables.
    """
    audit.check(
        'D9: cycle tables are <details> (first open); kv is 1 column on mobile',
        'function cycleTable(title, rows, cols, open, id)' in page.html
        and "'<details'+(id?' id=\"'+id+'\"':'')+(open?' open':'')+' class=\"cycle\">" in page.html
        and '.detail .kv{grid-template-columns:1fr}' in page.html,
    )


def money_format_toggle(audit, page):
    """Wave 2 (redesign): D6/FE3 compact/exact money toggle
    A persisted toggle (Compact default, Exact shows dollars and
    cents) governs the Explore data views; the drill-down header
    always shows exact figures. The option labels use format
    examples ($1.23M / $1,234,567.89), never a real figure.
    """
    audit.check(
        'D6/FE3: compact/exact money toggle exists, Compact default, persisted',
        'id="f-money"' in page.html
        and 'value="compact" selected' in page.html
        and 'value="exact"' in page.html
        and 'localStorage' in page.html
        and 'function moneyShort' in page.html
        and 'function setMoneyFmt' in page.html
        and "return 'compact';" in page.html,
    )
    audit.check(
        'D6/FE3: detail header always shows exact figures',
        'class="detail-head"' in page.html
        and 'fmtMoney(p.dirty_2026)' in page.html
        and 'fmtMoney(p.total_accepted_career)' in page.html,
    )


def skip_link(audit, page):
    """U5: skip link
    One Tab from the top of the page jumps straight to the data
    (Explore). Hidden until focused; the slim sticky front-door
    header stays dropped this round.
    """
    audit.check(
        'U5: skip link to the data exists, hidden until focused',
        'id="skip-link"' in page.html
        and 'Skip to the data' in page.html
        and '.skip-link{position:absolute' in page.html
        and '.skip-link:focus{top:0}' in page.html,
    )

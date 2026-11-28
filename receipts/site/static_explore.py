"""The build-time static renders for Explore: the overview strip and
the first page of the table.

Computed here from the dataset exactly as explore.js computes them
in the browser, so the static page is the no-JS fallback. The script
re-renders on filter, preset, cycle, sort or page change, so this
static text is the default-view fallback: Balanced preset, latest
election, grouped order, first page.
"""

from receipts.site.explore_data import (
    grouped_order,
    overview,
    page_label,
    page_slice,
)
from receipts.site.static_render import (
    esc_html,
    fmt_compact,
    fmt_money,
    fmt_tier_badge,
    party_chip,
    place_of,
)

PAGE_SIZE = 25

SOURCE_NAMES = {
    'individual': 'individual',
    'corporate_pac': 'corporate PAC',
    'aipac': 'AIPAC direct',
    'udp_benefit': 'UDP benefit',
}

GROUPED_NOTE = 'Grouped: House, then Senate, by party — flagged first in each party block.'


def _share_text(flagged, members):
    """A share as the page formats it: one decimal, whole when whole."""
    if not members:
        return '0%'
    share = round(flagged / members * 1000) / 10
    return f'{share:g}%'


def _waffle_class(block):
    """One waffle dot's class, as explore.js builds it."""
    if block['flagged'] is None:
        return 'uncalled'
    if block['party'] is None:
        return 'unjudged'
    base = {'Democrat': 'dem', 'Republican': 'rep'}.get(block['party'], 'ind')
    return base + (' flagged' if block['flagged'] else '')


def _waffle_html(blocks, grid_class, label):
    """The static waffle: one dot per block member, in display order."""
    dots = ''.join(f'<i class="{_waffle_class(block)}"></i>' * block['count'] for block in blocks)
    return f'<div class="waffle-grid {grid_class}" role="img" aria-label="{label}">{dots}</div>'


def _panel_html(name, panel, voting_count, grid_class):
    """One chamber's overview panel, as explore.js renders it."""
    stats = panel['top_source']
    source = SOURCE_NAMES[stats['source']]
    waffle_label = (
        'Waffle chart: each dot is one member, grouped by party with '
        'flagged members first in their party block'
    )
    html = (
        '<article class="overview-panel">'
        f'<div class="chamber-head"><span class="ch-name">{name}</span>'
        f'<span class="ch-count">{voting_count} named members</span></div>'
        '<div class="overview-stats">'
        '<div class="overview-stat"><span>Total raised</span><b>'
        f'{fmt_compact(panel["total_accepted"])}</b></div>'
        '<div class="overview-stat"><span>Flagged</span><b>'
        f'{panel["flagged"]} · {_share_text(panel["flagged"], panel["members"])}</b></div>'
        '<div class="overview-stat"><span>Top source</span><b>'
        f'{esc_html(source)} · {fmt_compact(stats["total"])}</b></div>'
        '</div>'
        f'{_waffle_html(panel["waffle"], grid_class, waffle_label)}'
        '<p class="waffle-legend">'
        '<span><b class="dot dem"></b>Democrat</span>'
        '<span><b class="dot dem flagged"></b>Democrat, flagged — lighter blue</span>'
        '<span><b class="dot rep"></b>Republican</span>'
        '<span><b class="dot rep flagged"></b>Republican, flagged — lighter red</span>'
        '<span><b class="dot unjudged"></b>Not judged</span>'
        '<span><b class="dot uncalled"></b>Uncalled seat</span></p>'
    )
    if panel['delegates']:
        html += (
            '<p class="delegates-note">Non-voting delegates not plotted: '
            f'{esc_html(", ".join(panel["delegates"]))}. Total raised and '
            'flagged counts above cover all '
            f'{esc_html(name)} members, delegates included.</p>'
        )
    html += (
        '<p class="src">Source: FEC filings. Career totals; flagged means '
        'any AIPAC direct or UDP benefit dollar since the last election. '
        'Counts here cover named members; the Story\u2019s waffle counts '
        'seats, uncalled seats included, so its flagged totals can '
        'differ.</p>'
        '</article>'
    )
    return html


def overview_html(dataset):
    """The overview strip: one panel per chamber, never combined."""
    panels = overview(dataset)
    incoming = [p for p in dataset if p['in_120th'] == 'yes']
    house_voting = sum(
        1
        for p in incoming
        if p['chamber_120'] == 'House' and p['state'] not in {'AS', 'GU', 'MP', 'PR', 'VI', 'DC'}
    )
    senate = sum(1 for p in incoming if p['chamber_120'] == 'Senate')
    return _panel_html('House', panels['House'], house_voting, 'house') + _panel_html(
        'Senate', panels['Senate'], senate, 'senate'
    )


# ---- server-rendered Explore table (the no-JS fallback) ----
# The five default columns and the grouped default order, rendered
# from the dataset as explore.js renderTable() renders them in the
# browser.
EXPLORE_COLS = [
    ('member', 'Member', 'member'),
    ('verdict', 'Verdict', 'verdict'),
    ('total_accepted_career', 'Total', 'money'),
    ('aipac_pac_direct_career', 'AIPAC $', 'money'),
    ('corporate_pac_career', 'Corporate PAC $', 'money'),
]
EXPLORE_SORTABLE = frozenset(
    [
        'member',
        'verdict',
        'total_accepted_career',
        'aipac_pac_direct_career',
        'corporate_pac_career',
    ]
)


def table_head_html():
    """The default columns' header row, with the grouped order in force."""
    cells = []
    for key, label, kind in EXPLORE_COLS:
        sortable = key in EXPLORE_SORTABLE
        cls = ' class="num"' if kind == 'money' else ''
        sort = f' data-sort="{key}"' if sortable else ''
        aria = ' aria-sort="none"' if sortable else ''
        cells.append(f'<th{cls}{sort}{aria}>{esc_html(label)}</th>')
    return '<tr>' + ''.join(cells) + '</tr>'


def member_cell(person):
    """Name, state/district and party dot, as the page renders them."""
    return (
        '<button type="button" class="name-btn" data-key="'
        f'{esc_html(person["person_key"])}">{esc_html(person["full_name"])}</button>'
        f'<span class="member-sub">{esc_html(place_of(person))} · '
        f'{party_chip(person)} '
        f'{esc_html(person["party_120"] or person["party_119"] or "—")}</span>'
    )


def money_cell(value):
    """A money cell: compact text, exact figure on hover."""
    return f'<span title="{esc_html(fmt_money(value))}">{fmt_compact(value)}</span>'


def table_row_html(person):
    """One row in the default view."""
    cells = [
        f'<td class="name">{member_cell(person)}</td>',
        f'<td>{fmt_tier_badge(person)}</td>',
        f'<td class="num">{money_cell(person["total_accepted_career"])}</td>',
        f'<td class="num">{money_cell(person["aipac_pac_direct_career"])}</td>',
        f'<td class="num">{money_cell(person["corporate_pac_career"])}</td>',
    ]
    return f'<tr data-key="{esc_html(person["person_key"])}">' + ''.join(cells) + '</tr>'


def table_body_html(dataset):
    """The first page of the table, in the grouped default order."""
    ordered = grouped_order(dataset)
    return ''.join(table_row_html(p) for p in page_slice(ordered, 1, PAGE_SIZE))


def showing_html(dataset):
    """The showing line for the first page, in the grouped order."""
    return f'{page_label(len(dataset), 1, PAGE_SIZE)} · {GROUPED_NOTE}'


def render_explore_slots(html, dataset):
    """Fill the Explore slots with the static overview and table."""
    for slot in (
        '%%EXPLORE_OVERVIEW%%',
        '%%EXPLORE_THEAD%%',
        '%%EXPLORE_TBODY%%',
        '%%EXPLORE_SHOWING%%',
    ):
        if slot not in html:
            raise SystemExit(f'explore template is missing slot: {slot}')
    html = html.replace('%%EXPLORE_OVERVIEW%%', overview_html(dataset))
    html = html.replace('%%EXPLORE_THEAD%%', table_head_html())
    html = html.replace('%%EXPLORE_TBODY%%', table_body_html(dataset))
    return html.replace('%%EXPLORE_SHOWING%%', showing_html(dataset))

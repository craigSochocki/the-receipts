"""Static Explore renders against the committed dataset."""

import json
import re
from pathlib import Path

import pytest

from receipts.site.explore_data import HOUSE_SEATS, SENATE_SEATS, grouped_order
from receipts.site.static_explore import (
    PAGE_SIZE,
    overview_html,
    render_explore_slots,
    showing_html,
    table_body_html,
    table_head_html,
)

ROOT = Path(__file__).resolve().parents[1]


def dataset():
    return json.loads((ROOT / 'congress-money-tracker.json').read_text())


def test_overview_has_two_chamber_panels_and_full_waffles():
    html = overview_html(dataset())
    assert html.count('<article class="overview-panel">') == 2
    assert 'House' in html and 'Senate' in html
    panels = html.split('<article class="overview-panel">')[1:]
    dots = [len(re.findall(r'<i class="', panel)) for panel in panels]
    assert dots == [HOUSE_SEATS, SENATE_SEATS]


def test_table_head_has_the_five_default_columns():
    head = table_head_html()
    assert head.count('<th') == 5
    for label in ('Member', 'Verdict', 'Total', 'AIPAC $', 'Corporate PAC $'):
        assert label in head


def test_table_body_is_the_first_page_in_grouped_order():
    people = dataset()
    body = table_body_html(people)
    assert body.count('<tr data-key=') == PAGE_SIZE
    first = grouped_order(people)[0]
    assert body.split('<tr data-key=')[1].startswith(f'"{first["person_key"]}"')
    assert first['full_name'] in body


def test_showing_line_names_the_page_and_the_grouped_order():
    people = dataset()
    assert showing_html(people) == (
        f'Showing 1–{PAGE_SIZE} of {len(people)} · '
        'Grouped: House, then Senate, by party — flagged first in each party block.'
    )


def test_render_explore_slots_fills_all_four_slots():
    template = (
        '<section>%%EXPLORE_OVERVIEW%%</section>'
        '<table><thead>%%EXPLORE_THEAD%%</thead>'
        '<tbody>%%EXPLORE_TBODY%%</tbody></table>'
        '<p>%%EXPLORE_SHOWING%%</p>'
    )
    html = render_explore_slots(template, dataset())
    assert '%%' not in html
    assert html.count('<article class="overview-panel">') == 2
    assert html.count('<tr data-key=') == PAGE_SIZE


def test_render_explore_slots_fails_loudly_on_a_missing_slot():
    with pytest.raises(SystemExit):
        render_explore_slots('<p>nothing here</p>', dataset())

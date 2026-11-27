"""The build-time generated regions match what the pages compute."""

import re

from receipts.site.static_explore import showing_html, table_body_html, table_head_html
from receipts.site.static_render import story_slots, story_texts


def static_story_and_table(audit, site):
    """The static story regions and the Explore table match the computed values."""
    rows = site.explore.rows
    texts = story_texts(rows)
    cards = dict(
        re.findall(r'<p class="card" id="step-(\w+)">(.*?)</p>', site.story.html, re.DOTALL)
    )
    audit.check(
        'static story cards match the computed story text',
        cards == texts,
        f'cards {sorted(cards)} vs computed {sorted(texts)}',
    )
    missing = [
        token
        for token, value in story_slots(rows).items()
        if value and value not in site.story.html
    ]
    audit.check(
        'static story regions match the computed values',
        not missing,
        f'missing or stale: {missing}',
    )
    audit.check(
        'static table head matches the default view',
        f'<thead id="explore-thead">{table_head_html()}</thead>' in site.explore.html,
    )
    audit.check(
        'static table holds the first page, in the grouped order',
        f'<tbody id="explore-tbody">{table_body_html(rows)}</tbody>' in site.explore.html,
    )
    audit.check(
        'static showing line matches the computed first page',
        showing_html(rows) in site.explore.html,
    )

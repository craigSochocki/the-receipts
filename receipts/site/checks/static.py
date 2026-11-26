"""The build-time generated regions match what the page computes."""

import re

from receipts.site.build_site import story_texts, table_row, table_rows, table_thead


def static_story_and_table(audit, page):
    """The static story cards and table match the computed values."""
    texts = story_texts(page.rows)
    cards = dict(re.findall(r'<p class="card" id="step-(\w+)">(.*?)</p>', page.html, re.DOTALL))
    audit.check(
        'static story cards match the computed story text',
        cards == texts,
        f'cards {sorted(cards)} vs computed {sorted(texts)}',
    )
    audit.check(
        'static table head matches the default view',
        f'<thead>{table_thead()}</thead>' in page.html,
    )
    match = re.search(r'<tbody>(.*?)</tbody>', page.html, re.DOTALL)
    body = match.group(1) if match else ''
    rows = table_rows(page.rows)
    audit.check(
        'static table holds every row, dirtiest first',
        body.count('<tr data-key=') == len(rows) and body.startswith(table_row(rows[0])),
    )

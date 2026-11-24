"""The front door: the landing story, scrollytelling, leaderboards, stats and masthead."""

import re
from dataclasses import asdict
from datetime import datetime

from receipts.common.settings import settings
from receipts.site.checks.page import num


def landing_story(audit, page):
    """landing story + finder (Change 1): computed, never hardcoded
    The story headline is rendered by JavaScript from the embedded
    dataset, so no "<N> of <M> incoming members" literal may appear in
    the built page at all: if one does, somebody typed the figure into
    the template and the next data change will strand it stale. The
    prose below is the page with the JSON payloads stripped, so raw
    data numbers cannot trip the check.
    """
    audit.check(
        'landing story block exists',
        'id="landing-story"' in page.html and 'id="story-clean-link"' in page.html,
    )
    audit.check(
        'finder controls exist',
        all(
            x in page.html
            for x in (
                'id="find-state"',
                'id="find-district"',
                'id="find-person"',
                'Find your member',
            )
        ),
    )
    audit.check(
        'story headline figure is computed, not hardcoded',
        re.search(r'\d+ of \d+ incoming members', page.prose) is None
        and re.search(r'\d+ House \+ \d+ Senate', page.prose) is None,
        'a literal story figure survives in the built page',
    )


def front_door(audit, page):
    """front door (landing-first): structure, mode, computed figures"""
    audit.check(
        'front-door section exists',
        all(
            x in page.html
            for x in (
                'id="front-door"',
                'id="dirtiest-headline"',
                'id="dirtiest-list"',
                'id="explore-btn"',
                'id="fresh-line"',
                'id="explore-head"',
                'id="tabs-nav"',
                'id="main"',
            )
        ),
    )
    audit.check(
        'mode lives in the URL hash (#explore)',
        'location.hash' in page.html
        and 'modeFromHash' in page.html
        and 'setMode' in page.html
        and "'explore'" in page.html,
    )


def scrollytelling(audit, page):
    """scrollytelling: chapters, reveals, count-ups, stagger"""
    found_chapters = re.findall(r'data-chapter="([^"]+)"', page.html)
    audit.check(
        'front door has 7 chapters in narrative order',
        found_chapters
        == ['hook', 'dirtiest', 'dirty-definition', 'clean', 'chamber', 'finder', 'data'],
        f'got {found_chapters}',
    )
    audit.check(
        'chapter order: hook, dirtiest, explainer, clean, chamber, finder, data',
        page.html.index('data-chapter="hook"')
        < page.html.index('data-chapter="dirtiest"')
        < page.html.index('data-chapter="dirty-definition"')
        < page.html.index('data-chapter="clean"')
        < page.html.index('data-chapter="chamber"')
        < page.html.index('data-chapter="finder"')
        < page.html.index('data-chapter="data"'),
    )
    audit.check(
        'scroll reveals use IntersectionObserver; hidden state is JS-gated',
        'IntersectionObserver' in page.html
        and 'initReveals' in page.html
        and 'html.js .chapter' in page.html
        and "document.documentElement.classList.add('js')" in page.html,
    )
    audit.check(
        'reduced-motion path renders everything visible',
        '@media (prefers-reduced-motion: reduce)' in page.html
        and 'opacity:1 !important' in page.html
        and "matchMedia('(prefers-reduced-motion: reduce)')" in page.html,
    )
    audit.check(
        'count-up mechanism present (data-value + formatter + rAF)',
        'data-value' in page.html
        and 'data-format' in page.html
        and 'requestAnimationFrame' in page.html
        and 'function runCountUp' in page.html
        and 'function formatCountUp' in page.html,
    )
    audit.check('waffle dots and senate tiles stagger on reveal', 'transition-delay' in page.html)
    # Explainer: career dirty total recomputes from the embedded data,
    # and its three components sum to it exactly.
    dc_total = sum(num(r['dirty_career']) for r in page.rows)
    dc_parts = (
        sum(num(r['corporate_pac_career']) for r in page.rows)
        + sum(num(r['aipac_pac_direct_career']) for r in page.rows)
        + sum(num(r['udp_ie_total_benefit_career']) for r in page.rows)
    )
    audit.check(
        'career dirty total: components reconcile',
        abs(dc_parts - dc_total) < 0.01,
        f'total {dc_total}, parts {dc_parts}',
    )
    audit.check(
        'dirty explainer chapter exists',
        'id="dirty-explainer"' in page.html
        and 'What counts as dirty' in page.html
        and 'Individual contributions are <b>not</b> dirty money' in page.html,
    )
    # The explainer's total must be computed at render, never typed:
    # extend the literal scan the same way the dirtiest figures are
    # guarded, with a negative test proving the detector works.
    EXPLAINER_LITERALS = [
        page.expected['career_dirty']['total_compact'],
        f'{dc_total:,.2f}'.rsplit('.', 1)[0],
        f'{dc_total:,.2f}',
    ]
    audit.check(
        'explainer figures are computed, not hardcoded',
        not any(lit in page.prose for lit in EXPLAINER_LITERALS),
        'a literal explainer figure survives in the built page',
    )
    audit.check(
        'negative test: injected explainer literal trips the check',
        any(
            lit in (page.prose + 'career dirty totals $' + EXPLAINER_LITERALS[2])
            for lit in EXPLAINER_LITERALS
        ),
    )


def leaderboards(audit, page):
    """leaderboards lead with dirty; default sort is Dirty 2026"""
    audit.check(
        'leaderboard order: dirtiest 2026, dirtiest career, total accepted',
        page.html.index('Top 20 — dirtiest in 2026')
        < page.html.index('Top 20 — dirtiest, career')
        < page.html.index('Top 20 — total accepted (career)'),
    )
    audit.check(
        'leaderboards intro frames dirty first',
        'Dirty money leads' in page.html
        and 'Individual contributions are not dirty money' in page.html,
    )
    audit.check(
        'default table sort is Dirty 2026 desc',
        "sortKey:'dirty_2026'" in page.html and "sortKey:'total_accepted_career'" not in page.html,
    )
    dc_top = sorted(
        [r for r in page.rows if isinstance(r['dirty_career'], (int, float))],
        key=lambda r: -r['dirty_career'],
    )[:3]
    audit.check(
        'career dirty top 3 are in descending order',
        [r['full_name'] for r in dc_top] == page.expected['career_dirty']['top3'],
    )
    audit.check(
        'dirty_career is null only for Armstrong',
        [r['full_name'] for r in page.rows if r['dirty_career'] is None] == ['Alan Armstrong'],
    )


def masthead(audit, page):
    """Wave 2 (redesign): D2 masthead demotion
    The masthead title used to be bigger than the hook (1.7rem vs
    1.55rem on mobile) — the wordmark led, not the story. D2 shrinks
    the title to ~1.15rem and lets the hook lead at 1.9rem on mobile.
    """
    audit.check(
        'D2: masthead title demoted to 1.15rem, hook leads at 1.9rem on mobile',
        'h1{font-size:1.15rem' in page.html
        and '.hook{font-size:1.9rem}' in page.html
        and 'h1{font-size:1.7rem' not in page.html,
    )


def orientation(audit, page):
    """Wave 2 (redesign): D3 orientation
    Chapter headings at 1.3rem with eyebrow kickers (one per
    chapter with an h2), the clean count in the same .big-number
    treatment as the dirty total, and a slim footer that lives
    inside #front-door (the page footer stays hidden there).
    """
    audit.check(
        'D3: chapter h2s are 1.3rem with eyebrow kickers',
        '.frontdoor h2{font-size:1.3rem' in page.html
        and page.html.count('class="kicker"') == 5
        and '.frontdoor .kicker{' in page.html,
    )
    audit.check(
        'D3: slim front-door footer lives inside #front-door',
        'class="frontfoot"' in page.html
        and page.html.index('id="front-door"')
        < page.html.index('class="frontfoot"')
        < page.html.index('<footer>'),
    )
    _cs = page.html.index('function renderCleanStory')
    _ce = page.html.index('function renderDirtyExplainer', _cs)
    audit.check(
        'D3: clean story count uses the same big-number treatment',
        'big-number' in page.html[_cs:_ce],
    )


def explore_stats(audit, page):
    cov = asdict(settings().verification.coverage_end)
    # ---- Wave 2 (redesign): D7 Explore stats 7 -> 3 ----
    # Only three cards: people tracked, the not-dirty count, and one
    # combined "not judged" card (9 ran unopposed + 1 unverified,
    # Luria, with names). The cutoffs paragraph is NOT deleted — the
    # veto stands (AGENTS.md §4 requires cutoffs labelled
    # everywhere); it collapses into a <details> instead.
    audit.check(
        'D7: Explore stats are 3 cards incl. a combined not-judged card',
        'not judged' in page.html
        and 'ran unopposed in 2026' in page.html
        and 'unverified: ' in page.html,
    )
    audit.check(
        'D7: cutoffs survive, collapsed into a details element',
        '<details class="cutoffs">' in page.html
        and '2026 is partial — coverage end dates' in page.html
        and all(
            f'<b>{datetime.strptime(str(cov[k]), "%Y-%m-%d").strftime("%b %d, %Y")}</b>'
            in page.html
            for k in ('committee_money_pas2', 'weball', 'independent_expenditures')
        ),
    )

#!/usr/bin/env python3
"""Verify the generated static site (docs/index.html) against the canonical
dataset (congress-money-tracker.json).

Checks:
 1. docs/index.html exists and contains no unreplaced template placeholders.
 2. The embedded compact payload decodes back to the dataset exactly —
    every field of every row, including nested per-cycle lists.
 3. Headline figures recomputed from the embedded data match the dataset:
    664 rows; clean True 98 / None 4 (Luria unverified + 3 unopposed);
    incoming House clean 70 (67 D, 3 R); incoming Senate clean 14;
    Constantino verified clean; Luria null; King-Hinds verified clean
    and contested; 9 ran unopposed; Armstrong "unknown" money cells;
    top-10 total-accepted names; 192 primary targets; 53 career-clean
    incoming House members; dirtiest top 5 in 2026 with the #1-vs-next-
    four comparison; party/outcome derivation (535 Won / 124 Not
    returning / 5 Uncalled, every row with a party source);
    leaderboards lead with dirty (2026, then career) and the default
    table sort is Dirty 2026; dirty_career recomputes and Stevens is
    the career dirty #1; composition charts reconcile to 435 / 100
    with per-category counts matching the dataset exactly. 2028
    primary targets: House 192 (same rule as 2026), Senate 13 Class 3
    Democrats led by Hassan; the tab's intro is computed at render,
    never typed; the front-door pointer opens it via showTab.
    Tolerance presets (methodology §14): AIPAC/UDP flag 231 in the
    120th (291 roster-wide); Balanced tiers clean 84 / below_threshold
    119 / dirty 328 (not-dirty 203), Lenient 84 / 173 / 274 (not-dirty
    257); 2028 targets under presets Strict 192/13, Balanced 133/6,
    Lenient 103/3; the front-door story defaults to Balanced not-dirty
    with the tolerance labeled; the Explore tolerance control
    (Strict / Balanced / Lenient) recomputes the counts, badges, and
    the 2028 tab live.
    Scrollytelling: 7 front-door chapters in narrative order
    (hook, dirtiest, dirty-definition, clean, chamber, finder, data);
    IntersectionObserver reveals gated on html.js (no-JS shows
    everything); prefers-reduced-motion renders everything visible;
    count-up end values equal the computed figures (career dirty total
    $1,070,633,247.20, components reconciling); waffle dots and senate
    tiles stagger on reveal.
 4. The page's JavaScript parses (node --check on both app scripts).
 5. docs/ serves over HTTP (200 + key strings present).
 6. The generator is deterministic apart from the generation timestamp.
 7. The embedded opposition-credit detail matches
    data/intermediate/opposition-computed.json exactly (race-phase level),
    including Stevens' two credited phases.

Usage: python3 receipts/site/verify_site.py [--skip-serve]
Exit non-zero on any failure.
"""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from receipts.common.config import load_config
from receipts.site.build_site import SCALARS, build_opp_payload
from receipts.site.build_site import main as build_main
from receipts.site.expectations import figure_literals, site_expectations
from receipts.validate.audit import Audit

CFG = load_config()
ROOT = CFG['_root']
SITE_DIR = ROOT / CFG['paths']['site']
DATASET_JSON = ROOT / CFG['paths']['dataset_json']


def extract_payload(html, script_id):
    m = re.search(
        rf'<script id="{script_id}" type="application/json">(.*?)</script>', html, re.DOTALL
    )
    if not m:
        raise SystemExit(f'missing embedded payload: {script_id}')
    return json.loads(m.group(1))


def decode_row(cols, arr):
    o = {k: arr[i] for i, k in enumerate(cols['scalars'])}
    base = len(cols['scalars'])
    nested_names = [
        'per_cycle',
        'udp_per_cycle',
        'self_funding_per_cycle',
        'other_committees_per_cycle',
        'all_ie_per_cycle',
        'all_ie_top_committees',
    ]
    nested_cols = [cols['pc'], cols['upc'], cols['sf'], cols['oc'], cols['aie'], cols['tc']]
    for j, (name, ccols) in enumerate(zip(nested_names, nested_cols, strict=True)):
        o[name] = [{k: e[i] for i, k in enumerate(ccols)} for e in (arr[base + j] or [])]
    return o


def values_equal(a, b, path=''):
    """Exact equality after a JSON round-trip (floats survive it)."""
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        # Positional encoding writes None for an absent optional key
        # (e.g. udp_per_cycle 'attribution'), so missing == None here.
        keys = set(a) | set(b)
        return all(values_equal(a.get(k), b.get(k), path + '.' + k) for k in keys)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(
            values_equal(x, y, f'{path}[{i}]') for i, (x, y) in enumerate(zip(a, b, strict=True))
        )
    return a == b


class BuiltPage:
    """docs/index.html as the site checks read it: the HTML, its prose and its embedded data."""

    def __init__(self, path):
        self.path = path
        self.html = path.read_text(encoding='utf-8')
        # The page without its JSON payloads, so raw data numbers cannot trip
        # the checks for typed-in figures.
        self.prose = re.sub(
            r'<script id="(receipts-cols|receipts-data|opp-data)" '
            r'type="application/json">.*?</script>',
            '',
            self.html,
            flags=re.DOTALL,
        )
        self.cols = extract_payload(self.html, 'receipts-cols')
        self.rows = [
            decode_row(self.cols, arr) for arr in extract_payload(self.html, 'receipts-data')
        ]
        self.incoming = [r for r in self.rows if r['in_120th'] == 'yes']
        self.opposition = extract_payload(self.html, 'opp-data')
        self.expected = site_expectations(self.rows, self.opposition)


def num(v):
    return v if isinstance(v, (int, float)) else 0


def coverage_stamp(audit, page):
    """Visible data-as-of stamp: the coverage end dates it shows must be
    the ones in config.yaml verification.coverage_end (formatted
    "Sep 30, 2026" style), and it must carry the "Data as of" label.
    """
    cov = CFG['verification']['coverage_end']
    cov_dates = [
        datetime.strptime(cov[k], '%Y-%m-%d').strftime('%b %d, %Y')
        for k in ('committee_money_pas2', 'weball', 'independent_expenditures')
    ]
    audit.check(
        'stamp shows config coverage end dates',
        all(d in page.html for d in cov_dates),
        f'looking for {cov_dates}',
    )
    audit.check('stamp says 2026 is partial', '2026 is partial' in page.html)


def data_round_trip(audit, page):
    """The embedded rows decode to exactly the published dataset."""
    dataset = json.loads(DATASET_JSON.read_text())
    audit.check('embedded row count is 664', len(page.rows) == 664, f'got {len(page.rows)}')
    audit.check(
        'column lists match generator',
        page.cols['scalars'] == SCALARS
        and page.cols['pc']
        and page.cols['sf']
        and page.cols['oc']
        and page.cols['aie']
        and page.cols['tc'],
    )

    mismatches = 0
    for i, (d_row, j_row) in enumerate(zip(page.rows, dataset, strict=True)):
        for k, v in j_row.items():
            if k == 'all_ie_top_committees' and v is None:
                v = []
            if not values_equal(d_row.get(k), v, k):
                mismatches += 1
                if mismatches <= 5:
                    print(
                        f'  mismatch row {i} {j_row.get("full_name")} field {k}: '
                        f'site={d_row.get(k)!r} dataset={v!r}'
                    )
    audit.check(
        'embedded data round-trips exactly (all rows, all fields)',
        mismatches == 0,
        f'{mismatches} mismatched fields',
    )


def opposition_detail(audit, page):
    """opposition-credit detail payload (race-phase level)"""
    opp_expected = build_opp_payload()
    audit.check(
        'embedded opposition detail matches opposition-computed.json',
        values_equal(page.opposition, opp_expected, 'opp'),
        f'{len(page.opposition)} persons, {sum(len(v) for v in page.opposition.values())} race-phases',
    )
    # Dataset-level counts use the same baseline keys as verify_dataset.py,
    # so the site and the dataset cannot disagree.
    for section in ('headline', 'career_dirty', 'charts', 'detail'):
        audit.pin(f'site figures: {section}', f'site.{section}', page.expected[section])
    c, t, t28 = page.expected['clean'], page.expected['tiers'], page.expected['targets_2028']
    audit.pin('clean True', 'clean_2026.true_total', c['true_total'])
    audit.pin('incoming House clean', 'clean_2026.house_120th_verified_clean', c['house_120'])
    audit.pin(
        'incoming House clean D',
        'clean_2026.house_120th_verified_clean_democrat',
        c['house_120_democrat'],
    )
    audit.pin(
        'incoming House clean R',
        'clean_2026.house_120th_verified_clean_republican',
        c['house_120_republican'],
    )
    audit.pin('incoming Senate clean', 'site.clean.senate_120', c['senate_120'])
    audit.pin(
        'clean None: unopposed / unverified names',
        'site.clean.null_names',
        {'unopposed': c['null_unopposed'], 'unverified': c['null_unverified']},
    )
    audit.pin('unopposed in 2026', 'site.clean.unopposed_total', c['unopposed_total'])
    audit.pin(
        'career-clean incoming House (incl. opposition credit)',
        'site.clean.career_clean_house_120',
        c['career_clean_house_120'],
    )
    audit.pin('AIPAC/UDP flag in the 120th', 'tiered_2026.aipac_udp_flag_120th', t['flag_120'])
    audit.pin('AIPAC/UDP flag roster-wide', 'tiered_2026.aipac_udp_flag_all', t['flag_all'])
    for preset in ('balanced', 'lenient'):
        for tier_name, n in t[preset].items():
            audit.pin(
                f'{preset} tier {tier_name} in the 120th', f'tiered_2026.{preset}.{tier_name}', n
            )
        audit.pin(
            f'not-dirty in the 120th under {preset}',
            f'tiered_2026.{preset}.not_dirty',
            t['not_dirty_120'][preset],
        )
    audit.pin(
        'House not dirty under Balanced (of incoming House incl. delegates)',
        'site.tiers.house_not_dirty_balanced',
        t['house_not_dirty_balanced'],
    )
    for preset in ('strict', 'balanced', 'lenient'):
        audit.pin(
            f'2028 targets {preset} House',
            f'tiered_2026.targets_2028_{preset}_house',
            t28[preset][0],
        )
        audit.pin(
            f'2028 targets {preset} Senate Class 3',
            f'tiered_2026.targets_2028_{preset}_senate_class3',
            t28[preset][1],
        )
    audit.pin(
        '2028 watchlist order + lead figures',
        'site.targets_2028.order',
        {k: v for k, v in t28.items() if k not in ('strict', 'balanced', 'lenient')},
    )

    king_hinds = [r for r in page.rows if 'King-Hinds' in r['full_name']]
    audit.check(
        'King-Hinds contested, not unopposed (MP district 01)',
        len(king_hinds) == 1 and king_hinds[0]['unopposed_2026'] is False,
    )
    audit.check(
        '2026 primary-target intro states the computed count',
        f'{t28["targets_2026_house"]} House Democrats in the incoming 120th '
        'took dirty money in 2026' in page.html,
    )
    audit.check(
        'methodology clean paragraph is computed, not stale',
        f'{c["all_120"]} verified clean in the incoming 120th' in page.html
        and f'{c["house_120"]} House ({c["house_120_democrat"]} D, {c["house_120_republican"]} R)'
        in page.html,
        'the methodology paragraph does not state the computed clean counts',
    )


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
    # The explainer's $1.07B must be computed at render, never typed:
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


def composition_charts(audit, page):
    """composition charts (House waffle, Senate state tiles): reconcile to 435 / 100"""
    audit.check(
        'composition section exists on the front door',
        'id="composition"' in page.html
        and 'renderComposition' in page.html
        and 'waffleSVG' in page.html
        and 'senateTilesSVG' in page.html
        and 'compositionSeats' in page.html,
    )
    audit.check(
        'composition sits after the clean story, before the finder',
        page.html.index('id="landing-story"')
        < page.html.index('id="composition"')
        < page.html.index('id="finder"'),
    )

    def _legend(counts):
        return [f'{k.split()[0].capitalize()} {k.split()[1]} {n}' for k, n in counts.items()]

    COMP_LITERALS = (
        _legend(page.expected['charts']['house'])
        + _legend(page.expected['charts']['senate'])
        + [f'Uncalled {435 - page.expected["charts"]["house_named"]}']
    )
    audit.check(
        'House waffle is 15 rows x 29 columns, column-major fill',
        'WAFFLE_ROWS = 15' in page.html
        and 'WAFFLE_COLS = 29' in page.html
        and 'Math.floor(i/WAFFLE_ROWS)' in page.html,
        'waffle geometry missing from the built page',
    )
    audit.check(
        'composition counts are computed, not hardcoded',
        not any(lit in page.prose for lit in COMP_LITERALS),
        'a literal composition count survives in the built page',
    )
    TERR = {'AS', 'GU', 'MP', 'PR', 'VI', 'DC'}

    def party_letter(r):
        p = r['party_120'] or r['party_119'] or '?'
        return {'Democrat': 'D', 'Republican': 'R', 'Independent': 'I'}.get(p, p)

    def seat_status(r):
        if r['clean_2026'] is True:
            return 'clean'
        if r['clean_2026'] is False:
            return 'dirty'
        return 'unopposed' if r['unopposed_2026'] is True else 'unverified'

    house_voting = [
        r for r in page.incoming if r['chamber_120'] == 'House' and r['state'] not in TERR
    ]
    sen = [r for r in page.incoming if r['chamber_120'] == 'Senate']
    audit.check(
        'House composition reconciles: 430 named voting + 5 uncalled = 435',
        len(house_voting) == 430 and 435 - len(house_voting) == 5,
        f'named {len(house_voting)}',
    )
    audit.check(
        'Senate composition reconciles: 99 named + 1 uncalled = 100',
        len(sen) == 99 and 100 - len(sen) == 1,
        f'named {len(sen)}',
    )
    audit.check(
        'Senate tiles cover 50 states: 49 with two named, Alaska with one + uncalled',
        len({r['state'] for r in sen}) == 50
        and len(sen) == 99
        and sum(1 for r in sen if r['state'] == 'AK') == 1,
        f'states {len({r["state"] for r in sen})}, named {len(sen)}',
    )
    audit.check(
        'Senate tile renderer present (state tiles + dotted patterns)',
        'senateTilesSVG' in page.html and 'dots-' in page.html and 'TILE_COLS = 10' in page.html,
        'senateTilesSVG or dotted patterns missing from the built page',
    )
    delegates = [r for r in page.incoming if r['chamber_120'] == 'House' and r['state'] in TERR]
    audit.check('delegates not plotted: 6', len(delegates) == 6, f'got {len(delegates)}')


def party_chips_and_outcomes(audit, page):
    """party chips + outcome labels (person marks)
    The chips render in JS at runtime (asserted in the smoke test);
    here: the helpers exist, and the derivation inputs recomputed
    from the embedded data cover every row with no per-person cases.
    """
    audit.check(
        'party chip + outcome helpers present',
        'function partyChip' in page.html
        and 'function outcomeLabel' in page.html
        and "'Not returning'" in page.html
        and "'Uncalled'" in page.html
        and 'class="pchip ' in page.html
        and "Democrat:['D','d']" in page.html
        and "Republican:['R','r']" in page.html
        and "Independent:['I','o']" in page.html,
    )
    no_party = [r for r in page.rows if not r['party_120'] and not r['party_119']]
    audit.check(
        'every row has a party source (party_120 else party_119)',
        len(no_party) == 0,
        f'{len(no_party)} rows with no party',
    )
    outcomes = {
        v: sum(1 for r in page.rows if r['in_120th'] == v) for v in ('yes', 'no', 'unknown')
    }
    audit.check(
        'outcome mapping covers all 664 (Won 535 / Not returning 124 / Uncalled 5)',
        outcomes == {'yes': 535, 'no': 124, 'unknown': 5},
        f'got {outcomes}',
    )

    def mark_spot(name, party, outcome):
        rows = [r for r in page.rows if name in r['full_name']]
        return (
            len(rows) == 1
            and (rows[0]['party_120'] or rows[0]['party_119']) == party
            and {'yes': 'Won', 'unknown': 'Uncalled', 'no': 'Not returning'}[rows[0]['in_120th']]
            == outcome
        )

    audit.check(
        'marks spot-check: Stevens D / Not returning',
        mark_spot('Stevens', 'Democrat', 'Not returning'),
    )
    audit.check('marks spot-check: El-Sayed D / Won', mark_spot('El-Sayed', 'Democrat', 'Won'))
    audit.check('marks spot-check: Guthrie R / Won', mark_spot('Guthrie', 'Republican', 'Won'))
    audit.check(
        'marks spot-check: Hernández PPD / Won (other gray chip)',
        mark_spot('Hernández', 'PPD', 'Won'),
    )
    const = [r for r in page.rows if 'Constantino' in r['full_name']]
    audit.check('Constantino is a single row', len(const) == 1)
    arm = [r for r in page.rows if 'Armstrong' in r['full_name']]
    audit.check(
        "Armstrong money cells are 'unknown'",
        len(arm) == 1
        and arm[0]['individual_contribution_total_career'] == 'unknown'
        and arm[0]['total_accepted_career'] is None,
    )
    targets28_s = [
        r
        for r in page.rows
        if r['in_120th'] == 'yes'
        and r['chamber_120'] == 'Senate'
        and r['party_120'] == 'Democrat'
        and r['senate_class'] == 3
        and num(r['dirty_2026']) > 0
    ]
    audit.check(
        '2028 Senate targets are all corporate-PAC dirty in 2026',
        all(
            num(r['corp_2026']) == num(r['dirty_2026'])
            and num(r['aipac_direct_2026']) == 0
            and num(r['udp_benefit_2026']) == 0
            for r in targets28_s
        ),
    )
    audit.check(
        '2028 tab exists (both tables + intro + renderer + Class 3 filter)',
        all(
            x in page.html
            for x in (
                'id="tab-targets28"',
                'id="targets28-house-table"',
                'id="targets28-senate-table"',
                'id="targets28-intro"',
                'renderTargets2028',
                'senate_class===3',
                'Dirty career',
            )
        )
        and 'renderTargets2028' in page.html,
    )
    audit.check(
        '2028 tab sits after the 2026 tab, before Methodology',
        page.html.index('data-tab="targets"')
        < page.html.index('data-tab="targets28"')
        < page.html.index('data-tab="method"'),
    )
    audit.check(
        '2028 front-door pointer exists (Data chapter, onclick)',
        'id="targets28-btn"' in page.html
        and "showTab('targets28')" in page.html
        and page.html.index('id="targets28-btn"') > page.html.index('data-chapter="finder"')
        and page.html.index('id="targets28-btn"') < page.html.index('id="explore-btn"'),
    )
    # The 2028 intro counts are rendered at runtime; none may be typed.
    t28_html = page.html[page.html.index('id="tab-targets28"') : page.html.index('id="tab-method"')]
    audit.check(
        '2028 intro counts are computed, not hardcoded',
        re.search(r'\d+ House Democrats', t28_html) is None
        and re.search(r'\d+ Democratic senators', t28_html) is None
        and 'house.length' in page.html
        and 'senate.length' in page.html
        and 'A watchlist, not a prediction' in page.html,
        'a literal 2028 count survives in the built page',
    )
    audit.check(
        'negative test: injected 2028 count trips the check',
        re.search(r'\d+ House Democrats', t28_html + '999 House Democrats') is not None,
    )


def tolerance_presets(audit, page):
    """tolerance presets (methodology §14): flag + tiers"""
    audit.check(
        'embedded payload carries the tolerance columns',
        all(
            k in page.cols['scalars']
            for k in ('aipac_udp_flag_2026', 'tier_balanced_2026', 'tier_lenient_2026')
        ),
    )
    audit.check(
        'tier nulls align with clean nulls exactly',
        all((r['tier_balanced_2026'] is None) == (r['clean_2026'] is None) for r in page.rows)
        and all((r['tier_lenient_2026'] is None) == (r['clean_2026'] is None) for r in page.rows),
    )
    audit.check(
        'tolerance control exists (Strict / Balanced / Lenient, Balanced default)',
        'id="f-tolerance"' in page.html
        and 'id="tolerance-note"' in page.html
        and 'value="strict"' in page.html
        and 'value="balanced" selected' in page.html
        and 'value="lenient"' in page.html
        and 'over $100,000 and over 5% of 2026 receipts' in page.html
        and 'over $250,000 and over 10% of 2026 receipts' in page.html
        and 'setPreset' in page.html,
    )
    audit.check(
        'flag badge + below-threshold badge exist (not the Dirty badge)',
        'badge flag' in page.html
        and 'AIPAC/UDP' in page.html
        and 'badge below' in page.html
        and 'Below threshold' in page.html
        and 'Corporate PAC tolerance presets' in page.html,
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


def senate_tiles_on_phones(audit, page):
    """Wave 2 (redesign): D1 Senate tiles reflow on phones
    Below 560px the Senate tiles render 5 wide x 10 tall (320x505
    viewBox); at desktop width they stay 10 wide (645x250). The
    waffle geometry is untouched (D1's waffle changes were cut).
    """
    audit.check(
        'D1: Senate tiles reflow to 5 wide below 560px, 10 wide above',
        'TILE_COLS = 10' in page.html
        and 'TILE_COLS_NARROW = 5' in page.html
        and 'function senateCols' in page.html
        and "matchMedia('(max-width: 560px)')" in page.html
        and "addEventListener('resize'" in page.html,
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


def explore_stats(audit, page):
    cov = CFG['verification']['coverage_end']
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


def tappable_charts(audit, page):
    """Wave 2 (redesign): U4 charts are tappable
    Waffle dots and Senate tile halves carry the person's key,
    and one delegated listener on the composition container opens
    the drill-down. Uncalled seats carry no key and stay inert.
    Per-dot keyboard focus was cut (435 dots ~ 535 tab stops).
    """
    audit.check(
        'U4: charts are tappable via a delegated SVG listener',
        'data-key' in page.html
        and "getElementById('composition').addEventListener('click'" in page.html
        and "closest('[data-key]')" in page.html,
    )


def stagger_cap(audit, page):
    """Wave 2 (redesign): FE10 stagger cap + text alternative
    The waffle and tile staggers are scaled so the whole sequence
    stays under ~500ms (was ~1.1s / ~1.5s); the dirtiest rows were
    already 360ms. Each chart also gets a visually-hidden
    sentence-form text alternative. The sticky-th clause is NOT
    done here: the only concrete fix (a 70vh inner scroller) was
    cut, and no other pure-CSS fix exists — see the wave report.
    """
    audit.check(
        'FE10: chart staggers capped under ~500ms',
        '480/(WAFFLE_COLS-1)' in page.html
        and '480/49' in page.html
        and 'col*40' not in page.html
        and 'i*30' not in page.html,
    )
    audit.check(
        'FE10: charts have a visually-hidden text alternative',
        '.visually-hidden{' in page.html
        and 'function chartAltText' in page.html
        and 'class="visually-hidden"' in page.html,
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


def javascript_parses(audit, page):
    """JS syntax"""
    app_scripts = re.findall(r'<script>(.*?)</script>', page.html, re.DOTALL)
    audit.check('two app scripts present', len(app_scripts) == 2, f'got {len(app_scripts)}')
    node_ok = True
    for i, src in enumerate(app_scripts):
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
            f.write(src)
            tmp = f.name
        r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
        if r.returncode != 0:
            node_ok = False
            print(f'  node --check script {i} failed:\n{r.stderr[:2000]}')
        Path(tmp).unlink(missing_ok=True)
    audit.check('page JavaScript parses (node --check)', node_ok)


def served_page(audit, page):
    """serve docs/ locally"""
    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    srv = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/index.html', timeout=10) as resp:
            body = resp.read().decode('utf-8')
            status = resp.status
        audit.check('local serve returns 200', status == 200, f'got {status}')
        for needle in [
            'The Receipts',
            'receipts-data',
            'Methodology',
            'primary targets',
            '2028 primary targets',
            'Clean money',
            'Leaderboards',
            'Data as of',
            'Find your member',
            'took no dirty money in 2026',
            'Dirtiest in 2026',
            'Explore the full data',
        ]:
            audit.check(f'served page contains {needle!r}', needle in body)
        audit.check(
            'served page size matches file',
            len(body.encode('utf-8')) == page.path.stat().st_size,
        )
    except Exception as e:  # noqa: BLE001 - report as a failed check
        audit.check(f'local serve works ({e})', False)
    finally:
        srv.shutdown()


def runtime_smoke_test(audit, page):
    """runtime smoke test (runs the page's JS against a DOM stub)"""
    import shutil

    smoke = ROOT / 'receipts' / 'site' / 'smoke_test.js'
    if shutil.which('node') is None:
        print('SKIP runtime smoke test (node not found)')
    else:
        exp_path = ROOT / CFG['paths']['intermediate'] / 'site_expectations.json'
        exp_path.parent.mkdir(parents=True, exist_ok=True)
        exp_path.write_text(json.dumps(page.expected, indent=1))
        r = subprocess.run(
            ['node', str(smoke), str(page.path), str(exp_path)], capture_output=True, text=True
        )
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr[:2000])
        audit.check('runtime smoke test (render, tabs, detail, CSV)', r.returncode == 0)


def deterministic(audit, page):
    """determinism (apart from the generation timestamp)"""
    before = page.path.read_bytes()
    build_main()
    after = page.path.read_bytes()

    def strip_ts(b):
        return re.sub(rb'Generated [0-9-]+ [0-9:]+ UTC', b'Generated TS', b)

    audit.check('generator deterministic apart from timestamp', strip_ts(before) == strip_ts(after))


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


def main():
    path = SITE_DIR / 'index.html'
    if not path.exists():
        raise SystemExit('FAIL docs/index.html does not exist: run build_site.py')
    audit = Audit()
    page = BuiltPage(path)
    audit.check('no unreplaced placeholders', '%%' not in page.html)
    skipped = {served_page} if '--skip-serve' in sys.argv else set()
    for section in SECTIONS:
        if section not in skipped:
            section(audit, page)
    audit.finish(
        'All site checks passed.\n'
        f'dataset md5: {hashlib.md5(DATASET_JSON.read_bytes()).hexdigest()}'
    )


if __name__ == '__main__':
    main()

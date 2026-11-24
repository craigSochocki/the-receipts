"""The composition charts, party chips, tolerance presets and chart behavior."""

import re
from collections import Counter

from receipts.site.checks.page import num

HOUSE_SEATS, SENATE_SEATS, STATES = 435, 100, 50
TERRITORIES = {'AS', 'GU', 'MP', 'PR', 'VI', 'DC'}
OUTCOME_LABELS = {'yes': 'Won', 'unknown': 'Uncalled', 'no': 'Not returning'}


def legend(counts):
    return [f'{k.split()[0].capitalize()} {k.split()[1]} {n}' for k, n in counts.items()]


def composition_section(audit, page):
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


def composition_counts_computed(audit, page):
    charts = page.expected['charts']
    literals = (
        legend(charts['house'])
        + legend(charts['senate'])
        + [f'Uncalled {HOUSE_SEATS - charts["house_named"]}']
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
        not any(lit in page.prose for lit in literals),
        'a literal composition count survives in the built page',
    )


def composition_seats(audit, page):
    house_voting = [
        r for r in page.incoming if r['chamber_120'] == 'House' and r['state'] not in TERRITORIES
    ]
    sen = [r for r in page.incoming if r['chamber_120'] == 'Senate']
    per_state = Counter(r['state'] for r in sen)
    audit.check(
        'House composition fits the chamber: named voting members never exceed the seats',
        len(house_voting) <= HOUSE_SEATS,
        f'named {len(house_voting)}',
    )
    audit.pin('House named voting members', 'site.composition.house_named', len(house_voting))
    audit.check(
        'Senate composition fits the chamber: two seats per state at most',
        len(sen) <= SENATE_SEATS and all(n <= 2 for n in per_state.values()),
        f'named {len(sen)}',
    )
    audit.pin('Senate named members', 'site.composition.senate_named', len(sen))
    audit.check(
        'Senate tiles cover every state',
        len(per_state) == STATES,
        f'states {len(per_state)}',
    )
    audit.pin(
        'Senate states with an uncalled seat',
        'site.composition.senate_states_with_uncalled_seat',
        sorted(state for state, n in per_state.items() if n < 2),
    )
    audit.check(
        'Senate tile renderer present (state tiles + dotted patterns)',
        'senateTilesSVG' in page.html and 'dots-' in page.html and 'TILE_COLS = 10' in page.html,
        'senateTilesSVG or dotted patterns missing from the built page',
    )
    delegates = [
        r for r in page.incoming if r['chamber_120'] == 'House' and r['state'] in TERRITORIES
    ]
    audit.pin('delegates not plotted', 'site.composition.delegates', len(delegates))


def composition_charts(audit, page):
    """composition charts (House waffle, Senate state tiles): reconcile to 435 / 100"""
    composition_section(audit, page)
    composition_counts_computed(audit, page)
    composition_seats(audit, page)


def chip_helpers(audit, page):
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


def party_and_outcome_counts(audit, page):
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
        'outcome mapping covers every row',
        sum(outcomes.values()) == len(page.rows),
        f'got {outcomes}',
    )
    audit.pin('outcomes (Won / Not returning / Uncalled)', 'site.outcomes', outcomes)


def mark_matches(page, name, party, outcome):
    rows = [r for r in page.rows if name in r['full_name']]
    return (
        len(rows) == 1
        and (rows[0]['party_120'] or rows[0]['party_119']) == party
        and OUTCOME_LABELS[rows[0]['in_120th']] == outcome
    )


def mark_spot_cases(audit, page):
    audit.check(
        'marks spot-check: Stevens D / Not returning',
        mark_matches(page, 'Stevens', 'Democrat', 'Not returning'),
    )
    audit.check(
        'marks spot-check: El-Sayed D / Won', mark_matches(page, 'El-Sayed', 'Democrat', 'Won')
    )
    audit.check(
        'marks spot-check: Guthrie R / Won', mark_matches(page, 'Guthrie', 'Republican', 'Won')
    )
    audit.check(
        'marks spot-check: Hernández PPD / Won (other gray chip)',
        mark_matches(page, 'Hernández', 'PPD', 'Won'),
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


def targets_2028_senate_corporate_only(audit, page):
    targets = [
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
            for r in targets
        ),
    )


def targets_2028_tab(audit, page):
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


def targets_2028_intro_computed(audit, page):
    """The 2028 intro counts are rendered at runtime; none may be typed."""
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


def party_chips_and_outcomes(audit, page):
    """Party chips, outcome labels and the 2028 targets tab cover every row."""
    chip_helpers(audit, page)
    party_and_outcome_counts(audit, page)
    mark_spot_cases(audit, page)
    targets_2028_senate_corporate_only(audit, page)
    targets_2028_tab(audit, page)
    targets_2028_intro_computed(audit, page)


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


def senate_tiles_on_phones(audit, page):
    """Below 560px the Senate tiles reflow to 5 wide by 10 tall."""
    audit.check(
        'D1: Senate tiles reflow to 5 wide below 560px, 10 wide above',
        'TILE_COLS = 10' in page.html
        and 'TILE_COLS_NARROW = 5' in page.html
        and 'function senateCols' in page.html
        and "matchMedia('(max-width: 560px)')" in page.html
        and "addEventListener('resize'" in page.html,
    )


def tappable_charts(audit, page):
    """Chart dots and tiles open the drill-down; uncalled seats stay inert."""
    audit.check(
        'U4: charts are tappable via a delegated SVG listener',
        'data-key' in page.html
        and "getElementById('composition').addEventListener('click'" in page.html
        and "closest('[data-key]')" in page.html,
    )


def stagger_cap(audit, page):
    """Chart staggers stay under half a second, and each chart has a text alternative."""
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

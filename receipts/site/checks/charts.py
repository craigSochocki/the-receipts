"""The composition charts, party chips, tolerance presets and chart behavior."""

import re

from receipts.site.checks.page import num


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

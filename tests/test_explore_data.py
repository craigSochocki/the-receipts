"""Explore aggregates against the committed dataset and baseline.

Expected figures come from data/source/baseline.json, never from
literals here; the rest is cross-consistency against the dataset
itself (independent recomputation from the same rows).
"""

import json
from pathlib import Path

from receipts.domain.targets import latest_record
from receipts.site import explore_data
from receipts.site.explore_data import (
    HOUSE_SEATS,
    SENATE_SEATS,
    clean_figures,
    explore_aggregates,
    grouped_order,
    leaderboards,
    overview,
    page_label,
    page_slice,
    party_breakdown,
    primary_targets_list,
    verdict_reason,
)

ROOT = Path(__file__).resolve().parents[1]


def dataset():
    return json.loads((ROOT / 'congress-money-tracker.json').read_text())


def baseline():
    return json.loads((ROOT / 'data' / 'source' / 'baseline.json').read_text())


def test_overview_waffle_fills_each_chamber():
    agg = overview(dataset())
    for chamber, seats in (('House', HOUSE_SEATS), ('Senate', SENATE_SEATS)):
        assert sum(b['count'] for b in agg[chamber]['waffle']) == seats


def test_overview_flagged_and_totals_agree_with_dataset():
    people = dataset()
    agg = overview(people)
    incoming = [p for p in people if p['in_120th'] == 'yes']
    for chamber in ('House', 'Senate'):
        members = [p for p in incoming if explore_data.chamber_of(p) == chamber]
        flagged = sum(1 for p in members if (latest_record(p) or {})['aipac_udp_flag'] is True)
        assert agg[chamber]['flagged'] == flagged
        assert agg[chamber]['members'] == len(members)
        total = sum(explore_data.dollars(p['total_accepted_career']) for p in members)
        assert agg[chamber]['total_accepted'] == total
    house = agg['House']
    assert len(house['delegates']) == baseline()['site.composition.delegates']


def test_overview_top_source_is_the_largest_family():
    people = dataset()
    agg = overview(people)
    incoming = [p for p in people if p['in_120th'] == 'yes']
    for chamber in ('House', 'Senate'):
        members = [p for p in incoming if explore_data.chamber_of(p) == chamber]
        families = {
            name: sum(explore_data.dollars(p[col]) for p in members)
            for name, col in explore_data.SOURCE_FAMILIES
        }
        top = max(families, key=families.get)
        assert agg[chamber]['top_source']['source'] == top
        assert agg[chamber]['top_source']['total'] == families[top]


def test_aipac_and_pro_israel_career_totals_match_baseline():
    people = dataset()
    base = baseline()
    assert (
        round(sum(explore_data.dollars(p['aipac_pac_direct_career']) for p in people), 2)
        == base['methodology_totals.aipac_pac_direct_career']
    )
    assert (
        round(sum(explore_data.dollars(p['pro_israel_pac_career']) for p in people), 2)
        == base['pro_israel.pro_israel_pac_career_total']
    )


def test_leaderboards_dirty_term_leads_and_career_top_matches_baseline():
    people = dataset()
    base = baseline()
    boards = leaderboards(people, 'balanced')
    dirty_term = {
        p['person_key']: explore_data.dollars(explore_data.headline(p)['dirty']) for p in people
    }
    top_key = max(dirty_term, key=dirty_term.get)
    assert boards['dirty_term'][0]['person_key'] == top_key
    assert boards['dirty_term'][0]['amount'] == dirty_term[top_key]
    assert boards['dirty_term'] == sorted(boards['dirty_term'], key=lambda e: -e['amount'])
    assert boards['dirty_career'][0]['amount'] == base['spot.dirty_career_top'][1]
    ranked = sorted(
        (p for p in people if p['rank_total_accepted'] is not None),
        key=lambda p: p['rank_total_accepted'],
    )
    assert boards['total_accepted'][0]['person_key'] == ranked[0]['person_key']


def test_primary_targets_agree_with_baseline():
    people = dataset()
    base = baseline()
    rows = primary_targets_list(people, 'balanced', 2028)
    assert len(rows) == sum(base['targets.balanced'])
    assert rows[0]['full_name'] == base['site.targets']['balanced_top3'][0]
    assert rows[0]['dirty'] == float(
        base['site.targets']['balanced_top_dirty_exact'].replace('$', '').replace(',', '')
    )
    assert rows == sorted(rows, key=lambda r: -r['dirty'])


def test_clean_figures_strict_matches_baseline_and_presets_nest():
    people = dataset()
    base = baseline()
    strict = clean_figures(people, 'strict')
    assert strict['incoming_not_dirty'] == base['site.clean']['all_120']
    balanced = clean_figures(people, 'balanced')
    lenient = clean_figures(people, 'lenient')
    assert (
        strict['incoming_not_dirty']
        <= balanced['incoming_not_dirty']
        <= lenient['incoming_not_dirty']
    )
    assert (
        balanced['by_chamber']['House'] + balanced['by_chamber']['Senate']
        == (balanced['incoming_not_dirty'])
    )


def test_party_breakdown_sums_to_incoming_totals():
    people = dataset()
    rows = party_breakdown(people, 'balanced')
    incoming = [p for p in people if p['in_120th'] == 'yes']
    assert sum(r['members'] for r in rows) == len(incoming)
    assert sum(r['total_accepted'] for r in rows) == round(
        sum(explore_data.dollars(p['total_accepted_career']) for p in incoming), 2
    )


def test_grouped_order_sections_parties_and_flagged_blocks():
    people = dataset()
    ordered = grouped_order([p for p in people if p['in_120th'] == 'yes'])
    chambers = [explore_data.chamber_of(p) for p in ordered]
    assert chambers == sorted(chambers, key=lambda c: explore_data.CHAMBER_ORDER.get(c, 2))
    for chamber in ('House', 'Senate'):
        section = [p for p in ordered if explore_data.chamber_of(p) == chamber]
        parties = [explore_data.party_of(p) for p in section]
        ranks = [explore_data.PARTY_ORDER.get(name, 3) for name in parties]
        assert ranks == sorted(ranks)
        for party in ('Democrat', 'Republican'):
            block = [p for p in section if explore_data.party_of(p) == party]
            flags = [explore_data.is_flagged(explore_data.headline(p)) for p in block]
            assert flags == sorted(flags, reverse=True)


def test_page_slice_and_label():
    rows = list(range(60))
    assert page_slice(rows, 1, 25) == list(range(25))
    assert page_slice(rows, 3, 25) == list(range(50, 60))
    assert page_slice(rows, 4, 25) == []
    assert page_label(60, 1, 25) == 'Showing 1–25 of 60'
    assert page_label(60, 3, 25) == 'Showing 51–60 of 60'
    assert page_label(0, 1, 25) == 'Showing 0 of 0'


def test_verdict_reason_names_the_rule():
    people = dataset()
    flagged = next(
        p
        for p in people
        if p['in_120th'] == 'yes' and (latest_record(p) or {})['aipac_udp_flag'] is True
    )
    reason = verdict_reason(explore_data.headline(flagged), 'balanced', 'the balanced rule')
    assert 'Flagged' in reason and 'every preset' in reason
    clean = next(
        p for p in people if p['in_120th'] == 'yes' and (latest_record(p) or {})['clean'] is True
    )
    assert 'no net dirty money' in verdict_reason(
        explore_data.headline(clean), 'balanced', 'the balanced rule'
    )
    unjudged = next(
        p for p in people if p['in_120th'] == 'yes' and (latest_record(p) or {})['clean'] is None
    )
    assert verdict_reason(explore_data.headline(unjudged), 'balanced', 'the balanced rule')


def test_explore_aggregates_shape():
    agg = explore_aggregates(dataset(), 'balanced', 2028)
    assert set(agg) == {
        'preset',
        'next_cycle',
        'overview',
        'leaderboards',
        'clean',
        'breakdown',
        'targets',
    }
    assert set(agg['overview']) == {'House', 'Senate'}
    assert set(agg['leaderboards']) == {
        'dirty_term',
        'dirty_career',
        'total_accepted',
        'udp_benefit',
        'self_funding',
        'all_ie',
    }

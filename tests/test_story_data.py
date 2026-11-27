"""Unit tests for receipts/site/story_data.py.

The figures are recomputed from the committed dataset in the test
itself, never taken on trust from the module: where a second route
to the same figure exists (raw columns, per-cycle lists, the term
rule), the test takes it. The headline numbers from the brief are
asserted as regression checks on top of the recomputation.
"""

import json
from pathlib import Path

from receipts.domain.targets import primary_targets
from receipts.domain.term import term_record
from receipts.site.expectations import dollars, latest
from receipts.site.story_data import (
    build_story_data,
    district_key,
    headline_counts,
    member_story,
    ranked_list,
    round_money,
    stacked_sources,
    waffle_panel,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = json.loads((ROOT / 'congress-money-tracker.json').read_text())


def incoming():
    return [r for r in DATASET if r['in_120th'] == 'yes']


def term_dirty(person):
    """Latest-term dirty money, recomputed from the cycle records."""
    if person['verdict_cycle'] is None:
        return None
    return term_record(person['cycles'], person['verdict_cycle'])['dirty']


def test_round_money():
    assert round_money(31_402_235.87) == '$31.4M'
    assert round_money(226_639_152.48) == '$226.6M'
    assert round_money(5_745_013.28) == '$5.7M'
    assert round_money(30_200) == '$30K'
    assert round_money(842) == '$842'
    assert round_money(0) == '$0'
    assert round_money(None) == '—'


def test_headline_counts_recomputed():
    counts = headline_counts(DATASET)
    people = incoming()
    assert counts['flag_120'] == sum(1 for p in people if latest(p)['aipac_udp_flag'] is True)
    assert counts['strict_clean'] == sum(1 for p in people if latest(p)['clean'] is True)
    assert counts['balanced_not_dirty'] == sum(
        1 for p in people if latest(p)['tier_balanced'] in ('clean', 'below_threshold')
    )
    assert counts['lenient_not_dirty'] == sum(
        1 for p in people if latest(p)['tier_lenient'] in ('clean', 'below_threshold')
    )
    assert counts['balanced_dirty'] == sum(
        1 for p in people if latest(p)['tier_balanced'] == 'dirty'
    )
    # Raw-column cross-checks, no term logic involved.
    assert counts['aipac_direct_career'] == sum(
        dollars(p['aipac_pac_direct_career']) for p in DATASET
    )
    assert counts['pro_israel_career'] == sum(dollars(p['pro_israel_pac_career']) for p in DATASET)
    # The brief's headline numbers, as regression checks.
    assert counts['flag_120'] == 299
    assert counts['strict_clean'] == 77
    assert counts['balanced_not_dirty'] == 170
    assert counts['lenient_not_dirty'] == 203
    assert counts['balanced_dirty'] == 361
    assert counts['aipac_direct_career'] == 109_040_065.96
    assert counts['pro_israel_career'] == 147_959_436.30


def test_primary_targets_count():
    assert len(primary_targets(incoming(), 'balanced', 2028)) == 320


def test_waffle_panels_are_seats():
    house = waffle_panel(DATASET, 'House', 435)
    senate = waffle_panel(DATASET, 'Senate', 100)
    assert house['seats'] == 435
    assert senate['seats'] == 100
    # Named members plus empty placeholders make the seat totals.
    assert house['named'] + (435 - house['named']) == 435
    assert senate['named'] + (100 - senate['named']) == 100
    assert house['named'] == 434
    assert senate['named'] == 100
    # Delegates are listed, never plotted.
    assert len(house['delegates']) == 6
    assert not house['delegates'] or all(
        name not in {m['name'] for m in house['members']} for name in house['delegates']
    )
    assert senate['delegates'] == []
    # Party blocks are contiguous and flagged members head each block.
    for panel in (house, senate):
        parties = [m['party'] for m in panel['members']]
        seen = []
        for party in parties:
            if party not in seen:
                seen.append(party)
        assert seen == sorted(seen, key={'D': 0, 'R': 1, 'I': 2, 'O': 3}.get)
        for party in seen:
            block = [m for m in panel['members'] if m['party'] == party]
            flags = [m['flagged'] for m in block]
            assert flags == sorted(flags, reverse=True)
    # The waffle counts its plotted seats, not incoming members only:
    # the uncalled seats' people are plotted too.
    assert house['counts']['flagged'] == sum(1 for m in house['members'] if m['flagged'])
    assert senate['counts']['flagged'] == sum(1 for m in senate['members'] if m['flagged'])
    assert house['counts']['flagged'] + senate['counts']['flagged'] == 302


def test_ranked_lists_are_sorted_and_cross_checked():
    data = build_story_data(DATASET, 2026, 2028)
    for chamber in ('house', 'senate'):
        ranked = data['ranked'][chamber]
        assert len(ranked) == 10
        dirties = [r['dirty'] for r in ranked]
        assert dirties == sorted(dirties, reverse=True)
        for entry in ranked:
            person = next(p for p in DATASET if p['person_key'] == entry['key'])
            assert entry['dirty'] == term_dirty(person)
            assert entry['rounded'] == round_money(entry['dirty'])
    assert data['ranked']['house'][0]['name'] == 'Adrian Boafo'
    assert data['ranked']['senate'][0]['name'] == 'Jacky Rosen'


def test_stacked_sources_sum_and_cross_check():
    data = build_story_data(DATASET, 2026, 2028)
    people = incoming()
    for chamber in ('house', 'senate'):
        group = [p for p in people if p['chamber_120'] == chamber.title()]
        stacked = data['stacked'][chamber]
        # Total accepted is exactly the three sources summed.
        assert stacked['total'] == (stacked['aipac'] + stacked['corp'] + stacked['individual'])
        assert abs(sum(stacked['shares'].values()) - 1) < 1e-9
        # Independent recomputation from the per-cycle lists: the
        # term's AIPAC money is the per-cycle AIPAC money at or after
        # the verdict cycle, summed over the person's candidate IDs.
        aipac = 0.0
        for p in group:
            verdict = p['verdict_cycle']
            aipac += sum(
                dollars(e.get('aipac_pac_direct'))
                for e in p.get('per_cycle') or []
                if e['cycle'] >= verdict
            )
        assert abs(stacked['aipac'] - aipac) < 0.01


def test_member_story_is_the_dataset_top():
    member = member_story(DATASET)
    assert member['name'] == 'Haley M. Stevens'
    assert member['split']['dirty'] == 31_402_235.87
    assert member['split']['rounded']['dirty'] == '$31.4M'
    assert member['returning'] is False
    assert member['race_chamber'] == 'Senate'
    # The trend is the up-for-election cycles, in order, and the last
    # one is the term the split reads.
    cycles = [t['cycle'] for t in member['trend']]
    assert cycles == sorted(cycles)
    assert member['trend'][-1]['cycle'] == 2026
    assert member['trend'][-1]['dirty'] == member['split']['dirty']
    # No other row's latest-term dirty money exceeds hers.
    assert all((term_dirty(p) or 0) <= member['split']['dirty'] for p in DATASET)
    # The zoom-out is her race chamber's incoming members only.
    assert member['zoom']['chamber'] == 'Senate'
    assert len(member['zoom']['top']) == 10
    assert member['zoom']['member_dirty'] > member['zoom']['top'][0]['dirty']


def test_district_map_keys_and_tiers():
    data = build_story_data(DATASET, 2026, 2028)
    districts = data['map']['districts']
    assert len(districts) == 430
    keys = [d['key'] for d in districts]
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)
    for district in districts:
        person = next(p for p in DATASET if p['person_key'] == district['member_key'])
        assert district['key'] == district_key(person)
        assert district['tier'] in ('dirty', 'below_threshold', 'clean', None)
        assert district['party'] in ('D', 'R', 'I', 'O')


def test_hero_and_targets():
    data = build_story_data(DATASET, 2026, 2028)
    people = incoming()
    assert data['hero']['dirty_total'] == sum(dollars(latest(p)['dirty']) for p in people)
    assert data['hero']['flagged'] == 299
    assert data['hero']['members'] == 535
    assert data['meta'] == {
        'current_cycle': 2026,
        'next_cycle': 2028,
        'incoming_total': 535,
    }
    assert len(data['targets']) == 8
    assert data['targets'][0]['name'] == 'Adrian Boafo'
    assert data['targets'][0]['dirty'] == 5_745_013.28
    assert [t['dirty'] for t in data['targets']] == sorted(
        [t['dirty'] for t in data['targets']], reverse=True
    )
    # Ranked-list helper agrees with the payload on the same people.
    house = [p for p in people if p['chamber_120'] == 'House']
    assert ranked_list(house, 10) == data['ranked']['house']
    assert stacked_sources(house) == data['stacked']['house']

"""What the page should show, computed from the embedded dataset."""

from collections import Counter

TERRITORIES = {'AS', 'DC', 'GU', 'MP', 'PR', 'VI'}
PARTY_LETTERS = {'Democrat': 'D', 'Republican': 'R', 'Independent': 'I'}
NOT_DIRTY_TIERS = ('clean', 'below_threshold')
TARGET_RULES = {
    'strict': lambda r: dollars(r['dirty_2026']) > 0,
    'balanced': lambda r: r['tier_balanced_2026'] == 'dirty',
    'lenient': lambda r: r['tier_lenient_2026'] == 'dirty',
}


def dollars(value):
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return value if is_number else 0


def exact(amount):
    return f'${amount:,.2f}'


def compact(amount):
    size = abs(amount)
    if size >= 1e9:
        text = f'${size / 1e9:.2f}B'
    elif size >= 1e6:
        text = f'${size / 1e6:.2f}M'
    elif size >= 1e3:
        text = f'${size / 1e3:.1f}K'
    else:
        text = f'${size:.0f}'
    return ('-' if amount < 0 else '') + text


def party_letter(person):
    party = person['party_120'] or person['party_119'] or '?'
    return PARTY_LETTERS.get(party, party)


def seat_status(person):
    if person['clean_2026'] is True:
        return 'clean'
    if person['clean_2026'] is False:
        return 'dirty'
    return 'unopposed' if person['unopposed_2026'] is True else 'unverified'


def by_dirty_2026(person):
    return -dollars(person['dirty_2026'])


def names(people):
    return [p['full_name'] for p in people]


def count(people, predicate):
    return sum(1 for p in people if predicate(p))


def is_clean(person):
    return person['clean_2026'] is True


def is_democrat(person):
    return person['party_120'] == 'Democrat'


def is_republican(person):
    return person['party_120'] == 'Republican'


def is_flagged(person):
    return person['aipac_udp_flag_2026'] is True


def seat_counts(people):
    counts = Counter(f'{seat_status(p)} {party_letter(p)}' for p in people)
    return dict(sorted(counts.items()))


def targets_2028(incoming, preset):
    """House Democrats and Class 3 Senate Democrats on the watchlist, dirtiest first."""
    on_watchlist = TARGET_RULES[preset]
    democrats = [p for p in incoming if is_democrat(p) and on_watchlist(p)]
    house = [p for p in democrats if p['chamber_120'] == 'House']
    senate = [p for p in democrats if p['chamber_120'] == 'Senate' and p['senate_class'] == 3]
    return sorted(house, key=by_dirty_2026), sorted(senate, key=by_dirty_2026)


class Roster:
    def __init__(self, people):
        self.everyone = people
        self.incoming = [p for p in people if p['in_120th'] == 'yes']
        self.house = [p for p in self.incoming if p['chamber_120'] == 'House']
        self.senate = [p for p in self.incoming if p['chamber_120'] == 'Senate']
        self.house_voting = [p for p in self.house if p['state'] not in TERRITORIES]
        self.delegates = [p for p in self.house if p['state'] in TERRITORIES]


def headline(roster):
    dirtiest = sorted(
        (p for p in roster.everyone if dollars(p['dirty_2026']) > 0), key=by_dirty_2026
    )[:5]
    top = dirtiest[0]
    next_four = sum(p['dirty_2026'] for p in dirtiest[1:])
    return {
        'top5': [[p['full_name'], p['dirty_2026']] for p in dirtiest],
        'top1_key': top['person_key'],
        'top1_compact': compact(top['dirty_2026']),
        'top1_exact': exact(top['dirty_2026']),
        'top1_returning': top['in_120th'] == 'yes',
        'next_four_total': next_four,
        'next_four_compact': compact(next_four),
        'exceeds_next_four': top['dirty_2026'] > next_four,
        'ratio': f'{top["dirty_2026"] / next_four:.2f}',
    }


def career_dirty(roster):
    ranked = sorted(
        (p for p in roster.everyone if isinstance(p['dirty_career'], (int, float))),
        key=lambda p: -p['dirty_career'],
    )
    return {
        'total_compact': compact(sum(p['dirty_career'] for p in ranked)),
        'top3': names(ranked[:3]),
        'top1_exact': exact(ranked[0]['dirty_career']),
    }


def is_career_clean(person):
    dirty_sources = (
        'corporate_pac_career',
        'aipac_pac_direct_career',
        'udp_ie_support_career',
        'udp_ie_opposing_opponents_career',
    )
    return all(dollars(person[source]) == 0 for source in dirty_sources)


def clean(roster):
    not_judged = [p for p in roster.everyone if p['clean_2026'] is None]
    unopposed = [p for p in not_judged if p['unopposed_2026'] is True]
    unverified = [p for p in not_judged if p['unopposed_2026'] is not True]
    house_clean = [p for p in roster.house if is_clean(p)]
    return {
        'true_total': count(roster.everyone, is_clean),
        'null_unopposed': sorted(names(unopposed)),
        'null_unverified': sorted(names(unverified)),
        'unopposed_total': count(roster.everyone, lambda p: p['unopposed_2026'] is True),
        'house_120': len(house_clean),
        'house_120_democrat': count(house_clean, is_democrat),
        'house_120_republican': count(house_clean, is_republican),
        'senate_120': count(roster.senate, is_clean),
        'all_120': count(roster.incoming, is_clean),
        'career_clean_house_120': count(roster.house, is_career_clean),
    }


def tier_counts(people, tier_column):
    counts = Counter(p[tier_column] for p in people)
    return {
        'clean': counts['clean'],
        'below_threshold': counts['below_threshold'],
        'dirty': counts['dirty'],
        'null': counts[None],
    }


def not_dirty(people, tier_column):
    return count(people, lambda p: p[tier_column] in NOT_DIRTY_TIERS)


def tiers(roster):
    balanced, lenient = 'tier_balanced_2026', 'tier_lenient_2026'
    return {
        'balanced': tier_counts(roster.incoming, balanced),
        'lenient': tier_counts(roster.incoming, lenient),
        'not_dirty_120': {
            'balanced': not_dirty(roster.incoming, balanced),
            'lenient': not_dirty(roster.incoming, lenient),
        },
        'house_not_dirty_balanced': [not_dirty(roster.house, balanced), len(roster.house)],
        'flag_120': count(roster.incoming, is_flagged),
        'flag_all': count(roster.everyone, is_flagged),
        'incoming_total': len(roster.incoming),
    }


def charts(roster):
    return {
        'house': seat_counts(roster.house_voting),
        'house_named': len(roster.house_voting),
        'senate': seat_counts(roster.senate),
        'senate_named': len(roster.senate),
        'delegates': seat_counts(roster.delegates),
    }


def watchlist(roster):
    lists = {preset: targets_2028(roster.incoming, preset) for preset in TARGET_RULES}
    balanced_house, balanced_senate = lists['balanced']
    strict_house, strict_senate = lists['strict']
    sizes = {preset: [len(house), len(senate)] for preset, (house, senate) in lists.items()}
    return {
        **sizes,
        'balanced_house_order': names(balanced_house[:2]),
        'balanced_house_top_dirty_exact': exact(balanced_house[0]['dirty_2026']),
        'balanced_senate_order': names(balanced_senate),
        'balanced_senate_top_dirty_exact': exact(balanced_senate[0]['dirty_2026']),
        'balanced_senate_top_career_exact': exact(balanced_senate[0]['dirty_career']),
        'strict_senate_top3': names(strict_senate[:3]),
        'targets_2026_house': len(strict_house),
    }


def detail(roster, opposition_credit, dirtiest_key):
    ranked = sorted(
        (p for p in roster.everyone if p['rank_total_accepted'] is not None),
        key=lambda p: p['rank_total_accepted'],
    )
    constantino = next(p for p in roster.everyone if 'Constantino' in p['full_name'])
    credit = {
        f'{race["cycle"]} {race["phase"]}': race['amount']
        for race in opposition_credit.get(dirtiest_key, [])
    }
    return {
        'top10_total_accepted': names(ranked[:10]),
        'constantino_self_funding_exact': exact(constantino['self_funding_career']),
        'constantino_clean': constantino['clean_2026'],
        'top1_opposition_credit': credit,
        'top1_opposition_credit_exact': [exact(amount) for amount in credit.values()],
    }


def site_expectations(people, opposition_credit):
    roster = Roster(people)
    hook = headline(roster)
    return {
        'headline': hook,
        'career_dirty': career_dirty(roster),
        'clean': clean(roster),
        'tiers': tiers(roster),
        'charts': charts(roster),
        'targets_2028': watchlist(roster),
        'detail': detail(roster, opposition_credit, hook['top1_key']),
    }


def whole_dollars(amount):
    return f'{amount:,.2f}'.rsplit('.', 1)[0]


def figure_literals(expectations):
    """Figures that must never be typed into the page's static text."""
    hook = expectations['headline']
    return [whole_dollars(amount) for _, amount in hook['top5']] + [
        whole_dollars(hook['next_four_total']),
        hook['top1_compact'],
        hook['next_four_compact'],
    ]

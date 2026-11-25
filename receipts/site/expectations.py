"""What the page should show, computed from the embedded dataset."""

from collections import Counter

from receipts.common.settings import settings
from receipts.domain.clean_2026 import is_career_clean
from receipts.domain.targets import DIRTY_UNDER, latest_record, primary_targets

PARTY_LETTERS = {'Democrat': 'D', 'Republican': 'R', 'Independent': 'I'}
NOT_DIRTY_TIERS = ('clean', 'below_threshold')
# What the page shows for someone with no latest election (no cycle was up).
NO_RECORD = {
    'dirty': None,
    'clean': None,
    'tier_balanced': None,
    'tier_lenient': None,
    'unopposed': False,
    'aipac_udp_flag': False,
}


def latest(person):
    """The record the page's default view reads: the person's latest election."""
    return latest_record(person) or NO_RECORD


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


def by_dirty(person):
    return -dollars(latest(person)['dirty'])


def names(people):
    return [p['full_name'] for p in people]


def count(people, predicate):
    return sum(1 for p in people if predicate(p))


def is_clean(person):
    return latest(person)['clean'] is True


def is_democrat(person):
    return person['party_120'] == 'Democrat'


def is_republican(person):
    return person['party_120'] == 'Republican'


def is_flagged(person):
    return latest(person)['aipac_udp_flag'] is True


class Roster:
    def __init__(self, people):
        self.everyone = people
        self.incoming = [p for p in people if p['in_120th'] == 'yes']
        self.house = [p for p in self.incoming if p['chamber_120'] == 'House']
        self.senate = [p for p in self.incoming if p['chamber_120'] == 'Senate']


def headline(roster):
    dirtiest = sorted(
        (p for p in roster.everyone if dollars(latest(p)['dirty']) > 0), key=by_dirty
    )[:5]
    top = dirtiest[0]
    next_four = sum(latest(p)['dirty'] for p in dirtiest[1:])
    return {
        'top5': [[p['full_name'], latest(p)['dirty']] for p in dirtiest],
        'top1_key': top['person_key'],
        'top1_compact': compact(latest(top)['dirty']),
        'top1_exact': exact(latest(top)['dirty']),
        'top1_returning': top['in_120th'] == 'yes',
        'next_four_total': next_four,
        'next_four_compact': compact(next_four),
        'exceeds_next_four': latest(top)['dirty'] > next_four,
        'ratio': f'{latest(top)["dirty"] / next_four:.2f}',
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


def clean(roster):
    not_judged = [p for p in roster.everyone if latest(p)['clean'] is None]
    unopposed = [p for p in not_judged if latest(p)['unopposed'] is True]
    unverified = [p for p in not_judged if latest(p)['unopposed'] is not True]
    house_clean = [p for p in roster.house if is_clean(p)]
    return {
        'true_total': count(roster.everyone, is_clean),
        'null_unopposed': sorted(names(unopposed)),
        'null_unverified': sorted(names(unverified)),
        'unopposed_total': count(roster.everyone, lambda p: latest(p)['unopposed'] is True),
        'house_120': len(house_clean),
        'house_120_democrat': count(house_clean, is_democrat),
        'house_120_republican': count(house_clean, is_republican),
        'senate_120': count(roster.senate, is_clean),
        'all_120': count(roster.incoming, is_clean),
        'career_clean_house_120': count(roster.house, is_career_clean),
    }


def tier_counts(people, tier_column):
    counts = Counter(latest(p)[tier_column] for p in people)
    return {
        'clean': counts['clean'],
        'below_threshold': counts['below_threshold'],
        'dirty': counts['dirty'],
        'null': counts[None],
    }


def not_dirty(people, tier_column):
    return count(people, lambda p: latest(p)[tier_column] in NOT_DIRTY_TIERS)


def tiers(roster):
    balanced, lenient = 'tier_balanced', 'tier_lenient'
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


def targets(roster):
    cycle = settings().cycles.next
    lists = {p: primary_targets(roster.incoming, p, cycle) for p in DIRTY_UNDER}
    by_chamber = {
        preset: [[p for p in people if p['chamber_120'] == c] for c in ('House', 'Senate')]
        for preset, people in lists.items()
    }
    house, senate = by_chamber['balanced']
    return {
        **{preset: [len(h), len(s)] for preset, (h, s) in by_chamber.items()},
        'balanced_top3': names(lists['balanced'][:3]),
        'balanced_top_dirty_exact': exact(latest(lists['balanced'][0])['dirty']),
        'balanced_house_top': names(house[:1]),
        'balanced_senate_top': names(senate[:1]),
        'balanced_parties': dict(
            sorted(Counter(party_letter(p) for p in lists['balanced']).items())
        ),
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
        'constantino_clean': latest(constantino)['clean'],
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
        'targets': targets(roster),
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

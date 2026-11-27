"""Explore aggregates: pure functions, dataset in, Explore figures out.

Every function takes dataset rows (dicts as loaded from the dataset
JSON) and returns plain values. No file or network access, no settings
read: the caller supplies the preset name and the next cycle. Tier
columns already stored on each row carry the preset logic, so no
threshold lives here.

Aggregate payload shape (``explore_aggregates`` returns this dict):

    {
      "preset": <preset name>,
      "next_cycle": <cycle>,
      "overview": {
        "House": <chamber overview>,
        "Senate": <chamber overview>,
      },
      "leaderboards": {
        "dirty_term": [<leaderboard entry>],
        "dirty_career": [<leaderboard entry>],
        "total_accepted": [<leaderboard entry>],
        "udp_benefit": [<leaderboard entry>],
        "self_funding": [<leaderboard entry>],
        "all_ie": [<leaderboard entry>],
      },
      "clean": <clean figures>,
      "breakdown": [<party-by-chamber row>],
      "targets": [<primary-target row>],
    }

A chamber overview is:

    {
      "members": <incoming members in the chamber>,
      "total_accepted": <career total accepted>,
      "flagged": <flagged members>,
      "flagged_share": <flagged share of the chamber>,
      "top_source": {"source": <family name>, "total": <career total>},
      "waffle": [<waffle block>],
      "delegates": [<delegate full name>],
    }

A waffle block is ``{"party": ..., "flagged": <bool>, "count": ...}`` in
display order: each party's flagged block first, then its unflagged
block, then the unjudged block, then the uncalled block. The House
waffle counts voting seats only; delegates are listed, not plotted,
and uncalled seats fill the chamber to its full size. The Senate
waffle counts named senators, with uncalled seats filling it the
same way.

A leaderboard entry is:

    {
      "person_key": ..., "full_name": ..., "party": ..., "place": ...,
      "amount": <career or term money>,
    }

Clean figures are:

    {
      "incoming_not_dirty": <count>,
      "by_chamber": {"House": <count>, "Senate": <count>},
      "career_clean_house": <count>,
      "unopposed": [<full name>],
      "unverified": [<full name>],
    }

A party-by-chamber row is:

    {
      "party": ..., "chamber": ...,
      "members": <count>,
      "individual": <career total>, "corporate_pac": <career total>,
      "aipac": <career total>, "total_accepted": <career total>,
      "udp_benefit": <career total>, "self_funding": <career total>,
      "all_ie_total": <career total>,
      "not_dirty": <count under the preset>,
    }

A primary-target row is:

    {
      "person_key": ..., "full_name": ..., "party": ..., "place": ...,
      "election": <cycle judged>,
      "dirty": ..., "corporate_pac": ..., "aipac": ...,
      "udp_benefit": ..., "dirty_career": ..., "individual": ...,
    }
"""

from receipts.domain.clean_2026 import is_career_clean, is_not_dirty
from receipts.domain.targets import latest_record, primary_targets

HOUSE_SEATS = 435
SENATE_SEATS = 100
TERRITORIES = frozenset({'AS', 'GU', 'MP', 'PR', 'VI', 'DC'})
PARTY_ORDER = {'Democrat': 0, 'Republican': 1, 'Independent': 2}
CHAMBER_ORDER = {'House': 0, 'Senate': 1}
SOURCE_FAMILIES = (
    ('individual', 'individual_contribution_total_career'),
    ('corporate_pac', 'corporate_pac_career'),
    ('aipac', 'aipac_pac_direct_career'),
    ('udp_benefit', 'udp_ie_total_benefit_career'),
)
NO_RECORD = {
    'dirty': None,
    'clean': None,
    'tier_balanced': None,
    'tier_lenient': None,
    'unopposed': False,
    'aipac_udp_flag': False,
}


def dollars(value):
    """A money cell as a number: unknown or missing money counts as zero."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return 0


def headline(person):
    """The record the default view reads: the person's latest election."""
    return latest_record(person) or NO_RECORD


def chamber_of(person):
    """The chamber the person sits in for the incoming Congress."""
    return person['chamber_120'] or person['chamber_119'] or ''


def party_of(person):
    """The party the person sits under for the incoming Congress."""
    return person['party_120'] or person['party_119'] or ''


def place_of(person):
    """State and district, or the state Senate seat."""
    district = person['district_120']
    if district in ('', None):
        district = person['district_119']
    if chamber_of(person) == 'Senate':
        return f'{person["state"]} · Senate'
    if district in ('', None):
        return person['state']
    return f'{person["state"]}-{district}'


def is_flagged(record):
    """Whether the record carries any AIPAC direct or UDP benefit dollar."""
    return record['aipac_udp_flag'] is True


def is_voting_house_member(person):
    """An incoming House member with a vote: not a territorial delegate."""
    return chamber_of(person) == 'House' and person['state'] not in TERRITORIES


# ---- the overview waffle: party blocks, flagged first ----
def _judged(members):
    return [p for p in members if headline(p)['tier_balanced'] is not None]


def _party_waffle_blocks(members, party):
    judged = _judged([p for p in members if party_of(p) == party])
    flagged = sum(1 for p in judged if is_flagged(headline(p)))
    return [
        {'party': party, 'flagged': True, 'count': flagged},
        {'party': party, 'flagged': False, 'count': len(judged) - flagged},
    ]


def waffle_blocks(members):
    """The waffle blocks for named members, in display order.

    Each party forms one block, its flagged members first; members
    with no verdict form the unjudged block at the end.
    """
    parties = sorted({party_of(p) for p in members}, key=lambda name: PARTY_ORDER.get(name, 3))
    blocks = [block for party in parties for block in _party_waffle_blocks(members, party)]
    blocks.append({'party': None, 'flagged': False, 'count': len(members) - len(_judged(members))})
    return [b for b in blocks if b['count']]


def chamber_overview(members, waffle_members, seats):
    """One chamber's overview strip numbers and waffle blocks.

    Counts cover every incoming member of the chamber; the waffle
    plots voting seats only, with uncalled seats filling it to the
    chamber's full size.
    """
    total_accepted = sum(dollars(p['total_accepted_career']) for p in members)
    flagged = sum(1 for p in members if is_flagged(headline(p)))
    sources = [(name, sum(dollars(p[column]) for p in members)) for name, column in SOURCE_FAMILIES]
    top_name, top_total = max(sources, key=lambda item: item[1])
    waffle = waffle_blocks(waffle_members)
    uncalled = seats - len(waffle_members)
    if uncalled:
        waffle = [*waffle, {'party': None, 'flagged': None, 'count': uncalled}]
    return {
        'members': len(members),
        'total_accepted': total_accepted,
        'flagged': flagged,
        'flagged_share': (flagged / len(members)) if members else None,
        'top_source': {'source': top_name, 'total': top_total},
        'waffle': waffle,
        'delegates': sorted(p['full_name'] for p in members if not is_voting_house_member(p)),
    }


def overview(people):
    """The overview strip: one entry per chamber, never combined."""
    incoming = [p for p in people if p['in_120th'] == 'yes']
    house = [p for p in incoming if chamber_of(p) == 'House']
    house_voting = [p for p in house if is_voting_house_member(p)]
    senate = [p for p in incoming if chamber_of(p) == 'Senate']
    return {
        'House': chamber_overview(house, house_voting, HOUSE_SEATS),
        'Senate': chamber_overview(senate, senate, SENATE_SEATS),
    }


# ---- leaderboards ----
def leaderboard_entry(person, amount):
    """One leaderboard row: who, where, and how much."""
    return {
        'person_key': person['person_key'],
        'full_name': person['full_name'],
        'party': party_of(person),
        'place': place_of(person),
        'amount': amount,
    }


def top_by_amount(people, amount_of, limit):
    """The largest amounts first, people with no amount last and cut."""
    ranked = sorted(people, key=lambda p: -dollars(amount_of(p)))
    return [
        leaderboard_entry(p, dollars(amount_of(p))) for p in ranked if dollars(amount_of(p)) > 0
    ][:limit]


def top_by_rank(people, rank_key, amount_key, limit):
    """The best ranks first, unranked people excluded."""
    ranked = [p for p in people if p[rank_key] is not None]
    ranked.sort(key=lambda p: p[rank_key])
    return [leaderboard_entry(p, dollars(p[amount_key])) for p in ranked[:limit]]


def leaderboards(people, preset):
    """The relocated leaderboard lists: dirty money leads, then scale.

    Individual contributions are not dirty money, so the dirty lists
    lead and total accepted follows as a scale measure.
    """
    dirty_term = [p for p in people if dollars(headline(p)['dirty']) > 0]
    return {
        'dirty_term': top_by_amount(dirty_term, lambda p: headline(p)['dirty'], 20),
        'dirty_career': top_by_amount(people, lambda p: p['dirty_career'], 20),
        'total_accepted': top_by_rank(people, 'rank_total_accepted', 'total_accepted_career', 20),
        'udp_benefit': top_by_rank(
            people, 'rank_udp_total_benefit', 'udp_ie_total_benefit_career', 10
        ),
        'self_funding': top_by_rank(people, 'rank_self_funding', 'self_funding_career', 10),
        'all_ie': top_by_rank(people, 'rank_all_ie_total', 'all_ie_total_career', 10),
    }


# ---- clean figures ----
def _member_is_not_dirty(person, preset, tier_key):
    record = headline(person)
    if preset == 'strict':
        return record['clean'] is True
    return is_not_dirty(record[tier_key])


def _count_by_chamber(people):
    return {
        chamber: sum(1 for p in people if chamber_of(p) == chamber)
        for chamber in ('House', 'Senate')
    }


def _not_judged(people):
    return [p for p in people if headline(p)['clean'] is None]


def _unopposed_names(people):
    return sorted(p['full_name'] for p in people if headline(p)['unopposed'] is True)


def _unverified_names(people):
    return sorted(p['full_name'] for p in people if headline(p)['unopposed'] is not True)


def _career_clean_house(incoming):
    return sum(1 for p in incoming if chamber_of(p) == 'House' and is_career_clean(p))


def clean_figures(people, preset):
    """Who is not dirty under the preset, and who was not judged."""
    incoming = [p for p in people if p['in_120th'] == 'yes']
    tier_key = 'tier_balanced' if preset == 'balanced' else 'tier_lenient'
    not_dirty = [p for p in incoming if _member_is_not_dirty(p, preset, tier_key)]
    not_judged = _not_judged(people)
    return {
        'incoming_not_dirty': len(not_dirty),
        'by_chamber': _count_by_chamber(not_dirty),
        'career_clean_house': _career_clean_house(incoming),
        'unopposed': _unopposed_names(not_judged),
        'unverified': _unverified_names(not_judged),
    }


# ---- party breakdown ----
def party_breakdown(people, preset):
    """Career money and not-dirty counts, grouped by party and chamber."""
    incoming = [p for p in people if p['in_120th'] == 'yes']
    tier_key = 'tier_balanced' if preset == 'balanced' else 'tier_lenient'
    groups = {}
    for person in incoming:
        key = (party_of(person), chamber_of(person))
        group = groups.setdefault(
            key,
            {
                'party': party_of(person),
                'chamber': chamber_of(person),
                'members': 0,
                'individual': 0,
                'corporate_pac': 0,
                'aipac': 0,
                'total_accepted': 0,
                'udp_benefit': 0,
                'self_funding': 0,
                'all_ie_total': 0,
                'not_dirty': 0,
            },
        )
        group['members'] += 1
        group['individual'] += dollars(person['individual_contribution_total_career'])
        group['corporate_pac'] += dollars(person['corporate_pac_career'])
        group['aipac'] += dollars(person['aipac_pac_direct_career'])
        group['total_accepted'] += dollars(person['total_accepted_career'])
        group['udp_benefit'] += dollars(person['udp_ie_total_benefit_career'])
        group['self_funding'] += dollars(person['self_funding_career'])
        group['all_ie_total'] += dollars(person['all_ie_total_career'])
        record = headline(person)
        clean = record['clean'] is True if preset == 'strict' else is_not_dirty(record[tier_key])
        if clean:
            group['not_dirty'] += 1
    rows = sorted(
        groups.values(),
        key=lambda g: (
            CHAMBER_ORDER.get(g['chamber'], 2),
            PARTY_ORDER.get(g['party'], 3),
        ),
    )
    return rows


# ---- primary targets ----
def primary_targets_list(people, preset, next_cycle):
    """The watchlist rows: seat up next cycle, dirty in the latest election."""
    incoming = [p for p in people if p['in_120th'] == 'yes']
    rows = []
    for person in primary_targets(incoming, preset, next_cycle):
        record = headline(person)
        rows.append(
            {
                'person_key': person['person_key'],
                'full_name': person['full_name'],
                'party': party_of(person),
                'place': place_of(person),
                'election': record['cycle'],
                'dirty': dollars(record['dirty']),
                'corporate_pac': dollars(record['corp']),
                'aipac': dollars(record['aipac_direct']),
                'udp_benefit': dollars(record['udp_benefit']),
                'dirty_career': dollars(person['dirty_career']),
                'individual': dollars(record['individual']),
            }
        )
    return rows


# ---- the grouped default order and pagination ----
def grouped_order(people):
    """The table's default order: chamber sections, party blocks, flagged first.

    House rows form one section, then Senate rows; inside a section
    each party sits together, flagged members at the head of their
    party's block, then by dirty money, then by name. Members with no
    chamber sit after both sections.
    """

    def key(person):
        record = headline(person)
        return (
            CHAMBER_ORDER.get(chamber_of(person), 2),
            PARTY_ORDER.get(party_of(person), 3),
            0 if is_flagged(record) else 1,
            -dollars(record['dirty']),
            person['full_name'].casefold(),
        )

    return sorted(people, key=key)


def page_slice(rows, page, page_size):
    """One page of rows: the slice for a one-based page number."""
    start = (page - 1) * page_size
    return rows[start : start + page_size]


def page_label(total, page, page_size):
    """The showing line for a page: first–last of the total."""
    if total == 0:
        return 'Showing 0 of 0'
    first = (page - 1) * page_size + 1
    last = min(total, page * page_size)
    return f'Showing {first}–{last} of {total}'


# ---- the drawer's plain-English verdict reason ----
def verdict_reason(record, preset, preset_short):
    """The plain-English rule behind one member's verdict.

    ``preset_short`` is the preset's short rule text as the caller
    states it (the thresholds live in config, not here). The flag is
    not tolerance-based: any flagged dollar flags the member under
    every preset, and a flagged member is never clean even when
    refunds elsewhere make the net negative.
    """
    tier_key = 'tier_balanced' if preset == 'balanced' else 'tier_lenient'
    if preset == 'strict':
        clean = record['clean']
        tier = None if clean is None else ('clean' if clean else 'dirty')
    else:
        tier = record[tier_key]
    if tier is None:
        if record['unopposed'] is True:
            return 'Unopposed: no opponent raised money, so no dirty money here is not a clean verdict.'
        return 'Unverified: no linked campaign filed money, so there is nothing to judge.'
    if is_flagged(record):
        return (
            'Flagged: took AIPAC PAC direct money or UDP benefit money. '
            'Any such dollar flags a member under every preset.'
        )
    if tier == 'dirty':
        return f'Dirty under the {preset} tolerance: {preset_short}.'
    if tier == 'below_threshold':
        return (
            f'Below threshold under the {preset} tolerance: took corporate '
            f'PAC money, but below the dirty line ({preset_short}). '
            'Below threshold is never called clean, and the amount is shown.'
        )
    return (
        'Clean: took no net dirty money — no corporate PAC, AIPAC PAC '
        'direct, or UDP benefit money in the term judged.'
    )


# ---- the whole payload ----
def explore_aggregates(people, preset, next_cycle):
    """The whole Explore payload, in the shape the docstring states."""
    return {
        'preset': preset,
        'next_cycle': next_cycle,
        'overview': overview(people),
        'leaderboards': leaderboards(people, preset),
        'clean': clean_figures(people, preset),
        'breakdown': party_breakdown(people, preset),
        'targets': primary_targets_list(people, preset, next_cycle),
    }

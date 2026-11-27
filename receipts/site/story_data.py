"""Story aggregates: the dataset in, the Story front door's figures out.

Pure functions only — no file reads, no network, no settings access.
The caller passes the dataset rows and the cycles; the build (or a
test) supplies them. Every figure the Story shows comes from here:
the static renderer formats these aggregates into HTML, and the
browser script renders the same aggregates into the same pictures,
so the two can never disagree about a number.

Aggregate payload (JSON shape, as returned by build_story_data):

    {
      "meta": {"current_cycle": 2026, "next_cycle": 2028,
               "incoming_total": 535},
      "preset": {"balanced_short": "corporate PAC over $100k and over 5% of receipts"},
      "hero": {"dirty_total": 226639152.48,
               "dirty_total_rounded": "$226.6M",
               "flagged": 299, "members": 535},
      "counts": {"flag_120": 299, "strict_clean": 77,
                 "balanced_not_dirty": 170, "lenient_not_dirty": 203,
                 "balanced_dirty": 361, "dirty_positive": 454,
                 "aipac_direct_career": 109040065.96,
                 "pro_israel_career": 147959436.30},
      "waffle": {"house": {"seats": 435, "named": 434,
                            "uncalled_seats": 5,
                            "delegates": ["..."],   # non-voting, listed not plotted
                            "members": [{"key", "name", "party": "D"|"R"|"I"|"O",
                                         "flagged": bool, "uncalled": bool},
                                        ... in layout order ...],
                            "counts": {"dem": 261, "rep": 173, "ind": 0, "other": 0,
                                       "flagged_dem": 87, "flagged_rep": 152,
                                       "flagged_ind": 0, "flagged_other": 0,
                                       "flagged": 241}},
                 "senate": {... same shape, 100 seats ...}},
      "ranked": {"house": [{"key", "name", "party", "seat", "dirty",
                             "rounded", "flagged"}, ... top 10 ...],
                 "senate": [... top 10 ...]},
      "stacked": {"house": {"aipac": ..., "corp": ..., "individual": ...,
                             "total": ...,   # total accepted: the three summed
                             "shares": {"aipac": 0.03, "corp": 0.11,
                                        "individual": 0.86}},
                  "senate": {...}},
      "member": {"key", "name", "party", "seat", "race_chamber": "Senate",
                 "returning": false,
                 "split": {"corp": ..., "aipac": ..., "individual": ...,
                           "udp_benefit": ..., "dirty": ...,
                           "rounded": {"corp": "$382K", ...}},
                 "trend": [{"cycle": 2018, "dirty": 30200.0,
                            "rounded": "$30K"}, ...],
                 "zoom": {"chamber": "Senate",
                          "top": [{"key", "name", "party", "dirty",
                                   "rounded"}, ... top 10 incoming ...],
                          "median": 663000.0, "median_rounded": "$663K",
                          "member_dirty": 31402235.87,
                          "member_rounded": "$31.4M"}},
      "map": {"districts": [{"key": "CA-04", "member_key", "name",
                              "party": "D"|"R"|"I"|"O",
                              "tier": "dirty"|"below_threshold"|"clean"|None,
                              "flagged": bool}, ...]},
      "targets": [{"key", "name", "party", "chamber", "seat", "dirty",
                   "rounded"}, ... top 8 ...],
      "targets_total": 320
    }

Definitions (methodology.md wins on every one):

- The story's population is the incoming 120th Congress
  (in_120th == "yes"), judged on the headline term — the verdict
  cycle and every cycle since, summed (methodology §14b). "Latest"
  below always means that term, via expectations.latest().
- Flagged means the AIPAC/UDP flag: any AIPAC PAC direct dollar or
  any UDP benefit dollar in the term, under every preset. The flag
  takes precedence over the net.
- The waffle plots SEATS, not members (methodology §17): 435 House
  seats and 100 Senate seats. Non-voting delegates are not plotted
  and are listed under the chart. A seat whose race is uncalled is
  plotted with the named person where one exists (their money is as
  filed) and as an empty placeholder where no member is named yet.
  One House seat has no member named at all in the roster. The
  waffle's flagged counts therefore differ from the incoming-only
  flag count: the waffle counts the plotted seats, counts.flag_120
  counts incoming members.
- The waffle layout order is fixed at build time: party blocks in
  D, R, other order, flagged members first inside their own party's
  block, then name. The browser never re-sorts; the steps only
  recolour, so no dot ever moves.
- Ranked lists and the stacked bars read incoming members only,
  by latest-term dirty money (corporate PAC + AIPAC direct + UDP
  benefit). The stacked total is total accepted — individual +
  corporate PAC + AIPAC direct — per chamber. UDP benefit is
  spending about a race, never money given to the campaign, so it
  is not part of the stacked total.
- Beat 4's member is the top latest-term dirty-money member over
  ALL rows, not incoming members only: the biggest dirty-money
  story in the dataset may belong to someone not returning. Their
  race chamber is the chamber of the candidacy that carried the
  most individual money in their verdict cycle (the candidate-ID
  prefix: H for House, S for Senate). The zoom-out shows incoming
  members of that chamber only.
"""

from receipts.domain.targets import primary_targets
from receipts.site.expectations import dollars, latest

# Voting seats in each chamber: structural facts, not results.
HOUSE_SEATS = 435
SENATE_SEATS = 100

# Non-voting delegates: no vote, so no waffle dot and no district on
# the map (methodology §17). At-large voting members (VT, ND, SD, DE,
# WY) are voting members and are plotted.
TERRITORIES = frozenset({'AS', 'DC', 'GU', 'MP', 'PR', 'VI'})

PARTY_ORDER = {'Democrat': 0, 'Republican': 1, 'Independent': 2}
PARTY_LETTER = {'Democrat': 'D', 'Republican': 'R', 'Independent': 'I'}


def round_money(value):
    """A story-round figure: $31.4M, $5.7M, $30K, $842 — never cents."""
    if value is None:
        return '—'
    if value == 'unknown':
        return 'unknown'
    if not isinstance(value, (int, float)):
        return str(value)
    neg = value < 0
    size = abs(value)
    if size >= 1e9:
        text = f'${size / 1e9:.1f}B'.replace('.0B', 'B')
    elif size >= 1e6:
        text = f'${size / 1e6:.1f}M'.replace('.0M', 'M')
    elif size >= 1e3:
        text = f'${size / 1e3:.0f}K'
    else:
        text = f'${size:,.0f}'
    return ('\u2212' if neg else '') + text


def party_of(person):
    """The party label the page shows: 120th, else 119th."""
    return person['party_120'] or person['party_119'] or ''


def party_letter(person):
    """D / R / I, or O for any other label."""
    return PARTY_LETTER.get(party_of(person), 'O')


def incoming_members(dataset):
    """The members of the incoming Congress."""
    return [r for r in dataset if r['in_120th'] == 'yes']


def is_flagged(person):
    """The AIPAC/UDP flag on the headline term."""
    return latest(person)['aipac_udp_flag'] is True


def waffle_members(people):
    """The plotted members in layout order: party blocks, flagged first.

    Dots never move between steps, so the order is fixed here: one
    contiguous block per party, flagged members at the head of their
    own party's block, then name for determinism.
    """
    ordered = sorted(
        people,
        key=lambda p: (
            PARTY_ORDER.get(party_of(p), 3),
            not is_flagged(p),
            p['full_name'].casefold(),
        ),
    )
    return [
        {
            'key': p['person_key'],
            'name': p['full_name'],
            'party': party_letter(p),
            'flagged': is_flagged(p),
            'uncalled': p['in_120th'] == 'unknown',
        }
        for p in ordered
    ]


def waffle_counts(members):
    """Per-party and flagged counts for one plotted chamber."""
    group = {'D': 'dem', 'R': 'rep', 'I': 'ind'}.get
    counts = {
        'dem': 0,
        'rep': 0,
        'ind': 0,
        'other': 0,
        'flagged': 0,
        'flagged_dem': 0,
        'flagged_rep': 0,
        'flagged_ind': 0,
        'flagged_other': 0,
    }
    for m in members:
        counts[group(m['party'], 'other')] += 1
        if m['flagged']:
            counts['flagged'] += 1
            counts['flagged_' + group(m['party'], 'other')] += 1
    return counts


def waffle_panel(dataset, chamber, seats):
    """One chamber's waffle: plotted members, placeholders, delegates."""
    incoming = [r for r in incoming_members(dataset) if r['chamber_120'] == chamber]
    if chamber == 'House':
        plotted = [r for r in incoming if r['state'] not in TERRITORIES]
        delegates = sorted(r['full_name'] for r in incoming if r['state'] in TERRITORIES)
        # Seats whose race is uncalled: the named person where one
        # exists (their 119th chamber names the seat).
        uncalled = [
            r for r in dataset if r['in_120th'] == 'unknown' and r['chamber_119'] == 'House'
        ]
        plotted = plotted + uncalled
    else:
        plotted = list(incoming)
        delegates = []
        uncalled = [
            r for r in dataset if r['in_120th'] == 'unknown' and r['chamber_119'] == 'Senate'
        ]
        plotted = plotted + uncalled
    members = waffle_members(plotted)
    placeholders = seats - len(members)
    if placeholders < 0:
        raise ValueError(f'{chamber} waffle: {len(members)} plotted over {seats} seats')
    return {
        'seats': seats,
        'named': len(members),
        'uncalled_seats': len(uncalled) + placeholders,
        'delegates': delegates,
        'members': members,
        'counts': waffle_counts(members),
    }


def seat_label(person):
    """'CA-04' for a House seat, 'CA · Senate' for a Senate seat."""
    if (person['chamber_120'] or person['chamber_119']) == 'Senate':
        return f'{person["state"]} · Senate'
    district = person['district_120'] or person['district_119']
    return person['state'] + (f'-{district}' if district not in ('', None) else '')


def district_key(person):
    """The Census district key: at-large seats are 00, DC's is 98."""
    n = int(person['district_120'] or person['district_119'] or 0)
    return person['state'] + '-' + ('98' if person['state'] == 'DC' else f'{n:02d}')


def ranked_list(people, count):
    """The dirtiest incoming members of one chamber, latest term."""
    ranked = sorted(people, key=lambda p: -dollars(latest(p)['dirty']))
    out = []
    for p in ranked[:count]:
        dirty = dollars(latest(p)['dirty'])
        out.append(
            {
                'key': p['person_key'],
                'name': p['full_name'],
                'party': party_letter(p),
                'seat': seat_label(p),
                'dirty': dirty,
                'rounded': round_money(dirty),
                'flagged': is_flagged(p),
            }
        )
    return out


def stacked_sources(people):
    """One chamber's total accepted, split by source (latest term).

    Total accepted is individual + corporate PAC + AIPAC direct.
    UDP benefit is excluded: it was never given to the campaign.
    """
    record = latest
    aipac = sum(dollars(record(p)['aipac_direct']) for p in people)
    corp = sum(dollars(record(p)['corp']) for p in people)
    individual = sum(dollars(record(p)['individual']) for p in people)
    total = aipac + corp + individual
    return {
        'aipac': aipac,
        'corp': corp,
        'individual': individual,
        'total': total,
        'shares': {
            key: (value / total if total > 0 else None)
            for key, value in (
                ('aipac', aipac),
                ('corp', corp),
                ('individual', individual),
            )
        },
    }


def race_chamber(person):
    """The chamber of the candidacy that carried the most individual money.

    In the person's verdict cycle, the candidate ID with the largest
    individual total names the race: H for House, S for Senate.
    """
    verdict = person['verdict_cycle']
    entries = [e for e in person.get('per_cycle') or [] if e['cycle'] == verdict]
    if not entries:
        return person['chamber_120'] or person['chamber_119'] or ''
    biggest = max(entries, key=lambda e: dollars(e.get('individual')))
    candidate_id = biggest.get('candidate_id') or ''
    return {'H': 'House', 'S': 'Senate'}.get(
        candidate_id[:1], person['chamber_120'] or person['chamber_119'] or ''
    )


def member_story(dataset):
    """Beat 4: the top latest-term dirty-money member in the dataset.

    Over all rows, not incoming members only — the biggest dirty-money
    story may belong to someone not returning. Their trend covers the
    cycles they were up for election; the zoom-out is incoming members
    of their race chamber only.
    """
    member = max(dataset, key=lambda p: dollars(latest(p)['dirty']))
    record = latest(member)
    chamber = race_chamber(member)
    incoming = [p for p in incoming_members(dataset) if p['chamber_120'] == chamber]
    zoom_top = ranked_list(incoming, 10)
    dirties = sorted((dollars(latest(p)['dirty']) for p in incoming), reverse=True)
    median = dirties[len(dirties) // 2] if dirties else 0
    split = {
        key: dollars(record[key])
        for key in ('corp', 'aipac_direct', 'individual', 'udp_benefit', 'dirty')
    }
    return {
        'key': member['person_key'],
        'name': member['full_name'],
        'party': party_letter(member),
        'seat': seat_label(member),
        'race_chamber': chamber,
        'returning': member['in_120th'] == 'yes',
        'split': {**split, 'rounded': {k: round_money(v) for k, v in split.items()}},
        'trend': [
            {
                'cycle': c['cycle'],
                'dirty': dollars(c['dirty']),
                'rounded': round_money(dollars(c['dirty'])),
            }
            for c in sorted(member.get('cycles') or [], key=lambda c: c['cycle'])
            if c.get('up_for_election')
        ],
        'zoom': {
            'chamber': chamber,
            'top': zoom_top,
            'median': median,
            'median_rounded': round_money(median),
            'member_dirty': split['dirty'],
            'member_rounded': round_money(split['dirty']),
        },
    }


def district_map(dataset):
    """Every incoming House seat for the district map, by verdict.

    Coloured by verdict (the Balanced tier on the headline term),
    never by raw dollars. Delegates have no district geometry and
    are not on the map.
    """
    districts = []
    for p in incoming_members(dataset):
        if p['chamber_120'] != 'House' or p['state'] in TERRITORIES:
            continue
        record = latest(p)
        districts.append(
            {
                'key': district_key(p),
                'member_key': p['person_key'],
                'name': p['full_name'],
                'party': party_letter(p),
                'tier': record['tier_balanced'],
                'flagged': is_flagged(p),
            }
        )
    return sorted(districts, key=lambda d: d['key'])


def headline_counts(dataset):
    """The headline counts, all over incoming members on the term."""
    incoming = incoming_members(dataset)
    return {
        'flag_120': sum(1 for p in incoming if is_flagged(p)),
        'strict_clean': sum(1 for p in incoming if latest(p)['clean'] is True),
        'balanced_not_dirty': sum(
            1 for p in incoming if latest(p)['tier_balanced'] in ('clean', 'below_threshold')
        ),
        'lenient_not_dirty': sum(
            1 for p in incoming if latest(p)['tier_lenient'] in ('clean', 'below_threshold')
        ),
        'balanced_dirty': sum(1 for p in incoming if latest(p)['tier_balanced'] == 'dirty'),
        'dirty_positive': sum(1 for p in incoming if dollars(latest(p)['dirty']) > 0),
        'aipac_direct_career': sum(dollars(p['aipac_pac_direct_career']) for p in dataset),
        'pro_israel_career': sum(dollars(p['pro_israel_pac_career']) for p in dataset),
    }


def build_story_data(dataset, current_cycle, next_cycle, balanced_short=None):
    """Every aggregate the Story front door needs, from the dataset."""
    incoming = incoming_members(dataset)
    house = [p for p in incoming if p['chamber_120'] == 'House']
    senate = [p for p in incoming if p['chamber_120'] == 'Senate']
    counts = headline_counts(dataset)
    dirty_total = sum(dollars(latest(p)['dirty']) for p in incoming)
    all_targets = primary_targets(incoming, 'balanced', next_cycle)
    targets = all_targets[:8]
    return {
        'meta': {
            'current_cycle': current_cycle,
            'next_cycle': next_cycle,
            'incoming_total': len(incoming),
        },
        'preset': {'balanced_short': balanced_short},
        'hero': {
            'dirty_total': dirty_total,
            'dirty_total_rounded': round_money(dirty_total),
            'flagged': counts['flag_120'],
            'members': len(incoming),
        },
        'counts': counts,
        'waffle': {
            'house': waffle_panel(dataset, 'House', HOUSE_SEATS),
            'senate': waffle_panel(dataset, 'Senate', SENATE_SEATS),
        },
        'ranked': {
            'house': ranked_list(house, 10),
            'senate': ranked_list(senate, 10),
        },
        'stacked': {
            'house': stacked_sources(house),
            'senate': stacked_sources(senate),
        },
        'member': member_story(dataset),
        'map': {'districts': district_map(dataset)},
        'targets_total': len(all_targets),
        'targets': [
            {
                'key': p['person_key'],
                'name': p['full_name'],
                'party': party_letter(p),
                'chamber': p['chamber_120'],
                'seat': seat_label(p),
                'dirty': dollars(latest(p)['dirty']),
                'rounded': round_money(dollars(latest(p)['dirty'])),
            }
            for p in targets
        ],
    }

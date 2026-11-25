"""Seat, delegate and outcome counts recomputed from the embedded data, pinned to the baseline."""

from collections import Counter

HOUSE_SEATS, SENATE_SEATS, STATES = 435, 100, 50
TERRITORIES = {'AS', 'GU', 'MP', 'PR', 'VI', 'DC'}


def composition(audit, page):
    house = [r for r in page.incoming if r['chamber_120'] == 'House']
    voting = [r for r in house if r['state'] not in TERRITORIES]
    senate = [r for r in page.incoming if r['chamber_120'] == 'Senate']
    per_state = Counter(r['state'] for r in senate)
    audit.check('named voting House members fit the chamber', len(voting) <= HOUSE_SEATS)
    audit.check(
        'two Senate seats per state at most',
        len(senate) <= SENATE_SEATS and all(n <= 2 for n in per_state.values()),
    )
    audit.check('every state has a senator', len(per_state) == STATES)
    audit.pin('House named voting members', 'site.composition.house_named', len(voting))
    audit.pin('Senate named members', 'site.composition.senate_named', len(senate))
    audit.pin(
        'Senate states with an uncalled seat',
        'site.composition.senate_states_with_uncalled_seat',
        sorted(state for state, n in per_state.items() if n < 2),
    )
    audit.pin('non-voting delegates', 'site.composition.delegates', len(house) - len(voting))


def outcomes(audit, page):
    audit.check(
        'every row has a party (party_120 else party_119)',
        all(r['party_120'] or r['party_119'] for r in page.rows),
    )
    counts = {v: sum(r['in_120th'] == v for r in page.rows) for v in ('yes', 'no', 'unknown')}
    audit.check('outcome mapping covers every row', sum(counts.values()) == len(page.rows))
    audit.pin('outcomes (Won / Not returning / Uncalled)', 'site.outcomes', counts)

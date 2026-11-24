from receipts.domain.names import norm, slug
from receipts.transform.build_roster import build

FACTS = {
    'added_members': [],
    'notes': [],
    'unknown_in_120th': [],
    'late_notes': [],
    'leadership_119': {},
    'unverified_leadership_120': {},
}


def legislator(bioguide, first, last, *terms, fec=()):
    return {
        'id': {'bioguide': bioguide, 'fec': list(fec)},
        'name': {'first': first, 'last': last, 'official_full': f'{first} {last}'},
        'terms': list(terms),
    }


def rep(state, district, party='Democrat', start='2025-01-03', end='2027-01-03'):
    return {'type': 'rep', 'state': state, 'district': district, 'party': party,
            'start': start, 'end': end}  # fmt: skip


def sen(state, senate_class, party='Democrat', start='2021-01-03', end='2027-01-03'):
    return {'type': 'sen', 'state': state, 'class': senate_class, 'party': party,
            'start': start, 'end': end}  # fmt: skip


def seats(house=(), senate=()):
    return {
        'house': [{'name': n, 'state': s, 'district': d, 'party': p} for n, s, d, p in house],
        'senate': [{'name': n, 'state': s, 'party': p} for n, s, p in senate],
        'delegates': [],
    }


def rows(legislators, r120, historical=None, facts=FACTS):
    roster, seated, newcomers = build(legislators, historical or {}, r120, facts)
    return roster.rows, roster.unmatched(seated), newcomers


def test_a_reelected_member_is_matched_to_their_120th_seat():
    found, unmatched, newcomers = rows(
        [legislator('A1', 'Ann', 'Able', rep('NY', 3), fec=['H1'])],
        seats(house=[('Ann Able', 'NY', 3, 'DFL')]),
    )
    row = found['A1']
    assert (row['in_119th'], row['in_120th']) == ('yes', 'yes')
    assert (row['chamber_120'], row['district_120'], row['party_120']) == ('House', '3', 'Democrat')
    assert 'DFL' in row['notes']
    assert unmatched == ([], []) and newcomers == []


def test_a_same_state_namesake_is_a_different_person():
    found, _, newcomers = rows(
        [legislator('A1', 'Ann', 'Able', rep('NY', 3))],
        seats(house=[('Bea Able', 'NY', 4, 'Democrat')]),
    )
    assert found['A1']['in_120th'] == 'no'
    assert newcomers == [('brand-new', 'Bea Able', 'NY')]
    assert found[slug('Bea', 'Able', 'NY', 'House')]['notes'].startswith('New member of the 120th')


def test_a_returning_former_member_keeps_their_old_fec_ids_only_after_recent_service():
    historical = {
        norm('Cal Cole'): {'bioguide': 'C9', 'fec': ['H8OLD'],
                           'last_term': {'type': 'rep', 'state': 'IL', 'end': '2011-01-03'}},
        norm('Dee Dunn'): {'bioguide': 'D9', 'fec': ['H0ANCIENT'],
                           'last_term': {'type': 'rep', 'state': 'IL', 'end': '1899-03-03'}},
    }  # fmt: skip
    found, _, newcomers = rows(
        [],
        seats(house=[('Cal Cole', 'IL', 8, 'Democrat'), ('Dee Dunn', 'IL', 9, 'Democrat')]),
        historical,
    )
    assert found['C9']['fec_candidate_ids'] == ['H8OLD']
    assert found['C9']['notes'].startswith('Returning former member')
    assert ('brand-new', 'Dee Dunn', 'IL') in newcomers
    assert found[slug('Dee', 'Dunn', 'IL', 'House')]['fec_candidate_ids'] == []


def test_an_outgoing_house_member_names_their_successor():
    found, *_ = rows(
        [legislator('A1', 'Ann', 'Able', rep('NY', 3))],
        seats(house=[('Eve Eng', 'NY', 3, 'Republican')]),
    )
    assert 'NY-3 in the 120th is held by Eve Eng (Republican)' in found['A1']['notes']


def test_senate_class_comes_from_the_own_term_or_the_seats_outgoing_holder():
    legislators = [
        legislator('S1', 'Sam', 'Stay', sen('OH', 3)),
        legislator('S2', 'Sue', 'Gone', sen('OH', 1, end='2025-01-03'), sen('OH', 1)),
    ]
    found, *_ = rows(
        legislators, seats(senate=[('Sam Stay', 'OH', 'Democrat'), ('Neo New', 'OH', 'Republican')])
    )
    assert found['S1']['senate_class'] == 3
    assert found[slug('Neo', 'New', 'OH', 'Senate')]['senate_class'] == 1
    assert found['S2']['in_120th'] == 'no'


def test_a_curated_fact_can_mark_120th_membership_unknown():
    facts = {
        **FACTS,
        'unknown_in_120th': [{'match': {'state': 'AK'}, 'note': 'race uncalled'}],
    }
    found, *_ = rows([legislator('K1', 'Kay', 'Kim', rep('AK', 0))], seats(), facts=facts)
    assert found['K1']['in_120th'] == 'unknown'
    assert found['K1']['notes'].endswith('120th membership UNKNOWN: race uncalled')

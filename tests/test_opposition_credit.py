from receipts.store.opposition import credit_rows, credits, races_of, support_mismatches
from receipts.store.udp_rows import UdpRow

PERSON_KEYS = {'H_BACKED': 'P1', 'H_OTHER': 'P2'}


def row(candidate_id, name, direction, cents, phase='P', district='16', cycle=2024):
    return UdpRow(candidate_id, name, cycle, direction, cents, 'H', 'NY', district, phase, 't')


def credit(rows):
    by_person, nonroster, credited, uncredited = credits(races_of(rows), PERSON_KEYS)
    return dict(by_person), dict(nonroster), credited, uncredited


def test_opposition_credits_to_the_one_backed_candidate():
    by_person, _, credited, _ = credit(
        [row('H_BACKED', 'BACKED, B', 'S', 100), row('H_RIVAL', 'RIVAL, R', 'O', 900)]
    )
    assert by_person == {'P1': 900}
    assert credit_rows(credited) == [
        {
            'cycle': 2024,
            'office': 'H',
            'state': 'NY',
            'district': '16',
            'election_type': 'P',
            'credited_to': 'P1',
            'backed_name': 'BACKED, B',
            'credit': 9.0,
        }
    ]


def test_two_backed_candidates_credit_no_one():
    by_person, nonroster, _, uncredited = credit(
        [
            row('H_BACKED', 'BACKED, B', 'S', 100),
            row('H_OTHER', 'OTHER, O', 'S', 100),
            row('H_RIVAL', 'RIVAL, R', 'O', 900),
        ]
    )
    assert by_person == {} and nonroster == {}
    assert uncredited[0][1] == 2


def test_spending_against_the_backed_candidate_is_never_credited():
    by_person, *_ = credit(
        [
            row('H_BACKED', 'BACKED, B', 'S', 100),
            row('H_BACKED', 'BACKED, B', 'O', 50),
            row('', 'Backed, B', 'O', 25),
            row('H_RIVAL', 'RIVAL, R', 'O', 900),
        ]
    )
    assert by_person == {'P1': 900}


def test_each_phase_is_judged_on_its_own():
    by_person, nonroster, *_ = credit(
        [
            row('H_BACKED', 'BACKED, B', 'S', 100, phase='P'),
            row('H_RIVAL', 'RIVAL, R', 'O', 900, phase='P'),
            row('H_NONROSTER', 'OUTSIDER, O', 'S', 100, phase='G'),
            row('H_RIVAL', 'RIVAL, R', 'O', 400, phase='G'),
        ]
    )
    assert by_person == {'P1': 900}
    assert nonroster == {'H_NONROSTER': 400}


def test_support_mismatches_compare_recomputed_support_to_the_published_figure():
    rows = [row('H_BACKED', 'BACKED, B', 'S', 12_345)]
    published = {'P1': '123.45', 'P2': '0.00', 'P3': 'unknown'}
    assert support_mismatches(rows, PERSON_KEYS, published) == []
    assert support_mismatches(rows, PERSON_KEYS, {'P1': '100.00'}) == [('P1', 100.0, 123.45)]

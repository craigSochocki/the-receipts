from receipts.domain.seats import (
    congress_elected_in,
    congress_start,
    house_seat_id,
    regular_senate_class,
    senate_seat_id,
    senate_term_end,
)

NEW_MAPS = {2026: {'TX'}}


def test_a_redrawn_state_gets_new_seats_from_2026():
    assert house_seat_id('TX', '9', 2024, NEW_MAPS, 2024) == 'H-TX-09/2024'
    assert house_seat_id('TX', '09', 2026, NEW_MAPS, 2024) == 'H-TX-09/2026'


def test_an_unchanged_state_keeps_its_seats():
    assert house_seat_id('MI', 11, 2024, NEW_MAPS, 2024) == house_seat_id(
        'MI', '11', 2026, NEW_MAPS, 2024
    )


def test_at_large_and_delegate_seats_are_district_zero():
    assert house_seat_id('AK', '00', 2026, NEW_MAPS, 2024) == 'H-AK-00/2024'
    assert house_seat_id('DC', 0, 2024, NEW_MAPS, 2024) == 'H-DC-00/2024'


def test_congresses_and_senate_terms_follow_the_calendar():
    assert [congress_elected_in(y) for y in (2024, 2026, 2028)] == [119, 120, 121]
    assert congress_start(120) == '2027-01-03'
    assert [senate_term_end(c, 2026) for c in (1, 2, 3)] == [
        '2031-01-03',
        '2033-01-03',
        '2029-01-03',
    ]


def test_senate_classes_rotate_every_two_years():
    assert [regular_senate_class(y) for y in (2018, 2020, 2022, 2024, 2026, 2028, 2030)] == [
        1,
        2,
        3,
        1,
        2,
        3,
        1,
    ]
    assert senate_seat_id('GA', 2) == 'S-GA-2'


def test_a_delegate_filed_as_district_01_maps_to_the_delegate_seat():
    from receipts.fec.candidates import Candidate
    from receipts.store.congress import seat_for

    blank = dict.fromkeys(Candidate._fields, '')
    king_hinds = Candidate(
        **{
            **blank,
            'office': 'H',
            'office_state': 'MP',
            'office_district': '01',
            'election_year': '2026',
        }
    )
    assert seat_for(king_hinds, {}, (2024, 2026), {}) == 'H-MP-00/2024'


def test_a_senate_special_in_a_state_without_the_regular_class_is_left_unlinked():
    from receipts.fec.candidates import Candidate
    from receipts.store.congress import seat_for

    blank = dict.fromkeys(Candidate._fields, '')
    ohio = Candidate(**{**blank, 'office': 'S', 'office_state': 'OH', 'election_year': '2026'})
    assert seat_for(ohio, {}, (2024, 2026), {'OH': [1, 3]}) is None
    assert seat_for(ohio._replace(office_state='GA'), {}, (2024, 2026), {'GA': [2, 3]}) == 'S-GA-2'

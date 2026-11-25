from receipts.domain.clean_2026 import (
    CAREER_DIRTY_COLUMNS,
    UNLINKED,
    UNOPPOSED,
    TolerancePreset,
    aipac_udp_flagged,
    is_career_clean,
    is_not_dirty,
    race_label,
    races_and_unopposed,
    tier,
    verdict,
)

PRESET = TolerancePreset(corp_amount=5000, corp_share=0.05)


def test_a_race_whose_only_rivals_raised_nothing_is_unopposed():
    race_map = {
        ('H', 'MA', '07'): [('H1', 500), ('H2', 0)],
        ('H', 'NY', '16'): [('H3', 9), ('H4', 1)],
    }
    race_of = {'H1': ('H', 'MA', '07'), 'H3': ('H', 'NY', '16')}
    assert races_and_unopposed(['H1'], race_map, race_of) == (
        [('H', 'MA', '07')],
        [('H', 'MA', '07')],
    )
    assert races_and_unopposed(['H3'], race_map, race_of) == ([('H', 'NY', '16')], [])
    assert races_and_unopposed(['H9'], race_map, race_of) == ([], [])


def test_race_labels():
    assert race_label(('H', 'CA', '51')) == 'CA-51'
    assert race_label(('S', 'MI', '00')) == 'MI Senate'


def test_clean_is_no_net_dirty_money_and_unknown_without_data_or_a_contest():
    assert verdict(True, True, False, 0) == (True, None)
    assert verdict(True, True, False, -50) == (True, None)
    assert verdict(True, True, False, 10) == (False, None)
    assert verdict(True, False, False, 0) == (None, UNLINKED)
    assert verdict(True, True, True, 0) == (None, UNOPPOSED)
    assert verdict(True, True, True, 10) == (False, None)


def test_tiers_under_a_preset():
    assert tier(None, False, 0, 100, PRESET) is None
    assert tier(False, True, 0, 100, PRESET) == 'dirty'
    assert tier(False, False, 6000, 100000, PRESET) == 'dirty'
    assert tier(False, False, 6000, 1000000, PRESET) == 'below_threshold'
    assert tier(False, False, 4000, 10000, PRESET) == 'below_threshold'
    assert tier(True, False, 0, 0, PRESET) == 'clean'
    assert tier(False, False, 6000, 0, PRESET) == 'below_threshold'


def test_any_aipac_or_udp_dollar_flags_a_member():
    assert aipac_udp_flagged(0.01, 0) is True
    assert aipac_udp_flagged(0, 2500.0) is True
    assert aipac_udp_flagged(0, 0) is False
    assert aipac_udp_flagged(-15000.0, 0) is False  # a refund flags no one


def test_not_dirty_means_clean_or_below_threshold():
    assert [is_not_dirty(t) for t in ('clean', 'below_threshold', 'dirty', None)] == [
        True,
        True,
        False,
        False,
    ]


def test_career_clean_needs_every_dirty_source_at_zero():
    clean = dict.fromkeys(CAREER_DIRTY_COLUMNS, 0)
    assert is_career_clean(clean)
    for column in CAREER_DIRTY_COLUMNS:
        assert not is_career_clean({**clean, column: 1})
    assert not is_career_clean({**clean, 'corporate_pac_career': 'unknown'})

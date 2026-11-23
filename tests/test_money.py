from receipts.domain.money import Money, ZERO


def test_parses_fec_amounts_exactly():
    assert Money.parse('2500') == Money(250000)
    assert Money.parse('1234.56') == Money(123456)
    assert Money.parse('-15000') == Money(-1500000)
    assert Money.parse('.5') == Money(50)


def test_blank_amount_is_zero():
    assert Money.parse('') == ZERO
    assert Money.parse(None) == ZERO
    assert Money.parse('  ') == ZERO


def test_addition_is_exact_where_floats_drift():
    assert Money.parse('0.10') + Money.parse('0.20') == Money.parse('0.30')
    assert Money.total(Money.parse('0.10') for _ in range(10)) == Money.parse('1.00')


def test_prints_dollars_with_two_decimals():
    assert str(Money(123456)) == '1234.56'
    assert str(Money(-5)) == '-0.05'
    assert str(ZERO) == '0.00'
    assert str(Money(876384203425)) == '8763842034.25'


def test_truthiness_and_sign():
    assert not ZERO
    assert Money(1)
    assert Money(-1).is_negative
    assert not Money(1).is_negative


def test_money_formats_with_or_without_thousands_separators():
    assert (str(Money(-123456789)), f'{Money(10720783):,}') == ('-1234567.89', '107,207.83')

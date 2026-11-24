"""Money as an exact number of cents."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True, order=True)
class Money:
    cents: int = 0

    @classmethod
    def parse(cls, text):
        """Dollars as the FEC files write them: '2500', '1234.56', '$1,000'."""
        cleaned = (text or '').replace('$', '').replace(',', '').strip()
        if not cleaned:
            return ZERO
        try:
            return cls(int((Decimal(cleaned) * 100).to_integral_value()))
        except InvalidOperation:
            raise ValueError(f'not an amount: {text!r}') from None

    @classmethod
    def total(cls, amounts):
        return cls(sum(amount.cents for amount in amounts))

    def __add__(self, other):
        return Money(self.cents + other.cents)

    def __bool__(self):
        return self.cents != 0

    @property
    def is_negative(self):
        return self.cents < 0

    def __str__(self):
        return format(self, '')

    def __format__(self, spec):
        """'' gives 1234.50; ',' gives 1,234.50."""
        sign = '-' if self.cents < 0 else ''
        dollars, cents = divmod(abs(self.cents), 100)
        return f'{sign}{dollars:{spec}}.{cents:02d}'


ZERO = Money(0)


def exact_sum(amounts, start=0):
    """Sum JSON dollar amounts in exact cents; the result's type follows sum(amounts, start)."""
    amounts = list(amounts)
    cents = Money.total(Money.parse(repr(a)) for a in amounts).cents
    exact_ints = isinstance(start, int) and all(isinstance(a, int) for a in amounts)
    return cents // 100 if exact_ints and cents % 100 == 0 else cents / 100

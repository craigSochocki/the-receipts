"""Money as an exact number of cents."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, order=True)
class Money:
    cents: int = 0

    @classmethod
    def parse(cls, text):
        text = (text or '').strip()
        if not text:
            return ZERO
        return cls(int((Decimal(text) * 100).to_integral_value()))

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
        sign = '-' if self.cents < 0 else ''
        dollars, cents = divmod(abs(self.cents), 100)
        return f'{sign}{dollars}.{cents:02d}'


ZERO = Money(0)

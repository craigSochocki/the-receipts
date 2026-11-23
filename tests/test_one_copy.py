from collections import namedtuple

from src.domain.one_copy import OneCopyEach

Item = namedtuple('Item', 'identity rank')


def test_the_preferred_copy_is_kept_and_the_rest_are_dropped():
    kept = OneCopyEach(preferred=lambda new, old: new.rank > old.rank)
    for item in [Item('a', 1), Item('a', 3), Item('a', 2), Item('b', 1)]:
        kept.add(item)

    assert list(kept) == [Item('a', 3), Item('b', 1)]
    assert kept.dropped == [Item('a', 1), Item('a', 2)]

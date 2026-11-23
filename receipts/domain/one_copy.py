"""Keeping one copy of something that was reported more than once."""


class OneCopyEach:
    """One item per identity; a later copy replaces the kept one only if preferred."""

    def __init__(self, preferred):
        self._preferred = preferred
        self._kept = {}
        self.dropped = []

    def add(self, item):
        kept = self._kept.get(item.identity)
        if kept is None:
            self._kept[item.identity] = item
        elif self._preferred(item, kept):
            self._kept[item.identity] = item
            self.dropped.append(kept)
        else:
            self.dropped.append(item)

    def __iter__(self):
        return iter(self._kept.values())

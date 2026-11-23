"""Rows of a pipe-delimited FEC bulk file, as named records."""


class LayoutChanged(Exception):
    """An FEC file no longer has the columns its reader expects."""


class BulkFile:
    def __init__(self, path, record):
        self.path = path
        self.record = record
        self.rows_read = 0

    def __iter__(self):
        width = len(self.record._fields)
        with open(self.path) as lines:
            for self.rows_read, line in enumerate(lines, start=1):
                fields = line.rstrip('\n').split('|')
                if len(fields) != width:
                    raise LayoutChanged(
                        f'{self.path} line {self.rows_read} has {len(fields)} fields where '
                        f'{self.record.__name__} expects {width}: the FEC file layout changed'
                    )
                yield self.record._make(fields)

"""Rows of a pipe-delimited FEC bulk file, as named records."""


class BulkFile:
    def __init__(self, path, record):
        self.path = path
        self.record = record
        self.rows_read = 0
        self.malformed_rows = 0

    def __iter__(self):
        width = len(self.record._fields)
        with open(self.path) as lines:
            for line in lines:
                self.rows_read += 1
                fields = line.rstrip('\n').split('|')
                if len(fields) != width:
                    self.malformed_rows += 1
                    continue
                yield self.record._make(fields)

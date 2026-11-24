"""Bookkeeping shared by the standing checks: named checks, baseline pins, one verdict."""

import sys

from receipts.common.baseline import expected as baseline_figure
from receipts.common.log import log


class Audit:
    def __init__(self):
        self.failures = []

    def check(self, label, condition, detail=''):
        log.info(
            f'[{"ok " if condition else "FAIL"}] {label}'
            + (f' — {detail}' if detail and not condition else '')
        )
        if not condition:
            self.failures.append(f'{label}: {detail}' if detail else label)

    def pin(self, label, key, observed):
        """Check a figure that new FEC data can move against the baseline."""
        want = baseline_figure(key, observed)
        self.check(f'{label} [{key}]', observed == want, f'got {observed!r}, baseline {want!r}')

    def finish(self, passed):
        """Exit non-zero listing every failure, or print `passed`."""
        log.info('')
        if self.failures:
            log.info(f'FAILED: {len(self.failures)} check(s)')
            for failure in self.failures:
                log.info(f'  - {failure}')
            sys.exit(1)
        log.info(passed)

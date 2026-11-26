#!/usr/bin/env python3
"""Verify docs/index.html against the dataset and the baseline."""

import hashlib
import sys

from receipts.common.log import run
from receipts.common.settings import settings
from receipts.site.checks.counts import composition, outcomes
from receipts.site.checks.data import coverage_stamp, data_round_trip, opposition_detail
from receipts.site.checks.figures import no_typed_figures
from receipts.site.checks.page import BuiltPage
from receipts.site.checks.runtime import (
    deterministic,
    javascript_parses,
    runtime_smoke_test,
    served_page,
)
from receipts.site.checks.static import static_story_and_table
from receipts.validate.audit import Audit

SECTIONS = [
    coverage_stamp,
    data_round_trip,
    opposition_detail,
    composition,
    outcomes,
    no_typed_figures,
    static_story_and_table,
    javascript_parses,
    served_page,
    runtime_smoke_test,
    deterministic,
]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = settings().paths.site / 'index.html'
    if not path.exists():
        raise SystemExit('FAIL docs/index.html does not exist: run build_site.py')
    audit = Audit()
    page = BuiltPage(path)
    audit.check('no unreplaced placeholders', '%%' not in page.html)
    skipped = {served_page} if '--skip-serve' in argv else set()
    for section in SECTIONS:
        if section not in skipped:
            section(audit, page)
    audit.finish(
        'All site checks passed.\n'
        f'dataset md5: {hashlib.md5(settings().paths.dataset_json.read_bytes()).hexdigest()}'
    )


if __name__ == '__main__':
    run(main)

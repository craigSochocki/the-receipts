#!/usr/bin/env python3
"""Standing audits of the dataset; every expected figure comes from baseline.json."""

import argparse

from receipts.common.log import run
from receipts.common.settings import settings
from receipts.validate.audit import Audit
from receipts.validate.audits.clean import clean_counts, clean_spot_cases, unopposed
from receipts.validate.audits.columns_2026 import columns_2026, cycle_records, headline_verdicts
from receipts.validate.audits.money import (
    all_ie,
    double_counts,
    opposition,
    other_committees,
    pro_israel,
    roster_totals,
    self_funding,
)
from receipts.validate.audits.published import Published
from receipts.validate.audits.ranks import ranks_and_dirty
from receipts.validate.audits.rows import csv_matches_json, rows_and_order
from receipts.validate.audits.senate import senate_class
from receipts.validate.audits.tiers import tiered_rule

SECTIONS = [
    rows_and_order,
    self_funding,
    other_committees,
    all_ie,
    pro_israel,
    roster_totals,
    double_counts,
    ranks_and_dirty,
    clean_counts,
    tiered_rule,
    columns_2026,
    cycle_records,
    headline_verdicts,
    clean_spot_cases,
    unopposed,
    senate_class,
    opposition,
    csv_matches_json,
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dataset-csv', default=settings().paths.dataset_csv)
    ap.add_argument('--dataset-json', default=settings().paths.dataset_json)
    args = ap.parse_args(argv)

    audit = Audit()
    dataset = Published(settings().root / args.dataset_json, settings().root / args.dataset_csv)
    for section in SECTIONS:
        section(audit, dataset)
    audit.finish(
        'VERIFY PASSED: all standing audits clean.\n'
        'Note: these audits check the dataset against its own definitions; '
        'they cannot catch a missing money dimension (see module docstring).'
    )


if __name__ == '__main__':
    run(main)

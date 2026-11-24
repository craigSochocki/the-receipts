#!/usr/bin/env python3
"""Standing audits for the Congress money tracker dataset.

Usage:
    python3 receipts/validate/verify_dataset.py [--dataset-csv PATH] [--dataset-json PATH]

Exits non-zero on any mismatch, printing every failure. Every expected
figure comes from data/source/baseline.json; none is written here.

  (a) per-cycle sums reproduce every career column: dbt tests on the gold
      tables (dbt/tests/*_career_is_its_cycles.sql), run by the marts pass.
  (b) roster totals match the baseline to the cent; a person with no FEC
      candidate ID ("unknown" money) is left out of every sum.
  (c) every rank column recomputes exactly (competition ranking:
      rank = 1 + count of strictly greater values).
  (d) the clean counts match the baseline, including career-clean and the
      clean-in-2026-but-not-career-clean split.
  (e) every 2026 column, the clean rule and dep_share recompute exactly:
      the linkage rule, the unopposed flag recomputed from weball26, the
      unopposed nulling of would-be-clean verdicts, the net-negative rule,
      the AIPAC/UDP flag, both tolerance tiers, and the int/float split on
      empty 2026 sums.
  (f) the opposition career columns recompute from gold.opposition_credits.
  (g) dedup: dbt tests (double_counts_*.sql) on the store's double_counts
      table and gold.accepted_money_per_cycle.
  (h) CSV and JSON agree field by field (CSV floats by float value,
      clean_2026 by True/False/empty, dep_share by float value, the
      per-cycle lists by repr; all_ie_top_committees is JSON-only and
      skipped).
  (i) one row per person, unique person_keys, row order matches roster.json.
  (j) self-funding and topline: named spot cases match the baseline; debts
      owed to is null everywhere; a person with no FEC ID reads unknown,
      not zero.
  (k) other committees: a named case's current-cycle pas2 total, its
      residual against weball, and the note that states them. The
      corporate/AIPAC re-derivation is enforced by the other-committees step.
  (l) all-IE: roster cycle totals (from gold) match the baseline; the
      row-sum gap is exactly the blank-direction rows; top-committee lists
      are sorted, split correctly, and null for a person with no FEC ID.
      The UDP reconciliation is enforced by the all-IE step.
  (m) clean-rule spot cases from the baseline: a member verified clean
      with linkage evidence, a member left null because their real
      campaign is unlinked, and the unopposed members, who are null, not
      clean, while a member with a funded opponent stays verified-clean.
  (n) senate_class: re-derived from the legislators yaml (the Senate-term
      class field) for every row, and the class counts match the baseline.
  (o) tiered dirty rule (methodology §14): the AIPAC/UDP flag and both
      tolerance tiers recompute; the tier counts, corp-only splits and
      2028-target counts under each preset match the baseline.

Caveat (AGENTS.md §5): this verifies the dataset against its own
definitions. It cannot catch a missing dimension — e.g. the
self-funding blind spot (candidate loans and contributions were never
pulled, so no audit here would have flagged their absence). A new money
dimension needs a new audit, not just a re-run of this one.
"""

import argparse

from receipts.common.settings import settings
from receipts.validate.audit import Audit
from receipts.validate.audits.clean import clean_counts, clean_spot_cases, unopposed
from receipts.validate.audits.columns_2026 import columns_2026
from receipts.validate.audits.money import (
    all_ie,
    opposition,
    other_committees,
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
    roster_totals,
    ranks_and_dirty,
    clean_counts,
    tiered_rule,
    columns_2026,
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
    main()

#!/usr/bin/env python3
"""Assemble the dataset from the store and write it once: base rows, then the cycle columns."""

import json

import pandas as pd

from receipts.common.log import log, run
from receipts.common.settings import settings
from receipts.transform.assemble import base_records
from receipts.transform.compute_2026 import cycle_fields, with_cycles


def base_keys():
    cycle_keys = {f'{k}_{settings().cycles.current}' for k in cycle_fields()} | {'cycles'}
    return [k for k in settings().dataset.json_keys if k not in cycle_keys]


def write_dataset(records):
    paths = settings().paths
    with open(paths.dataset_json, 'w') as f:
        json.dump(records, f, indent=1)
    pd.DataFrame(records, columns=list(settings().dataset.csv_columns)).to_csv(
        paths.dataset_csv, index=False
    )
    cycles = [{'person_key': r['person_key'], **c} for r in records for c in r['cycles']]
    pd.DataFrame(cycles).to_csv(paths.dataset_cycles_csv, index=False)
    log.info(
        f'wrote {settings().relative(paths.dataset_json)}, .csv ({len(records)} rows) '
        f'and {settings().relative(paths.dataset_cycles_csv)} ({len(cycles)} rows)'
    )


def main():
    write_dataset(with_cycles(base_records(base_keys())))


if __name__ == '__main__':
    run(main)

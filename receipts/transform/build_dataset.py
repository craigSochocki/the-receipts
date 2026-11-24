#!/usr/bin/env python3
"""Assemble the dataset from the store and write it once: base rows, then the cycle columns."""

import json

import pandas as pd

from receipts.common.log import log, run
from receipts.common.settings import settings
from receipts.transform.assemble import base_records
from receipts.transform.compute_2026 import with_2026


def base_keys():
    return [k for k in settings().dataset.json_keys if str(settings().cycles.current) not in k]


def write_dataset(records):
    paths = settings().paths
    with open(paths.dataset_json, 'w') as f:
        json.dump(records, f, indent=1)
    pd.DataFrame(records, columns=list(settings().dataset.csv_columns)).to_csv(
        paths.dataset_csv, index=False
    )
    log.info(f'wrote {settings().relative(paths.dataset_json)} and .csv ({len(records)} rows)')


def main():
    write_dataset(with_2026(base_records(base_keys())))


if __name__ == '__main__':
    run(main)

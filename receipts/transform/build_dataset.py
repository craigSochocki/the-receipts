#!/usr/bin/env python3
"""Assemble the dataset from the store and write it once: base rows, then the 2026 columns."""

import json

import pandas as pd

from receipts.common.config import load_config
from receipts.transform.assemble import base_records
from receipts.transform.compute_2026 import with_2026

CFG = load_config()
ROOT = CFG['_root']
BASE_KEYS = [k for k in CFG['dataset']['json_keys'] if '2026' not in k]


def write_dataset(records):
    with open(ROOT / CFG['paths']['dataset_json'], 'w') as f:
        json.dump(records, f, indent=1)
    pd.DataFrame(records, columns=CFG['dataset']['csv_columns']).to_csv(
        ROOT / CFG['paths']['dataset_csv'], index=False
    )
    print(f'wrote {CFG["paths"]["dataset_json"]} and .csv ({len(records)} rows)')


def main():
    write_dataset(with_2026(base_records(BASE_KEYS)))


if __name__ == '__main__':
    main()

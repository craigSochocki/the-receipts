#!/usr/bin/env python3
"""Assemble the dataset in one pass and write it once: merge, rank, then 2026."""
import json

import pandas as pd

from src.common.config import load_config
from src.transform.compute_2026 import with_2026
from src.transform.compute_ranking import ranked
from src.transform.merge_dataset import merged_records

CFG = load_config()
ROOT = CFG['_root']


def write_dataset(records):
    with open(ROOT / CFG['paths']['dataset_json'], 'w') as f:
        json.dump(records, f, indent=1)
    pd.DataFrame(records, columns=CFG['dataset']['csv_columns']).to_csv(
        ROOT / CFG['paths']['dataset_csv'], index=False)
    print(f"wrote {CFG['paths']['dataset_json']} and .csv ({len(records)} rows)")


def main():
    write_dataset(with_2026(ranked(merged_records())))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Fail unless every gold view reproduces the old pipeline's file byte for byte.

Run after src/rebuild.py and src/store/build_store.py.
"""
import filecmp
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.config import load_config
from src.store import accepted_money

CFG = load_config()
INTERMEDIATE = CFG['_root'] / CFG['paths']['intermediate']
GOLD_WRITERS = {accepted_money.write: ['money_pas2_weball.csv', 'money_per_cycle.json']}


def main():
    mismatches = []
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        for write, files in GOLD_WRITERS.items():
            write(scratch)
            for name in files:
                same = filecmp.cmp(scratch / name, INTERMEDIATE / name, shallow=False)
                print(f"{'same' if same else 'DIFFERS'}  {name}")
                if not same:
                    mismatches.append(name)
    if mismatches:
        sys.exit(f'gold views differ from the pipeline: {mismatches}')


if __name__ == '__main__':
    main()

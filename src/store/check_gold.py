#!/usr/bin/env python3
"""Fail unless every gold view reproduces the old pipeline's file byte for byte,
and the store's seats and terms hold together.

Run after src/rebuild.py and src/store/build_store.py.
"""
import filecmp
import sys
import tempfile
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.config import load_config
from src.store import accepted_money

CFG = load_config()
INTERMEDIATE = CFG['_root'] / CFG['paths']['intermediate']
STORE = CFG['_root'] / CFG['paths']['store']
GOLD_WRITERS = {accepted_money.write: ['money_pas2_weball.csv', 'money_per_cycle.json']}


SEATS_IN_FORCE = """
    SELECT seat_id FROM seats
    WHERE chamber = 'Senate' OR map_first_election = {year}
       OR (map_first_election < {year}
           AND state NOT IN (SELECT state FROM seats WHERE map_first_election = {year}))"""
STORE_FACTS = {
    'voting House seats for the 2024 election': (
        "SELECT count(*) FROM seats WHERE chamber = 'House' AND voting AND map_first_election = 2024", 435),
    'voting House seats for the 2026 election': (
        f"SELECT count(*) FROM seats WHERE chamber = 'House' AND voting AND seat_id IN ({SEATS_IN_FORCE.format(year=2026)})", 435),
    'Senate seats': ("SELECT count(*) FROM seats WHERE chamber = 'Senate'", 100),
    'non-voting delegate seats': ("SELECT count(*) FROM seats WHERE NOT voting", 6),
    'terms in a seat the table lacks': (
        "SELECT count(*) FROM terms WHERE seat_id NOT IN (SELECT seat_id FROM seats)", 0),
    '120th terms in a seat not up for 2026': (
        f"SELECT count(*) FROM terms WHERE congress = 120 AND seat_id NOT IN ({SEATS_IN_FORCE.format(year=2026)})", 0),
    'seats with two 120th members': (
        "SELECT count(*) FROM (SELECT seat_id FROM terms WHERE congress = 120 GROUP BY 1 HAVING count(*) > 1)", 0),
}


def check_store_facts():
    failed = []
    with duckdb.connect(str(STORE), read_only=True) as db:
        for fact, (query, expected) in STORE_FACTS.items():
            found = db.execute(query).fetchone()[0]
            print(f"{'ok' if found == expected else 'WRONG':>7}  {fact}: {found}")
            if found != expected:
                failed.append(fact)
    return failed


def main():
    mismatches = check_store_facts()
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
        sys.exit(f'store checks failed: {mismatches}')


if __name__ == '__main__':
    main()

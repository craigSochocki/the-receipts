"""Gold tables: each money step's per-person results, in cents, for dbt and the dataset."""

import duckdb
import pandas as pd

from receipts.common.settings import PATHS
from receipts.domain.money import Money

SQL_TYPES = {bool: 'BOOLEAN', int: 'BIGINT', str: 'VARCHAR'}


def cents(text):
    """A dollar amount as a money step writes it ('1234.50'), in cents; blank or unknown is NULL."""
    if text in (None, '', 'unknown'):
        return None
    return Money.parse(str(text)).cents


def write_gold(table, rows, dollar_columns):
    """Replace gold.<table> with `rows` (dicts, all with the same keys).

    `dollar_columns` hold dollar text and are stored as cents; every other
    column keeps its Python type (text, integer or yes/no).
    """
    columns = list(rows[0])
    stored = [{c: cents(r[c]) if c in dollar_columns else r[c] for c in columns} for r in rows]
    definition = ', '.join(f'{c} {sql_type(c, stored, dollar_columns)}' for c in columns)
    with duckdb.connect(str(PATHS.store)) as db:
        db.execute('CREATE SCHEMA IF NOT EXISTS gold')
        db.execute(f'CREATE OR REPLACE TABLE gold.{table} ({definition})')
        db.register('frame', pd.DataFrame(stored, columns=columns))
        db.execute(f'INSERT INTO gold.{table} SELECT * FROM frame')


def sql_type(column, rows, dollar_columns):
    if column in dollar_columns:
        return 'BIGINT'
    kinds = {type(r[column]) for r in rows if r[column] is not None}
    return SQL_TYPES[kinds.pop()] if len(kinds) == 1 else 'VARCHAR'


def per_cycle_rows(per_person, key='per_cycle'):
    """Flatten {person_key: {key: [entry, ...]}} into rows with person_key and entry order."""
    return [
        {'person_key': person_key, 'entry': n, **entry}
        for person_key, record in per_person.items()
        for n, entry in enumerate(record[key])
    ]

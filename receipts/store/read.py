"""Read-only access to the store for the scripts that write gold files."""

import duckdb

from receipts.common.settings import settings


def connect():
    return duckdb.connect(str(settings().paths.store), read_only=True)


def for_candidates(db, query, candidate_ids, *params):
    """Rows of `query` (which must end in a WHERE clause) for these candidate IDs only."""
    return db.execute(
        query + ' AND list_contains(?, candidate_id)', [*params, sorted(candidate_ids)]
    ).fetchall()

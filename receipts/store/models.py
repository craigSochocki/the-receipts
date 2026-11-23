"""Build one layer of the dbt project (dbt/) and run every test on it.

`silver`: the views over the store's tables, and the store's own tests.
`marts`: the per-person marts over the gold tables the money steps write.
`published`: the check that the marts agree with the dataset just written.
"""

import os
import sys

from dbt.cli.main import dbtRunner

from receipts.common.settings import PATHS, ROOT

PROJECT = ROOT / 'dbt'
COMPARISON = 'marts_match_the_published_dataset'
LAYERS = {
    'silver': ['--select', 'source:store', 'path:models/silver'],
    'marts': ['--select', 'source:gold', 'path:models/marts', '--exclude', COMPARISON],
    'published': ['--select', COMPARISON],
}


def build(layer):
    os.environ['RECEIPTS_STORE'] = str(PATHS.store)
    os.environ['RECEIPTS_DATASET'] = str(PATHS.dataset_json)
    args = ['build', '--project-dir', str(PROJECT), '--profiles-dir', str(PROJECT)]
    result = dbtRunner().invoke([*args, *LAYERS[layer]])
    if not result.success:
        raise SystemExit(f'dbt build of {layer} failed: a model or a test did not pass (see above)')


if __name__ == '__main__':
    build(sys.argv[1])

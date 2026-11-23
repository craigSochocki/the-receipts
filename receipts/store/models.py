"""Build one layer of the dbt project (dbt/) and run every test on it.

`silver`: the views over the store's tables, and the store's own tests.
`marts`: the per-person marts over the gold tables the money steps write.
"""

import os
import sys

from dbt.cli.main import dbtRunner

from receipts.common.settings import settings

LAYERS = {
    'silver': ['--select', 'source:store', 'path:models/silver', '--exclude', 'source:gold'],
    'marts': ['--select', 'source:gold', 'path:models/marts'],
}


def build(layer):
    os.environ['RECEIPTS_STORE'] = str(settings().paths.store)
    project = str(settings().root / 'dbt')
    args = ['build', '--project-dir', project, '--profiles-dir', project]
    result = dbtRunner().invoke([*args, *LAYERS[layer]])
    if not result.success:
        raise SystemExit(f'dbt build of {layer} failed: a model or a test did not pass (see above)')


if __name__ == '__main__':
    build(sys.argv[1])

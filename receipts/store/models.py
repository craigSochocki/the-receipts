"""Build the dbt models over the store and run every test on them (dbt/)."""

import os

from dbt.cli.main import dbtRunner

from receipts.common.settings import PATHS, ROOT

PROJECT = ROOT / 'dbt'


def main():
    os.environ['RECEIPTS_STORE'] = str(PATHS.store)
    result = dbtRunner().invoke(
        ['build', '--project-dir', str(PROJECT), '--profiles-dir', str(PROJECT)]
    )
    if not result.success:
        raise SystemExit('dbt build failed: a model or a test did not pass (see above)')


if __name__ == '__main__':
    main()

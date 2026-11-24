"""Progress messages for every entry point, as plain lines on stdout."""

import logging
import sys

log = logging.getLogger('receipts')


def run(main, *args):
    """Run a script's main with its progress messages shown, whatever dbt does to logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    main(*args)

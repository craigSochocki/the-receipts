"""Progress messages for every entry point, as plain lines on stdout."""

import logging
import sys

log = logging.getLogger('receipts')


def run(main, *args):
    """Run a script's main with its progress messages shown."""
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    main(*args)

import logging

import pytest

from receipts.validate.audit import Audit


def test_passing_checks_finish_cleanly(caplog):
    caplog.set_level(logging.INFO)
    audit = Audit()
    audit.check('two is two', 2 == 2)
    audit.finish('all clean')
    assert caplog.messages[-1] == 'all clean'


def test_a_failed_check_exits_listing_it(caplog):
    caplog.set_level(logging.INFO)
    audit = Audit()
    audit.check('two is three', 2 == 3, 'got 2')
    with pytest.raises(SystemExit) as stop:
        audit.finish('all clean')
    assert stop.value.code == 1
    assert '  - two is three: got 2' in caplog.messages

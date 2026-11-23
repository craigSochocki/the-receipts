from receipts.validate.run_history import file_age_days, row_drops


def row(file, cycle, rows, modified='2026-11-20T06:00:00Z', snapshot='fec-bulk-2026-11-15'):
    return {
        'snapshot': snapshot,
        'file': file,
        'cycle': cycle,
        'rows_read': rows,
        'last_modified': modified,
    }


def test_a_file_may_lose_up_to_the_allowed_share():
    assert row_drops([row('pas2', 2026, 1000)], [row('pas2', 2026, 990)]) == []


def test_a_bigger_drop_fails():
    assert row_drops([row('pas2', 2026, 1000)], [row('pas2', 2026, 989)]) == [
        'pas2 2026: 989 rows, was 1,000 in fec-bulk-2026-11-15'
    ]


def test_a_missing_file_fails():
    assert len(row_drops([row('ie', 2024, 10)], [])) == 1


def test_file_age_is_the_newest_current_cycle_file():
    current = [
        row('cm', 2026, 1, '2026-11-01T00:00:00Z'),
        row('weball', 2026, 1, '2026-11-08T23:59:59Z'),
        row('cm', 2024, 1, '2026-11-21T00:00:00Z'),
        row('ie', 2026, 1, None),
    ]
    assert file_age_days(current, 'fec-bulk-2026-11-22') == 14

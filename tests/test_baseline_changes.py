from src.validate.baseline_changes import changes, table


def test_lists_changed_added_and_removed_figures_but_not_snapshot_tags():
    old = {'_snapshot': 'fec-bulk-a', 'roster.total': 10.5, 'gone': 3, 'same': 1}
    new = {'_snapshot': 'fec-bulk-b', 'roster.total': 12.25, 'new': 4, 'same': 1}
    assert changes(old, new) == [('gone', 3, None), ('new', None, 4), ('roster.total', 10.5, 12.25)]


def test_the_table_shows_old_next_to_new():
    assert table([('roster.total', 10.5, 1234.5)]).splitlines()[-1] == (
        '| `roster.total` | 10.50 | 1,234.50 |')
    assert table([]) == 'No baseline figure moved.'

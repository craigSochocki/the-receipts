from receipts.store.build_store import file_and_cycle


def test_cycle_comes_from_the_file_name():
    assert file_and_cycle('pas2/pas224.zip') == ('pas2', 2024)
    assert file_and_cycle('cm/cm80.zip') == ('cm', 1980)
    assert file_and_cycle('weball/weball00.zip') == ('weball', 2000)
    assert file_and_cycle('ie/2022/independent_expenditure_2022.csv') == ('ie', 2022)

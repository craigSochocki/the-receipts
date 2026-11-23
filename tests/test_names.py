from receipts.domain.names import first_names_agree, slug, split_name


def test_split_handles_suffixes_and_known_multiword_names():
    assert split_name('Nicholas J. Begich III') == ('Nicholas J.', 'Begich')
    assert split_name('Chris Van Hollen') == ('Chris', 'Van Hollen')
    assert split_name('Mary Gay Scanlon') == ('Mary Gay', 'Scanlon')


def test_nicknames_agree_with_legal_names():
    assert first_names_agree('Bernie', 'Bernard')
    assert first_names_agree('Bob', 'Robert')
    assert first_names_agree('Andy', 'Garland', 'Andy', 'Andy Barr')


def test_different_first_names_do_not_agree():
    assert not first_names_agree('Sylvia', 'Johnny')


def test_slug_is_the_published_person_key_shape():
    # norm() drops the joining dashes; only spaces inside names become dashes.
    # These keys are published, so the shape is load-bearing.
    assert (
        slug('Pablo José', 'Hernández Rivera', 'PR', 'House') == 'pablo-josehernandez-riveraprhouse'
    )

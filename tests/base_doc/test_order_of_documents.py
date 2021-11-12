from paradoc import OneDoc


def test_order_of_docs(files_dir):
    source_dir = files_dir / "order_of_docs"
    one = OneDoc(source_dir)

    assert_list_main = [
        "order_of_docs\\00-main\\00-intro.md",
        "order_of_docs\\00-main\\01-part1\\00-intro.md",
        "order_of_docs\\00-main\\02-part2\\00-intro.md",
    ]

    for f_assert, md_actual in zip(assert_list_main, one.md_files_main):
        desired_f = files_dir / f_assert
        actual_f = md_actual.path
        assert desired_f.as_posix() == actual_f.as_posix()

    assert_list_app = [
        "order_of_docs\\01-app\\00-app1.md",
        "order_of_docs\\01-app\\01-part1\\00-intro.md",
        "order_of_docs\\01-app\\02-part2\\00-intro.md",
    ]

    for f_assert, md_actual in zip(assert_list_app, one.md_files_app):
        desired_f = files_dir / f_assert
        actual_f = md_actual.path
        assert desired_f.as_posix() == actual_f.as_posix()

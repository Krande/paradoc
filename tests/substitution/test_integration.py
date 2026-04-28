"""End-to-end: ${...} resolves to the same output as legacy {{__key__}}."""

from __future__ import annotations

import pandas as pd

from paradoc import OneDoc
from paradoc.db import dataframe_to_table_data


def _make_doc(tmp_path, body_text):
    test_dir = tmp_path / "doc"
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True)
    (main_dir / "test.md").write_text(body_text)
    return OneDoc(test_dir, work_dir=tmp_path / "work")


def _add_test_table(one, key="test_table"):
    df = pd.DataFrame({"Name": ["a", "b", "c"], "Value": [1, 2, 3]})
    one.db_manager.add_table(
        dataframe_to_table_data(key=key, df=df, caption=f"Caption for {key}", show_index=False)
    )


def test_new_syntax_resolves_db_table(tmp_path):
    one = _make_doc(tmp_path, "# X\n\n${ test_table }\n")
    _add_test_table(one)
    one.compile("OutDoc", export_format="html")

    build = tmp_path / "work" / "_build" / "00-main" / "test.md"
    text = build.read_text(encoding="utf-8")
    assert "${" not in text, "new-syntax marker should not survive into build"
    assert "Caption for test_table" in text


def test_new_and_legacy_syntax_produce_same_output(tmp_path):
    one_new = _make_doc(tmp_path / "new", "# X\n\n${ t }\n")
    _add_test_table(one_new, key="t")
    one_new.compile("New", export_format="html")
    new_text = (tmp_path / "new" / "work" / "_build" / "00-main" / "test.md").read_text()

    one_old = _make_doc(tmp_path / "old", "# X\n\n{{__t__}}\n")
    _add_test_table(one_old, key="t")
    one_old.compile("Old", export_format="html")
    old_text = (tmp_path / "old" / "work" / "_build" / "00-main" / "test.md").read_text()

    assert new_text == old_text


def test_kwargs_translate_to_table_annotation(tmp_path):
    one = _make_doc(tmp_path, '# X\n\n${ t(no_caption=True) }\n')
    _add_test_table(one, key="t")
    one.compile("Out", export_format="html")
    text = (tmp_path / "work" / "_build" / "00-main" / "test.md").read_text()

    assert "Caption for t" not in text
    assert "${" not in text


def test_unresolved_substitution_left_as_is(tmp_path, caplog):
    import logging

    one = _make_doc(tmp_path, "# X\n\n${ unknown_thing }\n")
    with caplog.at_level(logging.WARNING):
        one.compile("Out", export_format="html")
    text = (tmp_path / "work" / "_build" / "00-main" / "test.md").read_text()
    assert "${ unknown_thing }" in text
    assert any("Unresolved substitution" in r.message for r in caplog.records)


def test_legacy_syntax_emits_deprecation(tmp_path, caplog):
    import logging

    one = _make_doc(tmp_path, "# X\n\n{{__t__}}\n")
    _add_test_table(one, key="t")
    with caplog.at_level(logging.WARNING):
        one.compile("Out", export_format="html")
    assert any("Deprecated legacy substitution" in r.message for r in caplog.records)

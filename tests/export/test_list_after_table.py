"""DOCX export of a bullet list that directly follows a table."""

from paradoc import OneDoc

MD = """# Section

| Item | Value |
|------|-------|
| a    | 1     |
| b    | 2     |

- first point
- second point
"""


def test_bullet_list_after_table_exports(tmp_path):
    src = tmp_path / "doc"
    main = src / "00-main"
    main.mkdir(parents=True)
    (main / "content.md").write_text(MD, encoding="utf-8")

    one = OneDoc(src, work_dir=tmp_path / "work")
    one.compile("list_after_table", export_format="docx", auto_open=False)

    out = list((tmp_path / "work").rglob("list_after_table.docx"))
    assert out, "DOCX was not written"

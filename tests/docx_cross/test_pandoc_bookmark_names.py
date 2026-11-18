"""pandoc >= 3.12 writes hashed DOCX bookmark names; the exporter maps them back to the ids.

These run without pandoc: the names below are what pandoc 3.13 wrote for the ids.
"""

import zipfile

from paradoc.io.word.pandoc_bookmarks import (
    identifiers_in_markdown,
    pandoc_bookmark_name,
    restore_pandoc_bookmark_names,
)

# Bookmark names pandoc 3.13 wrote into a DOCX for these ids.
PANDOC_3_13_NAMES = {
    "section-1": "_3f3c65a76de9e0c3031ccb7f2069642064a0fd6",
    "fig:a": "_da29148b81ed9197ce8333fc723e94aec83a313",
    "tbl:m": "_5d2bdfd434814965b70bee1ca16915b43546d51",
    "eq:basic": "_e67a00a398d577a87d9d66d3c7ea2701411b566",
}

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def test_pandoc_bookmark_name_matches_pandoc():
    for ident, name in PANDOC_3_13_NAMES.items():
        assert pandoc_bookmark_name(ident) == name
    assert pandoc_bookmark_name("plain_id1") == "_plain_id1"


def test_identifiers_in_markdown():
    md = (
        "See [@fig:trends] and @tbl:metrics, and [@eq:a; @eq:b].\n\n"
        "![Cap](x.png){#fig:trends width=50%}\n\n"
        "$$ x $$ {#eq:a}\n\n"
        "Mail me at name@example.com.\n"
    )
    ids = identifiers_in_markdown(md)
    assert {"fig:trends", "tbl:metrics", "eq:a", "eq:b"} <= ids
    assert "example.com" not in ids


def _docx(path, body):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f"<w:document {W}><w:body>{body}</w:body></w:document>")


def _document_xml(path):
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


def test_restore_renames_bookmarks_and_link_anchors(tmp_path):
    eq = PANDOC_3_13_NAMES["eq:basic"]
    other = "_0123456789abcdef0123456789abcdef0123456"
    body = (
        f'<w:p><w:hyperlink w:anchor="{eq}"><w:r><w:t>eq. 1</w:t></w:r></w:hyperlink></w:p>'
        f'<w:p><w:bookmarkStart w:id="1" w:name="{eq}"/><w:bookmarkEnd w:id="1"/></w:p>'
        f'<w:p><w:bookmarkStart w:id="2" w:name="{other}"/><w:bookmarkEnd w:id="2"/></w:p>'
    )
    path = tmp_path / "t.docx"
    _docx(path, body)

    assert restore_pandoc_bookmark_names(path, {"eq:basic", "fig:unused"}) == 2

    xml = _document_xml(path)
    assert 'w:anchor="eq:basic"' in xml
    assert 'w:name="eq:basic"' in xml
    assert f'w:name="{other}"' in xml  # not derived from a known id: untouched
    with zipfile.ZipFile(path) as z:
        assert "[Content_Types].xml" in z.namelist()


def test_restore_leaves_older_pandoc_output_alone(tmp_path):
    body = '<w:p><w:bookmarkStart w:id="1" w:name="eq:basic"/><w:bookmarkEnd w:id="1"/></w:p>'
    path = tmp_path / "t.docx"
    _docx(path, body)
    before = path.read_bytes()

    assert restore_pandoc_bookmark_names(path, {"eq:basic"}) == 0
    assert path.read_bytes() == before

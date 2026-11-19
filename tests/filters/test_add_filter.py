"""OneDoc.add_filter: a filter instance made by the script that builds the document."""

from __future__ import annotations

import textwrap

import pytest

from paradoc import OneDoc
from paradoc.filters import Filter, attr


class Beam(Filter):
    def __init__(self, name: str, length: float):
        super().__init__(name)
        self._length = length

    @attr
    def length(self) -> float:
        return self._length


def _doc(tmp_path, body: str, filters_code: str | None = None) -> OneDoc:
    main = tmp_path / "doc" / "00-main"
    main.mkdir(parents=True)
    (main / "test.md").write_text(body, encoding="utf-8")
    if filters_code is not None:
        (tmp_path / "doc" / "filters.py").write_text(textwrap.dedent(filters_code), encoding="utf-8")
    return OneDoc(tmp_path / "doc", work_dir=tmp_path / "work")


def _built(tmp_path) -> str:
    return (tmp_path / "work" / "_build" / "00-main" / "test.md").read_text(encoding="utf-8")


def test_an_added_filter_fills_its_references(tmp_path):
    one = _doc(tmp_path, "B1 is ${ b1.length:.1f } m, B2 ${ b2.length:.1f } m.\n")
    one.add_filter(Beam("b1", 3.3))
    one.add_filter(Beam("b2", 4.0))
    one.compile("Out", export_format="html")
    assert "B1 is 3.3 m, B2 4.0 m." in _built(tmp_path)


def test_an_added_filter_sits_beside_the_doc_roots_filters(tmp_path):
    one = _doc(
        tmp_path,
        "${ b1.length:.1f } and ${ eig.first:.1f }\n",
        """
        from paradoc.filters import Filter, attr

        class Eig(Filter):
            @attr
            def first(self) -> float:
                return 1.5

        eig = Eig(name="eig")
        """,
    )
    one.add_filter(Beam("b1", 2.0))
    one.compile("Out", export_format="html")
    assert "2.0 and 1.5" in _built(tmp_path)


def test_add_filter_takes_filters_with_unique_names(tmp_path):
    one = _doc(tmp_path, "x\n")
    one.add_filter(Beam("b1", 1.0))
    with pytest.raises(ValueError, match="already registered"):
        one.add_filter(Beam("b1", 2.0))
    with pytest.raises(TypeError, match="Filter instance"):
        one.add_filter(object())

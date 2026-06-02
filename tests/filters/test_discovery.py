"""Filter discovery from a project's filters.py."""

import textwrap

from paradoc.filters import FilterRegistry, discover_filters


def test_discover_loads_path_module(tmp_path):
    (tmp_path / "filters.py").write_text(
        textwrap.dedent(
            """
            from paradoc.filters import Filter, attr

            class Demo(Filter):
                @attr
                def value(self):
                    return 7

            demo = Demo(name="demo")
            """
        )
    )

    reg = FilterRegistry()
    discover_filters(doc_root=tmp_path, registry=reg)

    assert "demo" in reg.known_names()
    assert reg.call_attr("demo", "value", {}) == 7


def test_discover_no_filters_module_is_silent(tmp_path):
    reg = FilterRegistry()
    discover_filters(doc_root=tmp_path, registry=reg)
    assert reg.known_names() == []

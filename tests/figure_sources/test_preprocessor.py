"""Figure-source comment preprocessor."""

import textwrap

import pytest

from paradoc.figure_sources import (
    CADModelFile,
    extract_figure_source_blocks,
    parse_spec_dict,
    preprocess_markdown,
)


def test_extract_blocks_finds_all():
    md = textwrap.dedent(
        """
        # Heading

        <!-- paradoc:figure
        figure_source: cad_model_file
        figure_title: Example
        source_inp: files/cad.stp
        camera_pos: iso_3
        -->

        Other text.

        <!-- paradoc:figure
        figure_source: cad_model_file
        figure_title: Example 2
        source_inp: files/other.stp
        -->
        """
    )
    blocks = extract_figure_source_blocks(md)
    assert len(blocks) == 2


def test_html_comments_without_prefix_ignored():
    md = "<!-- regular author comment -->\nText\n<!-- paradoc:figure\nfigure_source: cad_model_file\nfigure_title: T\nsource_inp: x.stp\n-->"
    blocks = extract_figure_source_blocks(md)
    assert len(blocks) == 1


def test_parse_spec_dict_skips_blank_and_comment_lines():
    body = "\n# author note\nfigure_source: cad_model_file\n\nfigure_title: Example\nsource_inp: files/cad.stp\n"
    data = parse_spec_dict(body)
    assert data == {
        "figure_source": "cad_model_file",
        "figure_title": "Example",
        "source_inp": "files/cad.stp",
    }


def test_parse_spec_missing_colon_raises():
    with pytest.raises(ValueError):
        parse_spec_dict("garbage line\n")


def test_preprocess_replaces_blocks():
    md = textwrap.dedent(
        """
        before

        <!-- paradoc:figure
        figure_source: cad_model_file
        figure_title: Example
        source_inp: files/cad.stp
        -->

        after
        """
    )

    def render(spec):
        assert isinstance(spec, CADModelFile)
        return f"![{spec.figure_title}](generated.png)"

    out = preprocess_markdown(md, render_block=render)
    assert "<!-- paradoc:figure" not in out
    assert "![Example](generated.png)" in out
    assert "before" in out and "after" in out


def test_preprocess_error_in_block_does_not_kill_render():
    md = textwrap.dedent(
        """
        <!-- paradoc:figure
        figure_source: nope_unknown
        figure_title: x
        -->
        rest of doc
        """
    )

    def render(spec):
        return "OK"

    out = preprocess_markdown(md, render_block=render)
    assert "ERROR" in out
    assert "rest of doc" in out

"""The feedstock recipe, pointed at a checkout.

paradoc's suite runs from a checkout against pixi.lock, so nothing it runs can see what
the PACKAGE contains or how it fares against the dependencies conda-forge resolves.
0.7.0 was released green and then failed on the feedstock (plotly 7, a missing pillow,
a stale pypandoc patch).

The rewrite these tests cover is what lets CI build the feedstock's own recipe against
this checkout, so that kind of fault shows up before a release rather than after one.
It is textual on purpose -- a YAML round-trip drops the recipe's comments -- which is
exactly why the shape of what it edits is worth pinning.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"

# SKIPPED AT MODULE LEVEL, before the import below, because the thing it imports is not
# in the package. The recipe ships `tests` and `files`; `scripts/` is not among them, so
# in a packaged test run this module would raise ModuleNotFoundError during COLLECTION --
# and a `pytestmark` skip cannot help, because collection has already failed by then.
if not (_SCRIPTS / "localise_feedstock_recipe.py").is_file():
    pytest.skip(
        "tests the repository's scripts/, which a packaged test run does not ship",
        allow_module_level=True,
    )

sys.path.insert(0, str(_SCRIPTS))

from localise_feedstock_recipe import (  # noqa: E402
    RecipeRewriteError,
    localise,
    project_version,
)

RECIPE = """schema_version: 1

context:
  python_min: "3.10"
  name: paradoc
  version: "0.6.1"

package:
  name: ${{ name }}
  version: ${{ version }}

source:
  url: https://github.com/Krande/paradoc/archive/v${{ version }}.tar.gz
  sha256: 6d49cfa85366af39a2b46a14b0a902a54dc32b2c568cd4bc85c040d1c63b07f5
  patches:
    - patches/remove_pypandoc_encoding_kwarg.patch

build:
  number: 0
  noarch: python

tests:
  - files:
      source:
        - tests
        - files
    script:
      # --timeout with the thread method (works on Windows) fails any test that
      # hangs instead of stalling CI, and dumps the hung test's stack trace.
      - pytest tests --ignore=tests/frontend --timeout=300 --timeout-method=thread
about:
  homepage: https://github.com/krande/paradoc
"""


def test_the_tarball_is_replaced_by_the_checkout():
    out = localise(RECIPE, "/work/paradoc")
    assert "path: /work/paradoc" in out
    # No part of the fetch may survive: a leftover `url` would be built INSTEAD of the
    # checkout, which would make this whole check silently test the released package.
    source_block = out.split("build:", 1)[0]
    assert "url:" not in source_block
    assert "sha256:" not in source_block


def test_tarball_patches_are_dropped_with_the_tarball():
    # A patch written against a released tarball has no business being applied to a
    # checkout; a fix that only lives in the feedstock belongs upstream.
    out = localise(RECIPE, "/work/paradoc")
    assert "patches" not in out


def test_the_comments_survive():
    out = localise(RECIPE, "/work/paradoc")
    assert "fails any test that" in out


def test_the_version_can_be_overridden_and_only_the_context_one_moves():
    # Building a checkout ahead of the released version while still claiming the old
    # number is the confusion this tool exists to remove.
    out = localise(RECIPE, "/work/paradoc", version="0.7.1")
    assert 'version: "0.7.1"' in out
    assert 'version: "0.6.1"' not in out
    assert "version: ${{ version }}" in out


def test_the_version_override_keeps_the_surrounding_blank_lines():
    out = localise(RECIPE, "/work/paradoc", version="0.7.1")
    assert 'version: "0.7.1"\n\npackage:' in out


def test_the_version_is_left_alone_when_not_asked_for():
    out = localise(RECIPE, "/work/paradoc")
    assert 'version: "0.6.1"' in out


def test_the_rest_of_the_recipe_is_untouched():
    out = localise(RECIPE, "/work/paradoc", version="0.7.1")
    for fragment in ("schema_version: 1", "name: paradoc", "python_min:", "- tests", "- files", "number: 0"):
        assert fragment in out, fragment
    assert "homepage: https://github.com/krande/paradoc" in out


def test_a_recipe_with_no_source_is_refused_rather_than_silently_built():
    with pytest.raises(RecipeRewriteError, match="no `source:` block"):
        localise("schema_version: 1\ncontext:\n  name: x\n", "/work/paradoc")


def test_the_version_override_refuses_when_there_is_nothing_to_override():
    with pytest.raises(RecipeRewriteError, match="context.version"):
        localise("source:\n  url: x\n\nbuild:\n  number: 0\n", "/work/paradoc", version="1.0.0")


def test_the_project_version_is_read_from_pyproject(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "paradoc"\nversion = "1.2.3"\n', encoding="utf-8")
    assert project_version(p) == "1.2.3"


def test_a_pyproject_without_a_version_is_an_error(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "paradoc"\n', encoding="utf-8")
    with pytest.raises(RecipeRewriteError):
        project_version(p)


def test_the_repo_pyproject_has_a_readable_version():
    assert project_version(_SCRIPTS.parent / "pyproject.toml")

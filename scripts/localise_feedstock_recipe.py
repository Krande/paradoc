"""Point a conda-forge feedstock recipe at a local checkout instead of a release tarball.

WHY THIS EXISTS. paradoc's own suite runs from a checkout against the versions in
pixi.lock, so nothing it runs can see what the *package* contains or how it behaves
against the dependency versions conda-forge resolves today. 0.7.0 showed the cost:
the release was cut green, and the feedstock then failed on plotly 7 (which rejects
the `scattermapbox` key in stored figure templates), on the recipe's test env lacking
pillow, and on a patch the recipe had carried since pypandoc 1.17 -- all found after
the release, by the feedstock, not by us.

This rewrites the feedstock's recipe so `rattler-build` builds THIS checkout rather
than a published tarball, which makes the feedstock's own definition -- what is
installed, which test files ship, which tests it runs -- a thing CI can check before
a release rather than after.

The rewrite is deliberately textual and minimal. A YAML round-trip would drop the
recipe's comments, and those comments are load-bearing (one records why the tests
run with a thread timeout). The source block is replaced whole, `patches:` included:
a patch written against a released tarball has no business being applied to a
checkout, and a fix that only lives in a feedstock patch belongs upstream anyway.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

#: Matches the whole `source:` block of a v1 recipe that fetches a tarball. Anchored
#: on the key at column 0 and terminated by the next top-level key, so an indented
#: `url:` elsewhere in the file cannot be mistaken for it.
_SOURCE_BLOCK = re.compile(
    r"^source:\n(?:[ \t]+.*\n|\n)*?(?=^[A-Za-z_]|\Z)",
    re.MULTILINE,
)

_VERSION_LINE = re.compile(r'^(?P<indent>[ \t]*)version:[ \t]*"[^"]*"[ \t]*$', re.MULTILINE)


class RecipeRewriteError(RuntimeError):
    """The recipe did not look the way this tool needs it to."""


def localise(recipe_text: str, checkout: str, version: str | None = None) -> str:
    """Return `recipe_text` with its source replaced by `checkout`.

    ``version`` overrides ``context.version`` when given. That matters because the
    original value is the released version, and building a checkout that is ahead of
    it would produce a package claiming to be the older one — which is exactly the
    confusion this whole tool exists to remove.
    """
    if "source:" not in recipe_text:
        raise RecipeRewriteError("no `source:` block found; is this a v1 recipe?")

    replacement = (
        "source:\n"
        "  # Rewritten by scripts/localise_feedstock_recipe.py: build THIS checkout\n"
        "  # rather than a published tarball, so packaging faults are visible before\n"
        "  # a release rather than after one.\n"
        f"  path: {checkout}\n"
        # The blank line the original block ended with, so the file reads the same
        # way after rewriting as it did before.
        + "\n"
    )
    # A FUNCTION, not the string: `re.sub` reads backslashes in a replacement as
    # escapes, so a Windows checkout path (`C:\work\paradoc`) either corrupts the
    # output or raises `bad escape \w`. Returning it from a lambda takes it
    # literally, which is the only correct reading of a filesystem path.
    new_text, count = _SOURCE_BLOCK.subn(lambda _: replacement, recipe_text, count=1)
    if count != 1:
        raise RecipeRewriteError("could not isolate the `source:` block")
    if "url:" in new_text.split("outputs:", 1)[0] and "path:" not in new_text.split("outputs:", 1)[0]:
        raise RecipeRewriteError("the source block still fetches a url after rewriting")

    if version is not None:
        # Only the FIRST version line, which is `context.version`. The outputs refer
        # to it through `${{ version }}` and must keep doing so.
        new_text, n = _VERSION_LINE.subn(lambda m: f'{m.group("indent")}version: "{version}"', new_text, count=1)
        if n != 1:
            raise RecipeRewriteError("could not find `context.version` to override")
    return new_text


def project_version(pyproject: pathlib.Path) -> str:
    """The version this checkout declares, so the built package is named honestly."""
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RecipeRewriteError(f'no `version = "..."` in {pyproject}')
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=pathlib.Path, help="the feedstock's recipe/recipe.yaml")
    parser.add_argument("--checkout", required=True, help="path the recipe should build from")
    parser.add_argument("--pyproject", type=pathlib.Path, default=None, help="take the version from here")
    parser.add_argument("-o", "--output", type=pathlib.Path, default=None, help="write here (default: in place)")
    args = parser.parse_args(argv)

    version = project_version(args.pyproject) if args.pyproject else None
    rewritten = localise(args.recipe.read_text(encoding="utf-8"), args.checkout, version)
    (args.output or args.recipe).write_text(rewritten, encoding="utf-8")
    print(f"recipe now builds {args.checkout}" + (f" as version {version}" if version else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

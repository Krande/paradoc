#!/usr/bin/env bash
# Build and test THIS checkout with the paradoc feedstock's recipe, exactly as conda-forge does.
#
# WHY THE FEEDSTOCK'S OWN BUILD AND NOT JUST ITS RECIPE. conda-forge builds inside
# quay.io/condaforge/linux-anvil-* with the feedstock mounted at /home/conda/feedstock_root, and
# the packaged tests run inside that checkout against whatever the solver picks TODAY -- not the
# versions in pixi.lock. Only the feedstock's build-locally.py reproduces the image, the mounts,
# the layout and the dependency resolution together (adapy learned the layout part the hard way:
# conda-forge/ada-py-feedstock#221).
#
# Usage: scripts/feedstock_build.sh [WORKDIR]      (needs docker, git, rsync and python3 on the host)
#   FEEDSTOCK_CONFIG   .ci_support variant to build (default: linux_64_)
#   FEEDSTOCK_REF      feedstock branch, tag or commit to test against (default: main)
set -euo pipefail

REPO="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
WORK="${1:-$(mktemp -d)}"
CONFIG="${FEEDSTOCK_CONFIG:-linux_64_}"
REF="${FEEDSTOCK_REF:-main}"
# Named like the real feedstock: run_docker_build.sh takes FEEDSTOCK_NAME from the directory.
FEEDSTOCK="$WORK/paradoc-feedstock"

rm -rf "$FEEDSTOCK"
# init + fetch rather than `clone --branch`: the latter takes only branch and tag names, and a
# commit is what you want to reproduce a past feedstock failure.
git init -q "$FEEDSTOCK"
git -C "$FEEDSTOCK" fetch -q --depth 1 https://github.com/conda-forge/paradoc-feedstock.git "$REF"
git -C "$FEEDSTOCK" checkout -q FETCH_HEAD

# The source must live INSIDE the feedstock: build-locally.py mounts only the feedstock root into
# the container. Tracked plus untracked-but-not-ignored files, so a local run builds the working
# tree you are looking at, not the last commit; deleted-but-tracked files are skipped.
SRC="$FEEDSTOCK/paradoc-src"
mkdir -p "$SRC"
(cd "$REPO" && git ls-files -z --cached --others --exclude-standard |
    rsync -a --from0 --ignore-missing-args --files-from=- ./ "$SRC/")

python3 "$REPO/scripts/localise_feedstock_recipe.py" "$FEEDSTOCK/recipe/recipe.yaml" \
    --checkout /home/conda/feedstock_root/paradoc-src --pyproject "$REPO/pyproject.toml"
sed -n '1,25p' "$FEEDSTOCK/recipe/recipe.yaml"

cd "$FEEDSTOCK"
# CI set: run_docker_build.sh adds `docker run -it` without it, which fails with no terminal.
CI="${CI:-true}" python3 build-locally.py "$CONFIG"

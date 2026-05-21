# Multi-stage build for `paradoc-serve` cloud deployments.
#
# Stage 1: build the frontend SPA bundle.
# Stage 2: solve the `serve` pixi environment from pixi.lock so the runtime
#          deps in this image are 1:1 with the local pixi env (no pip, no
#          PyPI extras, just conda-forge via the lockfile).

ARG PIXI_VERSION=0.68.0

FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY src/frontend/ ./
# `build:serve` uses vite.config.serve.ts — split chunks, no singlefile
# inlining. The default `build` (and `build:standalone`) still emit the
# self-contained 6.8 MiB index.html for offline/emailable docs.
RUN npm run build:serve


FROM ghcr.io/prefix-dev/pixi:${PIXI_VERSION} AS runtime
WORKDIR /app

# Sibling adapy checkout — even though the `serve` env doesn't depend
# on ada-py, pixi's `--locked` check verifies the whole workspace
# manifest against the lockfile, and `[feature.examples-figs]` carries
# `ada-py = { path = "../adapy", editable = true }`. Without the path
# present pixi rejects the lock as out-of-sync. Same pattern as
# Dockerfile.examples; the clone is shallow so it's cheap.
#
# `git` isn't in the slim pixi base, so install it from apt first.
# Mirror rewrite + HTTPS for the same egress reasons as adapy's
# Dockerfile.docs.
RUN sed -i 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g; s|http://security.ubuntu.com|https://security.ubuntu.com|g' /etc/apt/sources.list.d/*.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG ADAPY_GIT_URL
ARG ADAPY_REF=main
ARG CACHE_BUST=""
RUN test -n "$ADAPY_GIT_URL" \
        || (echo "::error::ADAPY_GIT_URL build-arg is required" >&2; exit 1) \
    && echo "cache-bust: $CACHE_BUST" \
    && git clone --depth 1 --branch "$ADAPY_REF" "$ADAPY_GIT_URL" /adapy

# Solve and materialise the pinned `serve` env first so source-only edits
# don't bust the heavy conda layer cache. pixi resolves `../adapy`
# relative to the workdir, so the sibling layout has to land before
# this RUN — see the clone above.
COPY pixi.toml pixi.lock pyproject.toml ./
RUN pixi install --environment serve --locked

# Source last for cache friendliness. PYTHONPATH points at src/ so the
# package is importable without a separate editable install.
COPY src/paradoc /app/src/paradoc

# Static SPA bundle from stage 1, served alongside the API by Traefik.
COPY --from=frontend-build /frontend/dist /app/static

# Build identity. The CI workflow passes --build-arg BUILD_SHA=$GITHUB_SHA
# (and BUILD_TAG / BUILD_TIME) so the running pod can self-report what
# image it is via /api/info — useful for the About panel in the UI and
# when debugging "is my fix actually live yet?".
ARG BUILD_SHA=unknown
ARG BUILD_TAG=unknown
ARG BUILD_TIME=unknown

ENV PYTHONPATH=/app/src \
    PARADOC_BUNDLE=/data/bundle \
    PARADOC_STATIC_DIR=/app/static \
    PARADOC_HOST=0.0.0.0 \
    PARADOC_PORT=8000 \
    PARADOC_BUILD_SHA=$BUILD_SHA \
    PARADOC_BUILD_TAG=$BUILD_TAG \
    PARADOC_BUILD_TIME=$BUILD_TIME

EXPOSE 8000

# `pixi run` activates the serve env and exec's python so PID 1 handles
# SIGTERM correctly under Kubernetes. Args are passed through the shell
# so the env-var defaults above can be overridden per-deploy.
ENTRYPOINT ["sh", "-c", "exec pixi run --environment serve python -m paradoc.serve.cli \"$PARADOC_BUNDLE\" --host \"$PARADOC_HOST\" --port \"$PARADOC_PORT\" \"$@\"", "--"]

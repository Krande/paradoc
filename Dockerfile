# Multi-stage build for `paradoc-serve` cloud deployments.
#
# Stage 1: build the frontend SPA bundle.
# Stage 2: solve the `serve` pixi environment from pixi.lock so the runtime
#          deps in this image are 1:1 with the local pixi env (no pip, no
#          PyPI extras, just conda-forge via the lockfile).

ARG PIXI_VERSION=0.67.0

FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY src/frontend/ ./
RUN npm run build


FROM ghcr.io/prefix-dev/pixi:${PIXI_VERSION} AS runtime
WORKDIR /app

# Solve and materialise the pinned `serve` env first so source-only edits
# don't bust the heavy conda layer cache.
COPY pixi.toml pixi.lock pyproject.toml ./
RUN pixi install --environment serve --locked

# Source last for cache friendliness. PYTHONPATH points at src/ so the
# package is importable without a separate editable install.
COPY src/paradoc /app/src/paradoc

# Static SPA bundle from stage 1, served alongside the API by Traefik.
COPY --from=frontend-build /frontend/dist /app/static

ENV PYTHONPATH=/app/src \
    PARADOC_BUNDLE=/data/bundle \
    PARADOC_STATIC_DIR=/app/static \
    PARADOC_HOST=0.0.0.0 \
    PARADOC_PORT=8000

EXPOSE 8000

# `pixi run` activates the serve env and exec's python so PID 1 handles
# SIGTERM correctly under Kubernetes. Args are passed through the shell
# so the env-var defaults above can be overridden per-deploy.
ENTRYPOINT ["sh", "-c", "exec pixi run --environment serve python -m paradoc.serve.cli \"$PARADOC_BUNDLE\" --host \"$PARADOC_HOST\" --port \"$PARADOC_PORT\" \"$@\"", "--"]

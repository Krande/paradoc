# Multi-stage build for `paradoc-serve` cloud deployments.
#
# Stage 1: build the frontend static bundle.
# Stage 2: install paradoc + serve extras and copy the built frontend in.
#
# The resulting image is read-only over compiled bundles. It does *not*
# include adapy or OCC — the build pipeline that produces bundles uses
# adapy elsewhere (CI of the project that ships the doc).

FROM node:20-alpine AS frontend-build

WORKDIR /frontend
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY src/frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

# This image is read-only over pre-built bundles. The build pipeline
# that produces bundles (which needs pandoc + adapy) lives elsewhere.
# `ca-certificates` is already present in the slim base, so we install
# nothing here and avoid hitting the OS package mirror at build time.
WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install --no-cache-dir ".[serve]"

# Static frontend bundle ready to be served alongside the API by an
# upstream proxy / ingress.
COPY --from=frontend-build /frontend/dist /app/static

ENV PARADOC_BUNDLE=/data/bundle
ENV PARADOC_HOST=0.0.0.0
ENV PARADOC_PORT=8000

EXPOSE 8000

ENTRYPOINT ["sh", "-c", "paradoc-serve \"$PARADOC_BUNDLE\" --host \"$PARADOC_HOST\" --port \"$PARADOC_PORT\""]

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

# pandoc is needed for compile mode but not strictly for serve mode;
# include it so the image can also run `paradoc compile` if desired.
RUN apt-get update \
    && apt-get install -y --no-install-recommends pandoc ca-certificates \
    && rm -rf /var/lib/apt/lists/*

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

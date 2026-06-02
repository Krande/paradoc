# paradoc-frontend Helm chart

Optional sub-chart for the adapy helm chart. Serves compiled paradoc
bundles from S3 (via `obstore`) or a mounted PVC.

The chart is gated by `enabled: false` so adopting projects opt in.
Add it to the parent chart's `Chart.yaml`:

```yaml
dependencies:
  - name: paradoc-frontend
    version: "*"
    repository: "file://../paradoc-frontend"
    condition: paradoc-frontend.enabled
```

Then in the parent `values.yaml`:

```yaml
paradoc-frontend:
  enabled: true
  bundle:
    source: s3
    s3Url: s3://my-bucket/reports
  s3:
    existingSecret: paradoc-s3-creds
    region: eu-north-1
```

## Auth

The default policy trusts upstream ingress headers
(`X-Auth-Request-User`). For belt-and-braces, set `auth.requireAuth: true`
to reject requests without an authenticated principal at the app layer
too.

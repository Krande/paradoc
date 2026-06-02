{{/*
Expand the name of the chart.
*/}}
{{- define "paradoc-frontend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "paradoc-frontend.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "paradoc-frontend.labels" -}}
app.kubernetes.io/name: {{ include "paradoc-frontend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "paradoc-frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "paradoc-frontend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
OIDC env-var block. Emits the env entries paradoc-serve reads to enable
multi-IdP token verification. ``auth.enabled=true`` is required;
``auth.providersExistingSecret`` should point at a Kubernetes Secret
holding the PARADOC_OIDC_PROVIDERS_JSON value (the JSON array of
provider blocks). ``auth.adminGroup`` is matched against the verified
token's groups claim to drive the admin role.

When auth.enabled is false, this expands to nothing — paradoc-serve
falls back to the synthetic local-dev admin user, which is what the
chart wants for dev / public-bundle deployments.
*/}}
{{- define "paradoc-frontend.authEnv" -}}
{{- if .Values.auth.enabled }}
- name: PARADOC_AUTH_ENABLED
  value: "true"
{{- if .Values.auth.providersExistingSecret }}
- name: PARADOC_OIDC_PROVIDERS_JSON
  valueFrom:
    secretKeyRef:
      name: {{ .Values.auth.providersExistingSecret }}
      key: {{ .Values.auth.providersExistingSecretKey | default "PARADOC_OIDC_PROVIDERS_JSON" }}
{{- end }}
{{- if .Values.auth.adminGroup }}
- name: PARADOC_AUTH_ADMIN_GROUP
  value: {{ .Values.auth.adminGroup | quote }}
{{- end }}
{{- end }}
{{- end -}}

{{/*
Postgres connection env. paradoc-serve's control plane (users, projects,
project_members) is optional — when PARADOC_DATABASE_URL is unset,
paradoc-serve runs in shared-only mode (no admin endpoints, no project
scopes).

Two ways to wire it:

  * ``database.existingSecret`` — name of a Secret in the same namespace
    holding the full DSN under ``database.existingSecretKey`` (default
    ``PARADOC_DATABASE_URL``). Use this with an ExternalSecret-backed
    Vault DSN; preferred in production.
  * ``database.url`` — inline literal DSN. Only use for local dev /
    tests where Vault isn't available. The literal lands in the chart
    rendered output, so don't store production credentials this way.
*/}}
{{- define "paradoc-frontend.databaseEnv" -}}
{{- if .Values.database.existingSecret }}
- name: PARADOC_DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.database.existingSecret }}
      key: {{ .Values.database.existingSecretKey | default "PARADOC_DATABASE_URL" }}
{{- else if .Values.database.url }}
- name: PARADOC_DATABASE_URL
  value: {{ .Values.database.url | quote }}
{{- end }}
{{- end -}}

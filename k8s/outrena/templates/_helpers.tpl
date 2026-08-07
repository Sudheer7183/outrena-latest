{{/*
Helpers for the OUTRENA Helm chart.
Standard pattern: define `outrena.fullname` once, reuse via `include "outrena.fullname" .`.
*/}}

{{/*
Expand the release-prefixed fullname used for every resource.
Mirrors the bitnami convention: release-name + chart-name, truncated to 63 chars
(DNS label limit) with trailing - stripped.
*/}}
{{- define "outrena.fullname" -}}
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

{{/*
Standard chart labels — applied to every resource.
*/}}
{{- define "outrena.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "outrena.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: outrena
outrena.com/phase: "6"
{{- end -}}

{{/*
Selector labels — must be a stable subset of `outrena.labels`.
Used in Deployment.spec.selector.matchLabels (immutable after creation).
*/}}
{{- define "outrena.selectorLabels" -}}
app.kubernetes.io/name: {{ include "outrena.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Chart name (defaults to .Chart.Name, override via .Values.nameOverride).
*/}}
{{- define "outrena.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Component names — used as the `app.kubernetes.io/component` label and as the
default container/pod name. Override per-component in values.yaml if needed.
*/}}
{{- define "outrena.backend.name" -}}
{{- default "backend" .Values.backend.name -}}
{{- end -}}

{{- define "outrena.frontend.name" -}}
{{- default "frontend" .Values.frontend.name -}}
{{- end -}}

{{- define "outrena.worker.name" -}}
{{- default "worker" .Values.worker.name -}}
{{- end -}}

{{- define "outrena.keycloak.name" -}}
{{- default "keycloak" .Values.keycloak.name -}}
{{- end -}}

{{/*
Postgres secret reference — returns either the user-supplied existingSecret
or the chart-managed postgres-secret. Used by the backend Deployment envFrom.
*/}}
{{- define "outrena.postgres-secret-ref" -}}
{{- if .Values.postgres.enabled -}}
{{- printf "%s-postgres" (include "outrena.fullname" .) -}}
{{- else -}}
{{- required "postgres.existingSecret is required when postgres.enabled=false" .Values.postgres.existingSecret -}}
{{- end -}}
{{- end -}}

{{/*
Redis secret reference — same pattern as postgres.
*/}}
{{- define "outrena.redis-secret-ref" -}}
{{- if .Values.redis.enabled -}}
{{- printf "%s-redis" (include "outrena.fullname" .) -}}
{{- else -}}
{{- required "redis.existingSecret is required when redis.enabled=false" .Values.redis.existingSecret -}}
{{- end -}}
{{- end -}}

{{/*
Image helper — resolves `image.tag` fallback to `global.imageTag`.
Usage: {{ include "outrena.image" (list . .Values.backend.image) }}
*/}}
{{- define "outrena.image" -}}
{{- $root := index . 0 -}}
{{- $img := index . 1 -}}
{{- $tag := $img.tag | default $root.Values.global.imageTag -}}
{{- $pullPolicy := $img.pullPolicy | default $root.Values.global.imagePullPolicy -}}
{{- printf "%s:%s" $img.repository $tag -}}
{{- end -}}

{{/*
imagePullSecrets helper — returns the YAML list fragment for `imagePullSecrets:`.
Usage: {{- include "outrena.imagePullSecrets" . | nindent 8 -}}
*/}}
{{- define "outrena.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets -}}
imagePullSecrets:
{{- toYaml . | nindent 0 -}}
{{- end -}}
{{- end -}}

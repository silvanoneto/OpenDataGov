{{/*
Expand the name of the chart.
*/}}
{{- define "feast.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "feast.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "feast.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "feast.labels" -}}
helm.sh/chart: {{ include "feast.chart" . }}
{{ include "feast.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "feast.selectorLabels" -}}
app.kubernetes.io/name: {{ include "feast.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "feast.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "feast.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host for registry
*/}}
{{- define "feast.postgresql.host" -}}
{{- if .Values.registry.backend.postgresql.host }}
{{- .Values.registry.backend.postgresql.host }}
{{- else }}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Redis host for online store
*/}}
{{- define "feast.redis.host" -}}
{{- if .Values.onlineStore.redis.host }}
{{- .Values.onlineStore.redis.host }}
{{- else }}
{{- printf "%s-redis-master" .Release.Name }}
{{- end }}
{{- end }}

{{/*
MinIO endpoint for offline store
*/}}
{{- define "feast.minio.endpoint" -}}
{{- if .Values.offlineStore.s3.endpoint }}
{{- .Values.offlineStore.s3.endpoint }}
{{- else }}
{{- printf "http://%s-minio:9000" .Release.Name }}
{{- end }}
{{- end }}

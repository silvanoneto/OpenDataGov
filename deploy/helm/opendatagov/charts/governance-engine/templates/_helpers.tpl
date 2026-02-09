{{/*
Expand the name of the chart.
*/}}
{{- define "governance-engine.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "governance-engine.fullname" -}}
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
{{- define "governance-engine.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "governance-engine.labels" -}}
helm.sh/chart: {{ include "governance-engine.chart" . }}
{{ include "governance-engine.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: opendatagov
app.kubernetes.io/component: governance
{{- end }}

{{/*
Selector labels
*/}}
{{- define "governance-engine.selectorLabels" -}}
app.kubernetes.io/name: {{ include "governance-engine.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "governance-engine.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "governance-engine.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "governance-engine.postgresql.host" -}}
{{- if .Values.postgresql.host }}
{{- .Values.postgresql.host }}
{{- else }}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Redis host
*/}}
{{- define "governance-engine.redis.host" -}}
{{- if .Values.redis.host }}
{{- .Values.redis.host }}
{{- else }}
{{- printf "%s-redis-master" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Kafka bootstrap servers
*/}}
{{- define "governance-engine.kafka.bootstrapServers" -}}
{{- if .Values.kafka.bootstrapServers }}
{{- .Values.kafka.bootstrapServers }}
{{- else }}
{{- printf "%s-kafka:9092" .Release.Name }}
{{- end }}
{{- end }}

{{/*
MinIO endpoint
*/}}
{{- define "governance-engine.minio.endpoint" -}}
{{- if .Values.minio.endpoint }}
{{- .Values.minio.endpoint }}
{{- else }}
{{- printf "%s-minio:9000" .Release.Name }}
{{- end }}
{{- end }}

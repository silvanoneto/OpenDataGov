{{/*
Expand the name of the chart.
*/}}
{{- define "lakehouse-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "lakehouse-agent.fullname" -}}
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
{{- define "lakehouse-agent.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "lakehouse-agent.labels" -}}
helm.sh/chart: {{ include "lakehouse-agent.chart" . }}
{{ include "lakehouse-agent.selectorLabels" . }}
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
{{- define "lakehouse-agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lakehouse-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "lakehouse-agent.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "lakehouse-agent.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "lakehouse-agent.postgresql.host" -}}
{{- if .Values.postgresql.host }}
{{- .Values.postgresql.host }}
{{- else }}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Redis host
*/}}
{{- define "lakehouse-agent.redis.host" -}}
{{- if .Values.redis.host }}
{{- .Values.redis.host }}
{{- else }}
{{- printf "%s-redis-master" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Kafka bootstrap servers
*/}}
{{- define "lakehouse-agent.kafka.bootstrapServers" -}}
{{- if .Values.kafka.bootstrapServers }}
{{- .Values.kafka.bootstrapServers }}
{{- else }}
{{- printf "%s-kafka:9092" .Release.Name }}
{{- end }}
{{- end }}

{{/*
MinIO endpoint
*/}}
{{- define "lakehouse-agent.minio.endpoint" -}}
{{- if .Values.minio.endpoint }}
{{- .Values.minio.endpoint }}
{{- else }}
{{- printf "%s-minio:9000" .Release.Name }}
{{- end }}
{{- end }}

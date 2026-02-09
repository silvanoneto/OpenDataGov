{{/*
Expand the name of the chart.
*/}}
{{- define "opendatagov.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "opendatagov.fullname" -}}
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
{{- define "opendatagov.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "opendatagov.labels" -}}
helm.sh/chart: {{ include "opendatagov.chart" . }}
{{ include "opendatagov.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: opendatagov
{{- end }}

{{/*
Selector labels
*/}}
{{- define "opendatagov.selectorLabels" -}}
app.kubernetes.io/name: {{ include "opendatagov.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
PostgreSQL fullname
*/}}
{{- define "opendatagov.postgresql.fullname" -}}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}

{{/*
Redis fullname
*/}}
{{- define "opendatagov.redis.fullname" -}}
{{- printf "%s-redis-master" .Release.Name }}
{{- end }}

{{/*
Kafka fullname
*/}}
{{- define "opendatagov.kafka.fullname" -}}
{{- printf "%s-kafka" .Release.Name }}
{{- end }}

{{/*
MinIO fullname
*/}}
{{- define "opendatagov.minio.fullname" -}}
{{- printf "%s-minio" .Release.Name }}
{{- end }}

{{/*
NATS fullname
*/}}
{{- define "opendatagov.nats.fullname" -}}
{{- printf "%s-nats" .Release.Name }}
{{- end }}

{{/*
Trino fullname
*/}}
{{- define "opendatagov.trino.fullname" -}}
{{- printf "%s-trino" .Release.Name }}
{{- end }}

{{/*
Airflow fullname
*/}}
{{- define "opendatagov.airflow.fullname" -}}
{{- printf "%s-airflow" .Release.Name }}
{{- end }}

{{/*
Superset fullname
*/}}
{{- define "opendatagov.superset.fullname" -}}
{{- printf "%s-superset" .Release.Name }}
{{- end }}

{{/*
Qdrant fullname
*/}}
{{- define "opendatagov.qdrant.fullname" -}}
{{- printf "%s-qdrant" .Release.Name }}
{{- end }}

{{/*
TimescaleDB fullname
*/}}
{{- define "opendatagov.timescaledb.fullname" -}}
{{- printf "%s-timescaledb" .Release.Name }}
{{- end }}

{{/*
Grafana fullname
*/}}
{{- define "opendatagov.grafana.fullname" -}}
{{- printf "%s-grafana" .Release.Name }}
{{- end }}

{{/*
Loki fullname
*/}}
{{- define "opendatagov.loki.fullname" -}}
{{- printf "%s-loki" .Release.Name }}
{{- end }}

{{/*
Tempo fullname
*/}}
{{- define "opendatagov.tempo.fullname" -}}
{{- printf "%s-tempo" .Release.Name }}
{{- end }}

{{/*
DataHub fullname
*/}}
{{- define "opendatagov.datahub.fullname" -}}
{{- printf "%s-datahub" .Release.Name }}
{{- end }}

{{/*
Keycloak fullname
*/}}
{{- define "opendatagov.keycloak.fullname" -}}
{{- printf "%s-keycloak" .Release.Name }}
{{- end }}

{{/*
OTel Collector fullname
*/}}
{{- define "opendatagov.otel-collector.fullname" -}}
{{- printf "%s-otel-collector" .Release.Name }}
{{- end }}

{{/*
Jaeger fullname
*/}}
{{- define "opendatagov.jaeger.fullname" -}}
{{- printf "%s-jaeger" .Release.Name }}
{{- end }}

{{/*
Governance Engine fullname
*/}}
{{- define "opendatagov.governance-engine.fullname" -}}
{{- printf "%s-governance-engine" .Release.Name }}
{{- end }}

{{/*
Lakehouse Agent fullname
*/}}
{{- define "opendatagov.lakehouse-agent.fullname" -}}
{{- printf "%s-lakehouse-agent" .Release.Name }}
{{- end }}

{{/*
Data Expert fullname
*/}}
{{- define "opendatagov.data-expert.fullname" -}}
{{- printf "%s-data-expert" .Release.Name }}
{{- end }}

{{/*
Quality Gate fullname
*/}}
{{- define "opendatagov.quality-gate.fullname" -}}
{{- printf "%s-quality-gate" .Release.Name }}
{{- end }}

{{/*
Gateway fullname
*/}}
{{- define "opendatagov.gateway.fullname" -}}
{{- printf "%s-gateway" .Release.Name }}
{{- end }}

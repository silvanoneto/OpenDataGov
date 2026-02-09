{{/*
Expand the name of the chart.
*/}}
{{- define "mlflow.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "mlflow.fullname" -}}
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
{{- define "mlflow.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "mlflow.labels" -}}
helm.sh/chart: {{ include "mlflow.chart" . }}
{{ include "mlflow.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "mlflow.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mlflow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "mlflow.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "mlflow.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "mlflow.postgresql.host" -}}
{{- if .Values.backend.postgresql.host }}
{{- .Values.backend.postgresql.host }}
{{- else }}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL connection string
*/}}
{{- define "mlflow.postgresql.connectionString" -}}
{{- $host := include "mlflow.postgresql.host" . }}
{{- $port := .Values.backend.postgresql.port }}
{{- $database := .Values.backend.postgresql.database }}
{{- printf "postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@%s:%d/%s" $host (int $port) $database }}
{{- end }}

{{/*
MinIO endpoint URL
*/}}
{{- define "mlflow.minio.endpointUrl" -}}
{{- if .Values.backend.artifactStore.s3.endpointUrl }}
{{- .Values.backend.artifactStore.s3.endpointUrl }}
{{- else }}
{{- printf "http://%s-minio:9000" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Artifact store URI
*/}}
{{- define "mlflow.artifactStore.uri" -}}
{{- if eq .Values.backend.artifactStore.type "s3" }}
{{- printf "s3://%s" .Values.backend.artifactStore.s3.bucket }}
{{- else }}
{{- "/mlflow/artifacts" }}
{{- end }}
{{- end }}

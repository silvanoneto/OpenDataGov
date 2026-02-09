{{/*
Expand the name of the chart.
*/}}
{{- define "kubeflow-pipelines.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "kubeflow-pipelines.fullname" -}}
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
{{- define "kubeflow-pipelines.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "kubeflow-pipelines.labels" -}}
helm.sh/chart: {{ include "kubeflow-pipelines.chart" . }}
{{ include "kubeflow-pipelines.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "kubeflow-pipelines.selectorLabels" -}}
app.kubernetes.io/name: {{ include "kubeflow-pipelines.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "kubeflow-pipelines.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "kubeflow-pipelines.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "kubeflow-pipelines.postgresql.host" -}}
{{- if .Values.apiServer.database.host }}
{{- .Values.apiServer.database.host }}
{{- else }}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL connection string for ML Metadata
*/}}
{{- define "kubeflow-pipelines.mlmd.connectionString" -}}
{{- $host := include "kubeflow-pipelines.postgresql.host" . }}
{{- $port := .Values.apiServer.database.port }}
{{- $database := .Values.apiServer.database.name }}
{{- printf "postgresql://$(DB_USER):$(DB_PASSWORD)@%s:%d/%s" $host (int $port) $database }}
{{- end }}

{{/*
MinIO endpoint URL
*/}}
{{- define "kubeflow-pipelines.minio.endpointUrl" -}}
{{- if .Values.apiServer.objectStore.host }}
{{- printf "%s:%d" .Values.apiServer.objectStore.host (int .Values.apiServer.objectStore.port) }}
{{- else }}
{{- printf "%s-minio:9000" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Artifact storage bucket path
*/}}
{{- define "kubeflow-pipelines.artifacts.bucketPath" -}}
{{- printf "minio://%s/%s" (include "kubeflow-pipelines.minio.endpointUrl" .) .Values.apiServer.objectStore.bucket }}
{{- end }}

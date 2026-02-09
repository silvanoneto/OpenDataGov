{{/*
Expand the name of the chart.
*/}}
{{- define "kserve.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "kserve.fullname" -}}
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
{{- define "kserve.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "kserve.labels" -}}
helm.sh/chart: {{ include "kserve.chart" . }}
{{ include "kserve.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "kserve.selectorLabels" -}}
app.kubernetes.io/name: {{ include "kserve.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "kserve.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "kserve.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
MinIO endpoint
*/}}
{{- define "kserve.minio.endpoint" -}}
{{- if .Values.storage.s3.endpoint }}
{{- .Values.storage.s3.endpoint }}
{{- else }}
{{- printf "%s-minio:9000" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Model storage URI
*/}}
{{- define "kserve.storage.uri" -}}
{{- if .Values.storage.s3.enabled }}
{{- printf "s3://%s" .Values.storage.s3.bucket }}
{{- else }}
{{- "/mnt/models" }}
{{- end }}
{{- end }}

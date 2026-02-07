{{/*
Common labels
*/}}
{{- define "opendatagov.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: opendatagov
{{- end }}

{{/*
Service-specific labels
*/}}
{{- define "opendatagov.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .release }}
{{- end }}

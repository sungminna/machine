{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "namu-wiki.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "namu-wiki.labels" -}}
helm.sh/chart: {{ include "namu-wiki.name" . }}
app.kubernetes.io/name: {{ include "namu-wiki.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
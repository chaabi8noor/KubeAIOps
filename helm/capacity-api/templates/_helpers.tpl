{{- define "capacity-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "capacity-api.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else if contains (include "capacity-api.name" .) .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "capacity-api.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "capacity-api.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "capacity-api.name" . }}
app.kubernetes.io/component: capacity-management
app.kubernetes.io/part-of: kubeaiops
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "capacity-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "capacity-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "capacity-api.serviceAccountName" -}}
{{- default "capacity-api" .Values.serviceAccount.name }}
{{- end }}

{{- define "capacity-api.configMapName" -}}
{{- default "capacity-api-config" .Values.config.name }}
{{- end }}

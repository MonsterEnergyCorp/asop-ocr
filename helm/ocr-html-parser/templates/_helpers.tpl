{{- define "ocr-html-parser.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "ocr-html-parser.fullname" -}}
{{- if .Values.fullnameOverride }}{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}{{- else }}{{- printf "%s-%s" .Release.Name (include "ocr-html-parser.name" .) | trunc 63 | trimSuffix "-" }}{{- end }}
{{- end }}
{{- define "ocr-html-parser.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "ocr-html-parser.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{- define "ocr-html-parser.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ocr-html-parser.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
{{- define "ocr-html-parser.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}{{- default (include "ocr-html-parser.fullname" .) .Values.serviceAccount.name }}{{- else }}{{- default "default" .Values.serviceAccount.name }}{{- end }}
{{- end }}

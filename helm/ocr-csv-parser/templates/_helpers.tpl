{{- define "ocr-csv-parser.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "ocr-csv-parser.fullname" -}}
{{- if .Values.fullnameOverride }}{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}{{- else }}{{- printf "%s-%s" .Release.Name (include "ocr-csv-parser.name" .) | trunc 63 | trimSuffix "-" }}{{- end }}
{{- end }}
{{- define "ocr-csv-parser.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "ocr-csv-parser.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{- define "ocr-csv-parser.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ocr-csv-parser.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
{{- define "ocr-csv-parser.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}{{- default (include "ocr-csv-parser.fullname" .) .Values.serviceAccount.name }}{{- else }}{{- default "default" .Values.serviceAccount.name }}{{- end }}
{{- end }}

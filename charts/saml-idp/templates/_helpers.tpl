{{/*
Chart name, truncated to fit label limits.
*/}}
{{- define "saml-idp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified app name.
*/}}
{{- define "saml-idp.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Chart name and version, used by the helm.sh/chart label.
*/}}
{{- define "saml-idp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels.
*/}}
{{- define "saml-idp.labels" -}}
helm.sh/chart: {{ include "saml-idp.chart" . }}
{{ include "saml-idp.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.extraLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/*
Selector labels.
*/}}
{{- define "saml-idp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "saml-idp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Name of the ServiceAccount to use.
*/}}
{{- define "saml-idp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "saml-idp.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Public base URL of the IdP: idp.baseUrl, else the first ingress host, else
empty (the app then derives it from each request).
*/}}
{{- define "saml-idp.baseUrl" -}}
{{- if .Values.idp.baseUrl -}}
{{- .Values.idp.baseUrl | trimSuffix "/" -}}
{{- else if .Values.ingress.enabled -}}
{{- $host := (first .Values.ingress.hosts).host -}}
{{- printf "%s://%s" (ternary "https" "http" (not (empty .Values.ingress.tls))) $host -}}
{{- end -}}
{{- end -}}

{{/*
The app's config.json, built from values.
*/}}
{{- define "saml-idp.config" -}}
{{- if not .Values.users -}}
{{- fail "users must contain at least one user" -}}
{{- end -}}
{{- $sp := dict
  "entityId" (required "sp.entityId is required" .Values.sp.entityId)
  "acsUrl" (required "sp.acsUrl is required" .Values.sp.acsUrl)
  "allowRequestAcsUrl" .Values.sp.allowRequestAcsUrl -}}
{{- $config := dict
  "baseUrl" (include "saml-idp.baseUrl" .)
  "entityId" .Values.idp.entityId
  "signResponse" .Values.idp.signResponse
  "signAssertion" .Values.idp.signAssertion
  "assertionLifetimeSeconds" (int .Values.idp.assertionLifetimeSeconds)
  "sp" $sp
  "attributeNames" .Values.attributeNames
  "users" .Values.users -}}
{{- toPrettyJson $config -}}
{{- end -}}

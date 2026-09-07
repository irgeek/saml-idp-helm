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
Name of the Secret holding the IdP signing cert/key. Fails the render if
neither an existing secret nor cert-manager has been configured.
*/}}
{{- define "saml-idp.certSecretName" -}}
{{- if .Values.certificate.existingSecret.name -}}
{{- .Values.certificate.existingSecret.name -}}
{{- else if .Values.certificate.certManager.enabled -}}
{{- default (printf "%s-tls" (include "saml-idp.fullname" .)) .Values.certificate.certManager.secretName -}}
{{- else -}}
{{- fail "You must set either certificate.existingSecret.name or certificate.certManager.enabled=true so saml-idp has a signing certificate/key" -}}
{{- end -}}
{{- end -}}

{{/*
Name of the ConfigMap holding config.js.
*/}}
{{- define "saml-idp.configMapName" -}}
{{- if .Values.config.existingConfigMap -}}
{{- .Values.config.existingConfigMap -}}
{{- else -}}
{{- include "saml-idp.fullname" . -}}
{{- end -}}
{{- end -}}

{{/*
CLI arguments for saml-idp, built from .Values.idp.* and the fixed in-pod
paths for the mounted cert/key/config.
*/}}
{{- define "saml-idp.args" -}}
- --host={{ .Values.idp.host }}
- --port={{ .Values.idp.port | toString }}
- --issuer={{ .Values.idp.issuer }}
- --acs={{ required "idp.acsUrl is required" .Values.idp.acsUrl }}
- --aud={{ required "idp.audience is required" .Values.idp.audience }}
- --cert=/etc/saml-idp/certs/{{ .Values.certificate.existingSecret.certKey | default "tls.crt" }}
- --key=/etc/saml-idp/certs/{{ .Values.certificate.existingSecret.keyKey | default "tls.key" }}
- --configFile=/etc/saml-idp/config/config.js
{{- if .Values.idp.sloUrl }}
- --slo={{ .Values.idp.sloUrl }}
{{- end }}
{{- if .Values.idp.serviceProviderId }}
- --spId={{ .Values.idp.serviceProviderId }}
{{- end }}
{{- if .Values.idp.authnContextClassRef }}
- --acr={{ .Values.idp.authnContextClassRef }}
{{- end }}
{{- if .Values.idp.authnContextDecl }}
- --acd={{ .Values.idp.authnContextDecl }}
{{- end }}
{{- if not .Values.idp.signResponse }}
- --signResponse=false
{{- end }}
{{- if .Values.idp.disableRequestAcsUrl }}
- --disableRequestAcsUrl
{{- end }}
{{- if .Values.idp.encryptAssertion }}
{{- if not .Values.idp.encryptionCert }}
{{- fail "idp.encryptionCert must be set when idp.encryptAssertion is true" }}
{{- end }}
- --enc
- --encryptionCert=/etc/saml-idp/encryption/tls.crt
{{- end }}
{{- if .Values.idp.relayState }}
- --rs={{ .Values.idp.relayState }}
{{- end }}
{{- if .Values.idp.rollSession }}
- --rollSession
{{- end }}
{{- range .Values.idp.extraArgs }}
- {{ . | quote }}
{{- end }}
{{- end -}}

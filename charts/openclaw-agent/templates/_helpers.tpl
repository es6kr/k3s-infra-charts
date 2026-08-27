{{/*
Chart name.
*/}}
{{- define "openclaw-agent.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{/*
Common labels.
*/}}
{{- define "openclaw-agent.labels" -}}
app.kubernetes.io/name: {{ include "openclaw-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Deterministic hash over everything that requires a re-provision when changed:
runtime package pins + the rendered agents/discord config. Used as the PVC
stamp-file comparison value so a warm pod restart skips both the npm install
and the config overwrite unless one of these inputs actually changed.
*/}}
{{- define "openclaw-agent.configHash" -}}
{{- $input := dict "runtimePackages" .Values.runtimePackages "agents" .Values.agents "discord" .Values.discord "gateway" .Values.gateway "ownerAllowFrom" .Values.ownerAllowFrom -}}
{{- $input | toJson | sha256sum -}}
{{- end -}}

{{/*
Init-container script: idempotent runtime provisioning.
Installs pinned model-provider packages into the PVC (skipped on a warm
restart via the stamp file) and renders openclaw.json from the ConfigMap
template with secret values substituted from env vars — never written to
the ConfigMap or to values.yaml in plaintext.
*/}}
{{- define "openclaw-agent.initScript" -}}
set -eu
STAMP=/home/node/.openclaw/.provision-stamp
WANT="{{ include "openclaw-agent.configHash" . }}"
RUNTIME_DIR=/home/node/.openclaw/runtime

CURRENT="$(cat "$STAMP" 2>/dev/null || true)"
if [ "$CURRENT" = "$WANT" ]; then
  echo "openclaw-agent: provision stamp unchanged ($WANT) — skipping npm install + config write"
  exit 0
fi

echo "openclaw-agent: provisioning (stamp $CURRENT -> $WANT)"

mkdir -p "$RUNTIME_DIR"
npm install --prefix "$RUNTIME_DIR" {{ .Values.runtimePackages | join " " }}

mkdir -p /home/node/.openclaw
sed \
  -e "s#__GATEWAY_TOKEN__#${GATEWAY_TOKEN}#g" \
  -e "s#__DISCORD_TOKEN_DGS_OPENCLAW__#${DISCORD_TOKEN_DGS_OPENCLAW}#g" \
  -e "s#__DISCORD_TOKEN_DGS_CLAUDE__#${DISCORD_TOKEN_DGS_CLAUDE}#g" \
  /config/openclaw.json.tmpl > /home/node/.openclaw/openclaw.json

# ANTHROPIC_SETUP_TOKEN is consumed directly by `openclaw models auth`, not
# written into openclaw.json — see README "Claude CLI auth" for the one-time
# manual step this chart does not automate yet.

printf '%s' "$WANT" > "$STAMP"
echo "openclaw-agent: provision complete"
{{- end -}}

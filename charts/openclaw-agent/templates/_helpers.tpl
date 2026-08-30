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
Deterministic hash over everything that requires a package re-install when
changed: runtime package pins + the rendered agents/discord config. Used as the
PVC stamp-file comparison value so a warm pod restart skips the npm install
unless one of these inputs actually changed.

Note this covers chart values only — it cannot observe Secret contents, which is
why the config render is NOT gated on it (see "initScript" below).
*/}}
{{- define "openclaw-agent.configHash" -}}
{{- $input := dict "runtimePackages" .Values.runtimePackages "agents" .Values.agents "discord" .Values.discord "gateway" .Values.gateway "ownerAllowFrom" .Values.ownerAllowFrom -}}
{{- $input | toJson | sha256sum -}}
{{- end -}}

{{/*
Init-container script: idempotent runtime provisioning.

Two independent concerns, deliberately gated separately:
  * package install  — expensive, gated on the stamp file (skipped on a warm restart)
  * config render    — cheap, ALWAYS re-run so a rotated Secret takes effect

The stamp hashes chart values only; it cannot see Secret contents, so gating the
config render on it would leave a restarted pod serving credentials that were
rotated out from under it.

Secret values are substituted with a node pass rather than `sed`: it JSON-escapes
each value (an unescaped `&` in a sed replacement expands to the matched text and
silently corrupts the token) and resolves every `__NAME__` placeholder the
ConfigMap emits, including accounts added after this chart was written.
*/}}
{{- define "openclaw-agent.initScript" -}}
set -eu
STAMP=/home/node/.openclaw/.provision-stamp
WANT="{{ include "openclaw-agent.configHash" . }}"
RUNTIME_DIR=/home/node/.openclaw/runtime

mkdir -p /home/node/.openclaw

CURRENT="$(cat "$STAMP" 2>/dev/null || true)"
if [ "$CURRENT" = "$WANT" ]; then
  echo "openclaw-agent: package stamp unchanged ($WANT) — skipping npm install"
else
  echo "openclaw-agent: installing runtime packages (stamp $CURRENT -> $WANT)"
  mkdir -p "$RUNTIME_DIR"
  npm install --prefix "$RUNTIME_DIR" {{ .Values.runtimePackages | join " " }}
fi

# Always rendered from the CURRENT Secret environment — never stamp-gated.
echo "openclaw-agent: rendering openclaw.json from the current secret environment"
node -e '
const fs = require("fs");
const src = fs.readFileSync("/config/openclaw.json.tmpl", "utf8");
const missing = [];
const out = src.replace(/__([A-Z0-9_]+)__/g, function (match, name) {
  const value = process.env[name];
  if (value === undefined || value === "") {
    missing.push(name);
    return match;
  }
  // JSON-escape, then strip the surrounding quotes the template already supplies.
  return JSON.stringify(value).slice(1, -1);
});
if (missing.length) {
  throw new Error("openclaw-agent: no secret value for placeholder(s): " + missing.join(", "));
}
JSON.parse(out); // fail loudly here rather than at gateway startup
fs.writeFileSync("/home/node/.openclaw/openclaw.json", out);
'

# ANTHROPIC_SETUP_TOKEN is NOT written into openclaw.json. Authenticating the
# Claude backend is a one-time manual step documented in the repository README
# under "Claude CLI auth"; the resulting auth profile persists on this PVC.

printf '%s' "$WANT" > "$STAMP"
echo "openclaw-agent: provision complete"
{{- end -}}

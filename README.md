# k3s-infra-charts

A Helm chart repository for Kubernetes and K3s infrastructure core components (`k3s-infra-base` umbrella chart and `cluster-issuers`).

## Included Charts

- **`k3s-infra-base`**: Umbrella chart rendering ArgoCD Applications for `ingress-nginx`, `cluster-issuers`, `longhorn`, `reflector`, `cnpg-operator`, and `vault` with single-values `enabled` toggles.
- **`cluster-issuers`**: Chart for deploying cert-manager `ClusterIssuers` for Let's Encrypt with global and per-issuer overrides.
- **`host-ip-service`**: Chart for bridging host-level TCP/HTTP services (e.g., Docker containers running on host IP `10.0.0.36`) into Kubernetes Service/Endpoints and generating corresponding Ingress resources with cert-manager TLS annotations.
- **`openclaw-agent`**: Chart for running one or more openclaw Discord agents on the unmodified upstream image, with model-provider packages installed into the PVC by an init container (not baked into the image) and config/secrets supplied as Kubernetes ConfigMap/Secret instead of an inline pod-command heredoc. `values.yaml` ships placeholder Discord IDs (`ownerAllowFrom`, `channelId`, `guildId`) — pass the real deployment-specific values via a separate `-f` override file kept outside this repo (they are identifying but not credentials; actual secrets always go through `existingSecret`, never a values file).

## Installation

Add the Helm repository:

```bash
helm repo add es6kr https://es6kr.github.io/k3s-infra-charts
helm repo update
```

Install `k3s-infra-base` umbrella chart:

```bash
helm install k3s-infra es6kr/k3s-infra-base -f values.yaml
```

Or install `cluster-issuers` chart standalone:

```bash
helm install cluster-issuers es6kr/cluster-issuers -f values.yaml
```

Or clone and inspect locally:

```bash
git clone https://github.com/es6kr/k3s-infra-charts.git
cd k3s-infra-charts
```

## `k3s-infra-base` Structure & Toggle

The `k3s-infra-base` chart uses a single-values toggle model to render ArgoCD Application CRs:

```yaml
global:
  cluster:
    name: "es6kr-oci"

components:
  ingress-nginx:
    enabled: true
    values:
      controller:
        service:
          externalIPs: ["203.0.113.10"]
  cluster-issuers:
    enabled: true
    values:
      global:
        acme:
          email: user@example.com
  longhorn:
    enabled: true
  reflector:
    enabled: true
  cnpg-operator:
    enabled: false
  vault:
    enabled: true
    values:
      server:
        ingress:
          hosts:
            - host: "vault.example.com"
              paths: ["/"]
          tls:
            - secretName: "wildcard-tls"
              hosts: ["vault.example.com"]
      oidc:
        issuerURL: "https://auth.example.com/application/o/vault/"
        clientID: "vault-sso"
        clientSecretRef: "vault-oidc-secret"
```

### Dynamic Values Generator (`generate_values.py`)

Clusters can generate their `values.yaml` dynamically from metadata JSON:

```bash
python3 charts/k3s-infra-base/generate_values.py \
  --meta cluster-meta.json \
  --schema charts/k3s-infra-base/values.schema.json \
  --output values.yaml
```

**Metadata JSON Schema Reference:**

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Cluster identifier (e.g. `dgs-dev36`) |
| `ingress` | string | No | Ingress type (`nginx` default) |
| `externalIPs` | array/string | No | Cluster VIPs / external IPs for ingress service |
| `domain` | string | No | Base cluster domain name (e.g. `dgs.ai.kr`) |
| `acmeEmail` | string | No | ACME contact email for Let's Encrypt |
| `cloudflareSecret` | string | No | Secret holding Cloudflare token (`cloudflare-api-token`) |
| `nodeCount` | integer | No | Node count for Longhorn replica calculation |
| `components` | object | No | Component enabled map (e.g. `{"vault": true}`) |
| `oidc` | object | No | Vault OIDC SSO configuration (`vaultIssuerURL`, `vaultClientID`, `vaultClientSecretRef`) |
| `wildcardTLSSecret` | string | No | Secret name for wildcard TLS certificate |


## `openclaw-agent` Secrets & Claude CLI auth

All credentials come from the Secret named by `existingSecret` (default
`openclaw-dgs-secrets`); none of them may be set in a values file. The init
container consumes the Secret via `envFrom` and substitutes each value into
`openclaw.json` at startup.

Required keys:

| Key | Purpose |
|-----|---------|
| `GATEWAY_TOKEN` | Token for the openclaw gateway's `auth.token` |
| `DISCORD_TOKEN_<ACCOUNT>` | Discord bot token, one per `discord.accounts` entry. The suffix is the account name uppercased with `-` replaced by `_` — `dgs-openclaw` becomes `DISCORD_TOKEN_DGS_OPENCLAW` |
| `ANTHROPIC_SETUP_TOKEN` | Only needed when an agent uses a `claude-cli/*` model. See below |

Adding a Discord account is values-only: add the entry under
`discord.accounts`, add an agent whose `discord.accountId` matches it, and add
the corresponding `DISCORD_TOKEN_<ACCOUNT>` key to the Secret. The init
container resolves every placeholder the ConfigMap emits, so no template change
is required.

### Claude CLI auth

The chart does **not** yet automate Anthropic authentication. Agents configured
with a `claude-cli/*` model (whether as `model` or in `fallback`) need a one-time
manual bootstrap; until it is done, requests routed to that backend fail while
the rest of the gateway works normally.

1. On a machine with an authenticated Claude Code CLI, generate a long-lived
   token (it starts with `sk-ant-oat01-`):

   ```bash
   claude setup-token
   ```

2. Store it in the Secret as `ANTHROPIC_SETUP_TOKEN`, so it is present in the
   pod environment.

3. Register the auth profile once, from inside the running pod:

   ```bash
   kubectl -n <namespace> exec -it <pod> -- \
     openclaw models auth login --provider anthropic --method setup-token
   ```

4. Confirm the profile is active:

   ```bash
   kubectl -n <namespace> exec -it <pod> -- openclaw models status
   ```

The resulting auth profile is written under `/home/node/.openclaw`, which is the
mounted PVC, so it survives pod restarts and does not need to be repeated on
every rollout. A setup token does not auto-refresh — if Claude requests start
returning 401, re-run `claude setup-token`, update the Secret, and repeat step 3.
For a long-lived gateway an Anthropic API key is the more predictable option.

## License

[Apache License 2.0](./LICENSE)
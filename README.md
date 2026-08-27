# k3s-infra-charts

A Helm chart repository for Kubernetes and K3s infrastructure core components (`k3s-infra-base` umbrella chart and `cluster-issuers`).

## Included Charts

- **`k3s-infra-base`**: Umbrella chart rendering ArgoCD Applications for `ingress-nginx`, `cluster-issuers`, `longhorn`, `reflector`, and `cnpg-operator` with single-values `enabled` toggles.
- **`cluster-issuers`**: Chart for deploying cert-manager `ClusterIssuers` for Let's Encrypt with global and per-issuer overrides.
- **`host-ip-service`**: Chart for bridging host-level TCP/HTTP services (e.g., Docker containers running on host IP `10.0.0.36`) into Kubernetes Service/Endpoints and generating corresponding Ingress resources with cert-manager TLS annotations.
- **`openclaw-agent`**: Chart for running one or more openclaw Discord agents on the unmodified upstream image, with model-provider packages installed into the PVC by an init container (not baked into the image) and config/secrets supplied as Kubernetes ConfigMap/Secret instead of an inline pod-command heredoc.

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
```

## License

[Apache License 2.0](./LICENSE)
#!/usr/bin/env python3
"""
k3s-infra-base Helm Chart Dynamic Values Generator & Schema Validator
Generates cluster-specific values.yaml from cluster metadata JSON and validates against values.schema.json.
"""

import json
import sys
import argparse
from typing import Dict, Any

try:
    import jsonschema
except ImportError:
    jsonschema = None

def generate_values(meta: Dict[str, Any]) -> Dict[str, Any]:
    cluster_name = meta.get("name")
    if not cluster_name:
        raise ValueError("Metadata field 'name' is required.")

    ingress_type = meta.get("ingress", "nginx")
    external_ips = meta.get("externalIPs", [])
    domain = meta.get("domain", "")
    acme_email = meta.get("acmeEmail", "")
    cloudflare_secret = meta.get("cloudflareSecret", "cloudflare-api-token")
    node_count = meta.get("nodeCount", 1)
    custom_components = meta.get("components", {})
    oidc = meta.get("oidc", {})
    wildcard_tls_secret = meta.get("wildcardTLSSecret", "")

    # Calculate longhorn replicaCount = min(nodeCount, 3)
    longhorn_replicas = min(max(int(node_count), 1), 3)

    # Ingress-nginx enabled toggle
    ingress_enabled = (ingress_type == "nginx")

    values: Dict[str, Any] = {
        "global": {
            "cluster": {
                "name": cluster_name
            }
        },
        "components": {
            "ingress-nginx": {
                "enabled": custom_components.get("ingress-nginx", ingress_enabled),
                "values": {
                    "controller": {
                        "service": {
                            "externalIPs": external_ips if ingress_enabled else ["100.64.0.1"]
                        }
                    }
                }
            },
            "cluster-issuers": {
                "enabled": custom_components.get("cluster-issuers", bool(domain and acme_email)),
                "values": {
                    "global": {
                        "acme": {
                            "email": acme_email or "user@example.com"
                        }
                    },
                    "clusterIssuers": {
                        "letsencrypt-prod": {
                            "server": "https://acme-v02.api.letsencrypt.org/directory",
                            "privateKeySecret": "letsencrypt-prod",
                            "solvers": [
                                {
                                    "dns01": {
                                        "cloudflare": {
                                            "apiTokenSecretRef": {
                                                "name": cloudflare_secret,
                                                "key": "api-token"
                                            }
                                        }
                                    },
                                    "selector": {
                                        "dnsZones": [domain] if domain else []
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            "longhorn": {
                "enabled": custom_components.get("longhorn", True),
                "values": {
                    "persistence": {
                        "defaultClassReplicaCount": longhorn_replicas
                    }
                }
            },
            "reflector": {
                "enabled": custom_components.get("reflector", True),
                "values": {}
            },
            "cnpg-operator": {
                "enabled": custom_components.get("cnpg-operator", False),
                "values": {}
            },
            "vault": {
                "enabled": custom_components.get("vault", False),
                "values": {
                    "server": {
                        "ha": {"enabled": False},
                        "ingress": {
                            "enabled": True,
                            "ingressClassName": "nginx",
                            "hosts": [
                                {
                                    "host": f"vault.{domain}" if domain else "",
                                    "paths": ["/"]
                                }
                            ],
                            "tls": [
                                {
                                    "secretName": wildcard_tls_secret,
                                    "hosts": [f"vault.{domain}" if domain else ""]
                                }
                            ]
                        }
                    },
                    "ui": {"enabled": True},
                    "oidc": {
                        "issuerURL": oidc.get("vaultIssuerURL", ""),
                        "clientID": oidc.get("vaultClientID", ""),
                        "clientSecretRef": oidc.get("vaultClientSecretRef", "vault-oidc-secret")
                    }
                }
            }
        }
    }

    return values

def validate_schema(values: Dict[str, Any], schema_path: str) -> None:
    if jsonschema is None:
        print("[WARN] jsonschema python package not installed; skipping client-side schema validation.", file=sys.stderr)
        return

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    jsonschema.validate(instance=values, schema=schema)
    print("✅ Values schema validation PASSED!")

def main():
    parser = argparse.ArgumentParser(description="Generate values.yaml for k3s-infra-base umbrella chart")
    parser.add_argument("--meta", required=True, help="Path to cluster metadata JSON file")
    parser.add_argument("--schema", help="Path to values.schema.json file for validation")
    parser.add_argument("--output", help="Output path for generated values (YAML/JSON)")
    args = parser.parse_args()

    with open(args.meta, "r", encoding="utf-8") as f:
        meta = json.load(f)

    generated = generate_values(meta)

    if args.schema:
        validate_schema(generated, args.schema)

    output_json = json.dumps(generated, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Generated values saved to: {args.output}")
    else:
        print(output_json)

if __name__ == "__main__":
    main()

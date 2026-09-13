#!/usr/bin/env python3
"""
Unit tests for k3s-infra-base dynamic values generator.
Verifies null handling, scalar externalIPs unwrapping, Vault OIDC configuration,
and schema validation conformance.
"""

import os
import sys
import unittest

# Add chart directory to sys.path
CHART_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, CHART_DIR)

import generate_values


class TestGenerateValues(unittest.TestCase):

    def test_null_oidc_and_wildcard_tls_secret(self):
        """Test that explicit null in oidc and wildcardTLSSecret does not raise AttributeError or render None."""
        meta = {
            "name": "test-cluster",
            "oidc": None,
            "wildcardTLSSecret": None,
        }
        values = generate_values.generate_values(meta)
        vault_values = values["components"]["vault"]["values"]
        self.assertEqual(vault_values["oidc"]["issuerURL"], "")
        self.assertEqual(vault_values["oidc"]["clientID"], "")
        self.assertEqual(vault_values["oidc"]["clientSecretRef"], "vault-oidc-secret")
        self.assertEqual(vault_values["server"]["ingress"]["tls"][0]["secretName"], "")

    def test_scalar_external_ips(self):
        """Test that scalar externalIPs string gets wrapped into a list."""
        meta = {
            "name": "test-cluster",
            "externalIPs": "100.82.193.45",
        }
        values = generate_values.generate_values(meta)
        ext_ips = values["components"]["ingress-nginx"]["values"]["controller"]["service"]["externalIPs"]
        self.assertEqual(ext_ips, ["100.82.193.45"])

    def test_empty_external_ips_fallback(self):
        """Test that empty externalIPs falls back to placeholder to satisfy minItems schema."""
        meta = {
            "name": "test-cluster",
            "externalIPs": [],
        }
        values = generate_values.generate_values(meta)
        ext_ips = values["components"]["ingress-nginx"]["values"]["controller"]["service"]["externalIPs"]
        self.assertEqual(ext_ips, ["100.64.0.1"])

    def test_vault_oidc_configured(self):
        """Test that Vault OIDC parameters are correctly mapped from metadata."""
        meta = {
            "name": "dgs-dev36",
            "domain": "dgs.ai.kr",
            "components": {
                "vault": True,
            },
            "oidc": {
                "vaultIssuerURL": "https://auth.dgs.ai.kr/application/o/vault/",
                "vaultClientID": "vault-sso",
                "vaultClientSecretRef": "custom-vault-secret",
            },
            "wildcardTLSSecret": "dgs-wildcard-tls",
        }
        values = generate_values.generate_values(meta)
        vault = values["components"]["vault"]
        self.assertTrue(vault["enabled"])
        self.assertEqual(vault["values"]["oidc"]["issuerURL"], "https://auth.dgs.ai.kr/application/o/vault/")
        self.assertEqual(vault["values"]["oidc"]["clientID"], "vault-sso")
        self.assertEqual(vault["values"]["oidc"]["clientSecretRef"], "custom-vault-secret")
        self.assertEqual(vault["values"]["server"]["ingress"]["hosts"][0]["host"], "vault.dgs.ai.kr")
        self.assertEqual(vault["values"]["server"]["ingress"]["tls"][0]["secretName"], "dgs-wildcard-tls")

    def test_schema_validation(self):
        """Test that sample-meta-dev36 generates values that pass schema validation."""
        meta_path = os.path.join(CHART_DIR, "tests", "sample-meta-dev36.json")
        schema_path = os.path.join(CHART_DIR, "values.schema.json")
        with open(meta_path, "r", encoding="utf-8") as f:
            import json
            meta = json.load(f)
        values = generate_values.generate_values(meta)
        try:
            import jsonschema
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=values, schema=schema)
        except ImportError:
            self.skipTest("jsonschema not installed")


if __name__ == "__main__":
    unittest.main()

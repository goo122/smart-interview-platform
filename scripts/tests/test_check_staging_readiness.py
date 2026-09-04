#!/usr/bin/env python3
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.check_staging_readiness import validate_compose_model, validate_values

VALID_VALUES = {
    "DOMAIN": "staging.invalid",
    "APP_ENV": "production",
    "APP_DEBUG": "false",
    "APP_SECRET_KEY": "a-strong-signing-key-with-at-least-32-characters",
    "POSTGRES_PASSWORD": "UrlSafeDatabasePassword_2026",
    "APP_AI_PROVIDER": "openai_compatible",
    "APP_LLM_API_KEY": "provider-key",
    "APP_LLM_BASE_URL": "https://llm.invalid/v1",
    "APP_LLM_MODEL": "chat-model",
    "APP_EMBEDDING_PROVIDER": "openai_compatible",
    "APP_EMBEDDING_API_KEY": "embedding-key",
    "APP_EMBEDDING_BASE_URL": "https://embedding.invalid/v1",
    "APP_EMBEDDING_MODEL": "embedding-model",
}


class StagingReadinessTests(unittest.TestCase):
    def test_valid_production_values_are_accepted(self) -> None:
        self.assertEqual(validate_values(VALID_VALUES), [])

    def test_placeholders_and_unsafe_values_are_rejected(self) -> None:
        values = VALID_VALUES | {
            "DOMAIN": "https://staging.example.com",
            "APP_DEBUG": "true",
            "POSTGRES_PASSWORD": "short",
        }

        errors = validate_values(values)

        self.assertTrue(any("placeholder" in error for error in errors))
        self.assertIn("APP_DEBUG must be false", errors)
        self.assertIn("POSTGRES_PASSWORD must use 24+ URL-safe characters", errors)
        self.assertTrue(any("hostname" in error for error in errors))

    @patch("scripts.check_staging_readiness.subprocess.run")
    def test_compose_network_boundary_is_accepted(self, run: Mock) -> None:
        run.return_value.stdout = json.dumps(
            {
                "services": {
                    "api": {"read_only": True},
                    "worker": {"read_only": True},
                    "frontend": {},
                    "postgres": {},
                    "redis": {},
                    "caddy": {"ports": [{"target": 80}, {"target": 443}]},
                }
            }
        )

        errors = validate_compose_model("docker", Path("prod.env"), {})

        self.assertEqual(errors, [])

    @patch("scripts.check_staging_readiness.subprocess.run")
    def test_published_database_port_is_rejected(self, run: Mock) -> None:
        run.return_value.stdout = json.dumps(
            {
                "services": {
                    "api": {"read_only": True},
                    "worker": {"read_only": True},
                    "frontend": {},
                    "postgres": {"ports": [{"target": 5432}]},
                    "redis": {},
                    "caddy": {"ports": [{"target": 80}, {"target": 443}]},
                }
            }
        )

        errors = validate_compose_model("docker", Path("prod.env"), {})

        self.assertIn("production service postgres must not publish host ports", errors)


if __name__ == "__main__":
    unittest.main()

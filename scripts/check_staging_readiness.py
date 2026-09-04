#!/usr/bin/env python3
"""Validate a staging environment and its production Compose model without external calls."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = (ROOT / "docker-compose.yml", ROOT / "compose.production.yml")
REQUIRED_KEYS = {
    "DOMAIN",
    "APP_ENV",
    "APP_DEBUG",
    "APP_SECRET_KEY",
    "POSTGRES_PASSWORD",
    "APP_AI_PROVIDER",
    "APP_LLM_API_KEY",
    "APP_LLM_BASE_URL",
    "APP_LLM_MODEL",
    "APP_EMBEDDING_PROVIDER",
    "APP_EMBEDDING_API_KEY",
    "APP_EMBEDDING_BASE_URL",
    "APP_EMBEDDING_MODEL",
}
PLACEHOLDER_MARKERS = ("replace", "example.com", "change-me", "placeholder")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_values(values: dict[str, str]) -> list[str]:
    errors = [f"missing required setting: {key}" for key in sorted(REQUIRED_KEYS - values.keys())]
    for key in sorted(REQUIRED_KEYS & values.keys()):
        value = values[key]
        if not value:
            errors.append(f"{key} must not be empty")
        elif any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{key} still contains a placeholder")

    if values.get("APP_ENV", "").lower() not in {"production", "prod"}:
        errors.append("APP_ENV must be production or prod")
    if values.get("APP_DEBUG", "").lower() not in {"false", "0"}:
        errors.append("APP_DEBUG must be false")
    if values.get("APP_AI_PROVIDER") != "openai_compatible":
        errors.append("APP_AI_PROVIDER must be openai_compatible")
    if values.get("APP_EMBEDDING_PROVIDER") != "openai_compatible":
        errors.append("APP_EMBEDDING_PROVIDER must be openai_compatible")
    if len(values.get("APP_SECRET_KEY", "")) < 32:
        errors.append("APP_SECRET_KEY must contain at least 32 characters")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,}", values.get("POSTGRES_PASSWORD", "")):
        errors.append("POSTGRES_PASSWORD must use 24+ URL-safe characters")
    domain = values.get("DOMAIN", "")
    if domain.startswith(("http://", "https://")) or "." not in domain:
        errors.append("DOMAIN must be a hostname without http:// or https://")
    return errors


def compose_command(docker: str, env_file: Path, *args: str) -> list[str]:
    return [
        docker,
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        str(COMPOSE_FILES[0]),
        "-f",
        str(COMPOSE_FILES[1]),
        *args,
    ]


def validate_compose_model(
    docker: str, env_file: Path, process_env: dict[str, str]
) -> list[str]:
    result = subprocess.run(
        compose_command(docker, env_file, "config", "--format", "json"),
        cwd=ROOT,
        env=process_env,
        check=True,
        capture_output=True,
        text=True,
    )
    services = json.loads(result.stdout)["services"]
    errors: list[str] = []
    for service_name in ("api", "frontend", "postgres", "redis"):
        if services[service_name].get("ports"):
            errors.append(f"production service {service_name} must not publish host ports")
    for service_name in ("api", "worker"):
        if not services[service_name].get("read_only"):
            errors.append(f"production service {service_name} must use a read-only root filesystem")
    caddy_targets = {port["target"] for port in services["caddy"].get("ports", [])}
    if not {80, 443}.issubset(caddy_targets):
        errors.append("Caddy must publish HTTP and HTTPS ports")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.production")
    parser.add_argument("--skip-image-check", action="store_true")
    args = parser.parse_args()
    env_file = args.env_file.resolve()

    if not env_file.is_file():
        print(f"Staging readiness failed: environment file not found: {env_file}")
        return 1
    values = parse_env_file(env_file)
    errors = validate_values(values)
    if errors:
        print("Staging readiness failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    docker = shutil.which("docker")
    if docker is None:
        print("Staging readiness failed: Docker CLI was not found on PATH")
        return 1
    process_env = os.environ | values | {"PRODUCTION_ENV_FILE": str(env_file)}
    compose_errors = validate_compose_model(docker, env_file, process_env)
    if compose_errors:
        print("Staging readiness failed:")
        for error in compose_errors:
            print(f"- {error}")
        return 1
    if not args.skip_image_check:
        image = "interviewplatform-staging-preflight:local"
        subprocess.run(
            [
                docker,
                "build",
                "--tag",
                image,
                str(ROOT / "backend-python"),
            ],
            cwd=ROOT,
            env=process_env,
            check=True,
        )
        process_env["APP_DATABASE_URL"] = (
            "postgresql+asyncpg://postgres:"
            f"{values['POSTGRES_PASSWORD']}@postgres:5432/ai_interview"
        )
        process_env["APP_REDIS_URL"] = "redis://redis:6379/0"
        subprocess.run(
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "--env-file",
                str(env_file),
                "--env",
                "APP_DATABASE_URL",
                "--env",
                "APP_REDIS_URL",
                image,
                "python",
                "scripts/check_production_config.py",
            ],
            cwd=ROOT,
            env=process_env,
            check=True,
        )
    print("Staging readiness check passed without contacting external providers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

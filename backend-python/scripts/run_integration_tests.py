"""Run the PostgreSQL/pgvector/Redis integration-test gate in isolated Docker resources."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_NAME = "interviewplatform-integration"
DOCKER_FALLBACK = Path(
    r"C:\Users\李广威\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
)
DATABASE_URL = (
    "postgresql+asyncpg://postgres:integration-only@"
    "postgres:5432/ai_interview_integration"
)
REDIS_URL = "redis://redis:6379/0"
COMPOSE_FILE = Path(__file__).resolve().parents[2] / "compose.integration.yml"
BACKEND_DIR = Path(__file__).resolve().parents[1]


class IntegrationGateError(RuntimeError):
    """Raised when the integration environment or test gate fails."""


def _docker_executable() -> str:
    on_path = shutil.which("docker")
    if on_path:
        return on_path
    if DOCKER_FALLBACK.is_file():
        return str(DOCKER_FALLBACK)
    raise IntegrationGateError("Docker CLI was not found on PATH or at the Docker Desktop path")


def _compose_command(docker: str, *args: str) -> list[str]:
    return [docker, "compose", "-p", PROJECT_NAME, "-f", str(COMPOSE_FILE), *args]


def _redact(text: str) -> str:
    redacted = re.sub(
        r"(?i)(postgres(?:ql)?(?:\+[^:]+)?://)[^@\s]+@",
        r"\1<redacted>@",
        text,
    )
    redacted = re.sub(r"(?i)(redis://)[^@\s]+@", r"\1<redacted>@", redacted)
    return re.sub(
        r"(?i)(APP_[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD))\s*=\s*[^\s]+",
        r"\1=<redacted>",
        redacted,
    )


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _require_success(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode != 0:
        detail = _redact("\n".join((result.stdout + result.stderr).splitlines()[-5:]))
        raise IntegrationGateError(f"{label} failed (exit {result.returncode})\n{detail}")
    return result.stdout


def _container_statuses(docker: str) -> dict[str, dict[str, Any]]:
    result = _run(_compose_command(docker, "ps", "--format", "json"))
    if result.returncode != 0:
        return {}
    statuses: dict[str, dict[str, Any]] = {}
    raw = result.stdout.strip()
    if not raw:
        return statuses
    entries: list[Any]
    try:
        decoded = json.loads(raw)
        entries = decoded if isinstance(decoded, list) else [decoded]
    except json.JSONDecodeError:
        entries = [json.loads(line) for line in raw.splitlines() if line.strip()]
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("Service"), str):
            statuses[entry["Service"]] = entry
    return statuses


def _wait_for_health(docker: str, timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        statuses = _container_statuses(docker)
        healthy = all(
            statuses.get(service, {}).get("Health") == "healthy"
            for service in ("postgres", "redis")
        )
        if healthy:
            return
        time.sleep(2)
    raise IntegrationGateError("PostgreSQL or Redis did not become healthy before timeout")


def _wait_for_worker(docker: str, timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = _container_statuses(docker).get("worker", {})
        if status.get("Health") == "healthy":
            return
        if status.get("State") == "exited":
            raise IntegrationGateError("Knowledge worker exited before becoming healthy")
        time.sleep(2)
    raise IntegrationGateError("Knowledge worker did not become healthy before timeout")


def _verify_schema(docker: str) -> None:
    sql = """
select version_num from alembic_version;
select exists(select 1 from pg_extension where extname = 'vector');
 select atttypmod
 from pg_attribute
 where attrelid = 'knowledge_chunks'::regclass and attname = 'embedding';
 select exists(
     select 1 from information_schema.tables
     where table_name = 'interview_resume_evaluations'
 );
 select exists(
     select 1 from information_schema.columns
     where table_name = 'interview_reports'
       and column_name = 'resume_evaluation_snapshot'
 );
 select exists(
     select 1 from information_schema.columns
     where table_name = 'interview_reports'
       and column_name = 'generation_lease_expires_at'
 );
 select exists(
     select 1 from pg_constraint
     where conname = 'uq_interview_report_items_report_turn'
 );
"""
    result = _run(
        _compose_command(
            docker,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "postgres",
            "-d",
            "ai_interview_integration",
            "-Atc",
            sql,
        )
    )
    output = _require_success(result, "Schema verification")
    values = [line.strip() for line in output.splitlines() if line.strip()]
    expected = ["0013_interview_report_queue", "t", "1536", "t", "t", "t", "t"]
    if values != expected:
        raise IntegrationGateError(
            f"Schema verification returned unexpected safe values: {values}"
        )
    print(
        "Schema: Alembic 0013, pgvector enabled, embedding dimension 1536, "
        "resume snapshot and report generation fencing present"
    )


def _run_pytest(docker: str, run_number: int) -> str:
    mount_args = [
        "-v",
        f"{BACKEND_DIR / 'app'}:/workspace/app:ro",
        "-v",
        f"{BACKEND_DIR / 'tests'}:/workspace/tests:ro",
        "-v",
        f"{BACKEND_DIR / 'pyproject.toml'}:/workspace/pyproject.toml:ro",
        "-v",
        f"{PROJECT_NAME}_knowledge-storage-integration:/app/storage",
    ]
    command = _compose_command(
        docker,
        "run",
        "--rm",
        "--no-deps",
        *mount_args,
        "-w",
        "/workspace",
        "-e",
        "RUN_INTEGRATION_TESTS=1",
        "-e",
        f"KNOWLEDGE_TEST_DATABASE_URL={DATABASE_URL}",
        "-e",
        f"KNOWLEDGE_TEST_REDIS_URL={REDIS_URL}",
        "-e",
        "APP_ENV=test",
        "-e",
        "APP_AI_PROVIDER=unavailable",
        "-e",
        "APP_EMBEDDING_PROVIDER=fake",
        "-e",
        "APP_KNOWLEDGE_STORAGE_DIR=/app/storage",
        "--entrypoint",
        "/bin/sh",
        "migrate",
        "-c",
        "RUN_INTEGRATION_TESTS=1 python -m pytest --override-ini addopts= -m integration -ra",
    )
    result = _run(command)
    output = _redact(result.stdout + result.stderr)
    if result.returncode != 0:
        detail = "\n".join(output.splitlines()[-12:])
        raise IntegrationGateError(
            f"Integration pytest run {run_number} failed "
            f"(exit {result.returncode})\n{detail}"
        )
    match = re.search(r"(?P<passed>\d+) passed(?:, (?P<skipped>\d+) skipped)?", output)
    if (
        not match
        or int(match.group("passed")) < 9
        or int(match.group("skipped") or 0) != 0
    ):
        raise IntegrationGateError(
            f"Integration pytest run {run_number} did not report 9 passed and 0 skipped"
        )
    summary = (
        f"run {run_number}: {match.group('passed')} passed, "
        f"{match.group('skipped') or 0} skipped"
    )
    print(f"Integration tests {summary}")
    return summary


def main() -> int:
    docker = ""
    try:
        docker = _docker_executable()
        version = _require_success(
            _run([docker, "version", "--format", "{{.Server.Version}}"]), "Docker check"
        ).strip()
        compose_version = _require_success(
            _run([docker, "compose", "version", "--short"]), "Compose check"
        ).strip()
        print(f"Docker Engine: {version}")
        print(f"Docker Compose: {compose_version}")
        _require_success(_run(_compose_command(docker, "config", "--quiet")), "Compose config")
        print("Compose config: valid")

        _require_success(
            _run(_compose_command(docker, "down", "-v", "--remove-orphans")),
            "Pre-run cleanup",
        )
        _require_success(
            _run(_compose_command(docker, "build", "migrate", "worker")),
            "Migration and worker image build",
        )
        _require_success(
            _run(_compose_command(docker, "up", "-d", "postgres", "redis")),
            "Database startup",
        )
        _wait_for_health(docker)
        print("Services: PostgreSQL and Redis healthy")
        _require_success(
            _run(_compose_command(docker, "run", "--rm", "--no-deps", "migrate")),
            "Alembic migration",
        )
        _require_success(
            _run(_compose_command(docker, "up", "-d", "worker")),
            "Worker startup",
        )
        _wait_for_worker(docker)
        print("Worker: healthy")
        _verify_schema(docker)
        _run_pytest(docker, 1)
        _run_pytest(docker, 2)
        print("Integration gate: 2 consecutive runs passed")
        return 0
    except IntegrationGateError as exc:
        print(f"Integration gate FAILED: {_redact(str(exc))}", file=sys.stderr)
        return 1
    finally:
        if docker:
            cleanup = _run(_compose_command(docker, "down", "-v", "--remove-orphans"))
            if cleanup.returncode == 0:
                print("Cleanup: integration containers, network and volumes removed")
            else:
                print(
                    "Cleanup: failed; inspect only the interviewplatform-integration project",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create a PostgreSQL and knowledge-storage backup for the production Compose stack."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = (ROOT / "docker-compose.yml", ROOT / "compose.production.yml")


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.production")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "backups")
    args = parser.parse_args()
    env_file = args.env_file.resolve()
    if not env_file.is_file():
        print(f"Backup failed: environment file not found: {env_file}")
        return 1
    docker = shutil.which("docker")
    if docker is None:
        print("Backup failed: Docker CLI was not found on PATH")
        return 1

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = args.output_dir.resolve() / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    process_env = os.environ | {"PRODUCTION_ENV_FILE": str(env_file)}
    command = compose_command(
        docker,
        env_file,
        "exec",
        "-T",
        "postgres",
        "pg_dump",
        "--username=postgres",
        "--dbname=ai_interview",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
    )
    database_path = backup_dir / "database.dump"
    with database_path.open("wb") as database_file:
        subprocess.run(command, cwd=ROOT, env=process_env, stdout=database_file, check=True)
    subprocess.run(
        compose_command(
            docker,
            env_file,
            "cp",
            "api:/app/storage/.",
            str(backup_dir / "knowledge-storage"),
        ),
        cwd=ROOT,
        env=process_env,
        check=True,
    )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = {
        "createdAt": datetime.now(UTC).isoformat(),
        "gitRevision": revision,
        "database": database_path.name,
        "knowledgeStorage": "knowledge-storage",
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Backup completed: {backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

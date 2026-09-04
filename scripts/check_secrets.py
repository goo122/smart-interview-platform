#!/usr/bin/env python3
"""Fail when tracked repository files contain high-confidence secret signatures."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style API key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "AWS access key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
}
MAX_FILE_BYTES = 2 * 1024 * 1024


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings: list[tuple[Path, str]] = []
    for path in tracked_files(root):
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            content = path.read_bytes()
        except OSError:
            continue
        if b"\0" in content:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append((path.relative_to(root), label))

    if findings:
        print("Potential secrets found in tracked files:")
        for path, label in findings:
            print(f"- {path}: {label}")
        return 1

    print("Tracked-file secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

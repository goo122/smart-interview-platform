import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class StoredFile:
    safe_filename: str
    path: str


class FileStoragePort(Protocol):
    async def save_pdf(self, content: bytes) -> StoredFile:
        raise NotImplementedError

    async def delete(self, path: str) -> None:
        raise NotImplementedError


class LocalFileStorage(FileStoragePort):
    """Store files below a configured directory using generated names only."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_pdf(self, content: bytes) -> StoredFile:
        safe_filename = f"{uuid4().hex}.pdf"
        path = self.root / safe_filename
        await asyncio.to_thread(path.write_bytes, content)
        return StoredFile(safe_filename=safe_filename, path=str(path))

    async def delete(self, path: str) -> None:
        candidate = Path(path).expanduser().resolve()
        if self.root not in candidate.parents:
            return
        try:
            await asyncio.to_thread(candidate.unlink)
        except FileNotFoundError:
            return


class FakeFileStorage(FileStoragePort):
    """In-memory storage double useful for unit and API tests."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def save_pdf(self, content: bytes) -> StoredFile:
        safe_filename = f"{uuid4().hex}.pdf"
        self.files[safe_filename] = content
        return StoredFile(safe_filename=safe_filename, path=f"/fake-storage/{safe_filename}")

    async def delete(self, path: str) -> None:
        safe_filename = Path(path).name
        self.files.pop(safe_filename, None)
        self.deleted.append(path)

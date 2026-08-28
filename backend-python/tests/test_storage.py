from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.infrastructure.storage.files import LocalFileStorage


@pytest.mark.asyncio
async def test_local_file_storage_survives_a_storage_adapter_restart() -> None:
    with TemporaryDirectory(dir=Path.cwd()) as directory:
        storage_root = Path(directory)
        first_storage = LocalFileStorage(str(storage_root))
        stored = await first_storage.save_pdf(b"%PDF-synthetic-e2e")

        restarted_storage = LocalFileStorage(str(storage_root))
        assert Path(stored.path).read_bytes() == b"%PDF-synthetic-e2e"

        await restarted_storage.delete(stored.path)
        assert not Path(stored.path).exists()

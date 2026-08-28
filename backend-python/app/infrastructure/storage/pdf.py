import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from app.modules.knowledge.domain import PdfPage
from app.modules.knowledge.exceptions import InvalidPdfError, UnsupportedPdfError


class PdfParserPort(Protocol):
    async def parse(self, path: str) -> Sequence[PdfPage]: ...


class PypdfPdfParser:
    async def parse(self, path: str) -> Sequence[PdfPage]:
        return await asyncio.to_thread(self._parse_sync, path)

    @staticmethod
    def _parse_sync(path: str) -> Sequence[PdfPage]:
        try:
            reader = PdfReader(Path(path))
        except Exception as exc:
            raise InvalidPdfError("PDF file cannot be parsed") from exc
        if reader.is_encrypted:
            raise UnsupportedPdfError("Encrypted PDF files are not supported")
        pages: list[PdfPage] = []
        try:
            for number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                pages.append(PdfPage(page_number=number, text=text))
        except Exception as exc:
            raise InvalidPdfError("PDF text extraction failed") from exc
        if not any(page.text.strip() for page in pages):
            raise UnsupportedPdfError("PDF contains no extractable text")
        return pages


class FakePdfParser:
    def __init__(
        self, pages: Sequence[PdfPage] | None = None, error: Exception | None = None
    ) -> None:
        self.pages = tuple(pages or (PdfPage(1, "Fake PDF text"),))
        self.error = error
        self.calls = 0

    async def parse(self, path: str) -> Sequence[PdfPage]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.pages

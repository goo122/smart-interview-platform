import hashlib
import re
from collections.abc import Sequence
from typing import Protocol

from app.modules.knowledge.domain import PdfPage, TextChunk


class TextSplitterPort(Protocol):
    def split(self, pages: Sequence[PdfPage]) -> Sequence[TextChunk]: ...


class SimpleTextSplitter:
    """Deterministic page-aware splitter with character-based token approximation."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, pages: Sequence[PdfPage]) -> Sequence[TextChunk]:
        result: list[TextChunk] = []
        for page in pages:
            text = self.clean(page.text)
            if not text:
                continue
            start = 0
            while start < len(text):
                end = min(start + self.chunk_size, len(text))
                if end < len(text):
                    boundary = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
                    if boundary > start + self.chunk_size // 2:
                        end = boundary
                content = text[start:end].strip()
                if content:
                    result.append(
                        TextChunk(
                            chunk_index=len(result),
                            page_number=page.page_number,
                            content=content,
                            token_count=self.estimate_tokens(content),
                            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        )
                    )
                if end >= len(text):
                    break
                next_start = max(end - self.chunk_overlap, start + 1)
                start = next_start
        return result

    @staticmethod
    def clean(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def estimate_tokens(content: str) -> int:
        # This cheap estimate is deliberately replaceable by a tokenizer later.
        return max(1, (len(content) + 3) // 4)

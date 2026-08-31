"""Application service for safe, rate-limited demeanor analysis."""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.ai.demeanor import (
    DEMEANOR_ANALYSIS_VERSION,
    DemeanorAnalysisRequest,
    DemeanorAnalyzerPort,
    StructuredDemeanorEvaluation,
)
from app.core.config import Settings
from app.modules.interview.demeanor_repository import DemeanorEvaluationRepository
from app.modules.interview.domain import (
    InterviewDemeanorEvaluation,
    InterviewSession,
    InterviewStatus,
    utc_now,
)
from app.modules.interview.exceptions import (
    DemeanorAnalysisConflictError,
    DemeanorAnalysisFailedError,
    DemeanorAnalysisRateLimitError,
    DemeanorAnalysisUnavailableError,
    InterviewNotFoundError,
    InvalidDemeanorImageError,
    InvalidInterviewTransitionError,
)
from app.modules.interview.repository import InterviewRepository


class RedisRateLimiter(Protocol):
    async def set(self, *args: Any, **kwargs: Any) -> Any: ...

    async def delete(self, *names: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class DemeanorCapabilities:
    available: bool
    provider: str
    max_image_bytes: int
    max_pixels: int
    min_interval_seconds: float
    analysis_version: str


class DemeanorAnalysisService:
    """Coordinate authorization, validation, provider calls and persistence."""

    def __init__(
        self,
        interview_repository: InterviewRepository,
        repository: DemeanorEvaluationRepository,
        provider: DemeanorAnalyzerPort,
        settings: Settings,
        redis: RedisRateLimiter | None = None,
    ) -> None:
        self._interview_repository = interview_repository
        self._repository = repository
        self._provider = provider
        self._settings = settings
        self._redis = redis
        self._local_lock = asyncio.Lock()
        self._local_in_flight: set[tuple[UUID, UUID]] = set()
        self._local_last_request: dict[tuple[UUID, UUID], float] = {}

    def capabilities(self) -> DemeanorCapabilities:
        provider_name = (
            self._provider.provider_name if self._provider.is_available else "unavailable"
        )
        return DemeanorCapabilities(
            available=self._provider.is_available,
            provider=provider_name,
            max_image_bytes=self._settings.demeanor_analysis_max_image_bytes,
            max_pixels=self._settings.demeanor_analysis_max_pixels,
            min_interval_seconds=self._settings.demeanor_analysis_min_interval_seconds,
            analysis_version=DEMEANOR_ANALYSIS_VERSION,
        )

    @property
    def max_image_bytes(self) -> int:
        return self._settings.demeanor_analysis_max_image_bytes

    async def analyze(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        image_bytes: bytes,
        mime_type: str | None,
    ) -> InterviewDemeanorEvaluation:
        session = await self._interview_repository.get_for_user(session_id, user_id)
        if session is None:
            raise InterviewNotFoundError("Interview session not found")
        self._validate_session(session)
        normalized_mime = self._validate_image(image_bytes, mime_type)
        if not self._provider.is_available:
            raise DemeanorAnalysisUnavailableError(
                "面试仪态分析服务暂时不可用，请稍后重试。"
            )

        lock_key = (user_id, session_id)
        await self._acquire_request_slot(lock_key)
        try:
            try:
                result = await asyncio.wait_for(
                    self._provider.analyze(
                        DemeanorAnalysisRequest(image_bytes=image_bytes, mime_type=normalized_mime)
                    ),
                    timeout=self._settings.demeanor_analysis_request_timeout_seconds,
                )
                validated = StructuredDemeanorEvaluation.model_validate(result)
            except asyncio.CancelledError:
                raise
            except ValidationError as exc:
                raise DemeanorAnalysisFailedError(
                    "面试仪态分析结果无效，请稍后重试。"
                ) from exc
            except TimeoutError as exc:
                raise DemeanorAnalysisUnavailableError(
                    "面试仪态分析服务响应超时，请稍后重试。"
                ) from exc
            except DemeanorAnalysisFailedError:
                raise
            except Exception as exc:
                raise DemeanorAnalysisFailedError(
                    "面试仪态分析失败，请稍后重试。"
                ) from exc
            return await self._repository.create(
                session_id=session_id,
                user_id=user_id,
                overall_score=validated.overall_score,
                eye_contact_score=validated.eye_contact_score,
                posture_score=validated.posture_score,
                facial_visibility_score=validated.facial_visibility_score,
                expression_naturalness_score=validated.expression_naturalness_score,
                summary=validated.summary,
                suggestions=validated.suggestions,
                confidence=validated.confidence,
                provider_name=self._provider.provider_name,
                analysis_version=DEMEANOR_ANALYSIS_VERSION,
                captured_at=utc_now(),
            )
        finally:
            await self._release_request_slot(lock_key)

    async def average_score(self, user_id: UUID, session_id: UUID) -> int | None:
        samples = await self._repository.list_completed(session_id, user_id)
        if not samples:
            return None
        return _round_half_up(sum(item.overall_score for item in samples) / len(samples))

    async def _acquire_request_slot(self, key: tuple[UUID, UUID]) -> None:
        now = time.monotonic()
        async with self._local_lock:
            if key in self._local_in_flight:
                raise DemeanorAnalysisConflictError(
                    "上一条面试仪态分析仍在处理，请稍后再试。"
                )
            last = self._local_last_request.get(key)
            if (
                last is not None
                and now - last < self._settings.demeanor_analysis_min_interval_seconds
            ):
                raise DemeanorAnalysisRateLimitError(
                    "面试仪态分析请求过于频繁，请稍后再试。"
                )
            self._local_in_flight.add(key)
            self._local_last_request[key] = now

        if self._redis is None:
            return
        user_id, session_id = key
        interval = max(1, int(self._settings.demeanor_analysis_min_interval_seconds))
        try:
            acquired = await self._redis.set(
                f"demeanor:rate:{user_id}:{session_id}", uuid4().hex, ex=interval, nx=True
            )
        except Exception:
            await self._release_request_slot(key)
            raise DemeanorAnalysisUnavailableError(
                "面试仪态分析服务暂时不可用，请稍后重试。"
            ) from None
        if not acquired:
            await self._release_request_slot(key)
            raise DemeanorAnalysisRateLimitError(
                "面试仪态分析请求过于频繁，请稍后再试。"
            )
        lock_ttl = max(
            interval + 1,
            int(self._settings.demeanor_analysis_request_timeout_seconds) + interval,
        )
        try:
            locked = await self._redis.set(
                f"demeanor:inflight:{user_id}:{session_id}",
                uuid4().hex,
                ex=lock_ttl,
                nx=True,
            )
        except Exception:
            await self._release_request_slot(key)
            raise DemeanorAnalysisUnavailableError(
                "面试仪态分析服务暂时不可用，请稍后重试。"
            ) from None
        if not locked:
            await self._release_request_slot(key)
            raise DemeanorAnalysisConflictError(
                "上一条面试仪态分析仍在处理，请稍后再试。"
            )

    async def _release_request_slot(self, key: tuple[UUID, UUID]) -> None:
        async with self._local_lock:
            self._local_in_flight.discard(key)
        if self._redis is not None:
            user_id, session_id = key
            with contextlib.suppress(Exception):
                await self._redis.delete(f"demeanor:inflight:{user_id}:{session_id}")

    def _validate_session(self, session: InterviewSession) -> None:
        if session.status != InterviewStatus.IN_PROGRESS:
            raise InvalidInterviewTransitionError(
                "只有进行中的面试可以进行仪态分析。"
            )

    def _validate_image(self, image_bytes: bytes, mime_type: str | None) -> str:
        if not image_bytes:
            raise InvalidDemeanorImageError("请上传有效的摄像头截图。")
        if len(image_bytes) > self._settings.demeanor_analysis_max_image_bytes:
            raise InvalidDemeanorImageError("摄像头截图大小超过限制。")
        normalized_mime = (mime_type or "").strip().lower()
        if normalized_mime not in {"image/jpeg", "image/png"}:
            raise InvalidDemeanorImageError("仅支持 JPEG 或 PNG 摄像头截图。")
        if normalized_mime == "image/jpeg":
            width, height = _jpeg_dimensions(image_bytes)
        else:
            width, height = _png_dimensions(image_bytes)
        if width * height > self._settings.demeanor_analysis_max_pixels:
            raise InvalidDemeanorImageError("摄像头截图像素尺寸超过限制。")
        return normalized_mime


def _jpeg_dimensions(payload: bytes) -> tuple[int, int]:
    if len(payload) < 4 or payload[:3] != b"\xff\xd8\xff" or payload[-2:] != b"\xff\xd9":
        raise InvalidDemeanorImageError("JPEG 文件损坏或格式无效。")
    index = 2
    dimensions: tuple[int, int] | None = None
    saw_start_of_scan = False
    while index < len(payload):
        while index < len(payload) and payload[index] == 0xFF:
            index += 1
        if index >= len(payload):
            break
        marker = payload[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            saw_start_of_scan = True
            break
        if index + 2 > len(payload):
            break
        segment_length = int.from_bytes(payload[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(payload):
            break
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if segment_length < 7:
                break
            height = int.from_bytes(payload[index + 3 : index + 5], "big")
            width = int.from_bytes(payload[index + 5 : index + 7], "big")
            if width > 0 and height > 0:
                dimensions = (width, height)
                index += segment_length
                continue
            break
        index += segment_length
    if dimensions is None or not saw_start_of_scan:
        raise InvalidDemeanorImageError("JPEG 文件损坏或格式无效。")
    return dimensions


def _png_dimensions(payload: bytes) -> tuple[int, int]:
    import zlib

    signature = b"\x89PNG\r\n\x1a\n"
    if len(payload) < len(signature) or payload[:8] != signature:
        raise InvalidDemeanorImageError("PNG 文件损坏或格式无效。")
    index = 8
    dimensions: tuple[int, int] | None = None
    saw_iend = False
    saw_idat = False
    while index < len(payload):
        if index + 12 > len(payload):
            break
        length = int.from_bytes(payload[index : index + 4], "big")
        chunk_start = index + 4
        chunk_end = chunk_start + 4 + length + 4
        if chunk_end > len(payload):
            break
        chunk_type = payload[chunk_start : chunk_start + 4]
        chunk_data = payload[chunk_start + 4 : chunk_start + 4 + length]
        expected_crc = int.from_bytes(payload[chunk_start + 4 + length : chunk_end], "big")
        actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            break
        if chunk_type == b"IHDR":
            if length != 13 or dimensions is not None:
                break
            width = int.from_bytes(chunk_data[:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
            if width <= 0 or height <= 0:
                break
            dimensions = (width, height)
        elif chunk_type == b"IEND":
            if length != 0 or dimensions is None:
                break
            saw_iend = True
            index = chunk_end
            break
        elif chunk_type == b"IDAT":
            saw_idat = True
        index = chunk_end
    if dimensions is None or not saw_idat or not saw_iend or index != len(payload):
        raise InvalidDemeanorImageError("PNG 文件损坏或格式无效。")
    return dimensions


def _round_half_up(value: float) -> int:
    return int(value + 0.5)

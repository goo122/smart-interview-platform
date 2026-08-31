import asyncio
import struct
import zlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.ai.demeanor import (
    FakeDemeanorAnalyzer,
    StructuredDemeanorEvaluation,
)
from app.core.config import Settings
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User
from app.modules.interview.demeanor_service import DemeanorAnalysisService
from app.modules.interview.dependencies import get_demeanor_analysis_service
from app.modules.interview.domain import (
    InterviewDemeanorEvaluation,
    InterviewSession,
    InterviewStatus,
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

JPEG_1X1 = (
    b"\xff\xd8\xff\xc0\x00\x13\x08\x00\x01\x00\x01"
    + b"\x00" * 12
    + b"\xff\xda\x00\x02"
    + b"\xff\xd9"
)


def _png_1x1() -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = b"\x00\xff\x00\x00\xff"
    idat = zlib.compress(raw)

    def chunk(name: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(name + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", checksum)

    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


class FakeInterviewRepository:
    def __init__(self, session: InterviewSession) -> None:
        self.session = session

    async def get_for_user(self, session_id: UUID, user_id: UUID) -> InterviewSession | None:
        if session_id == self.session.id and user_id == self.session.user_id:
            return self.session
        return None


class FakeDemeanorRepository:
    def __init__(self) -> None:
        self.samples: list[InterviewDemeanorEvaluation] = []

    async def create(self, **values: object) -> InterviewDemeanorEvaluation:
        now = datetime.now(UTC)
        sample = InterviewDemeanorEvaluation(
            id=uuid4(),
            session_id=values["session_id"],
            user_id=values["user_id"],
            overall_score=values["overall_score"],
            eye_contact_score=values["eye_contact_score"],
            posture_score=values["posture_score"],
            facial_visibility_score=values["facial_visibility_score"],
            expression_naturalness_score=values["expression_naturalness_score"],
            summary=values["summary"],
            suggestions=list(values["suggestions"]),
            confidence=values["confidence"],
            provider_name=values["provider_name"],
            analysis_version=values["analysis_version"],
            captured_at=values["captured_at"],
            created_at=now,
        )
        self.samples.append(sample)
        return sample

    async def list_completed(
        self, session_id: UUID, user_id: UUID
    ) -> list[InterviewDemeanorEvaluation]:
        return [
            sample
            for sample in self.samples
            if sample.session_id == session_id and sample.user_id == user_id
        ]


def _service(
    provider: object | None = None,
    *,
    status: InterviewStatus = InterviewStatus.IN_PROGRESS,
    min_interval: float = 5,
    timeout: float = 30,
    max_image_bytes: int = 2 * 1024 * 1024,
) -> tuple[DemeanorAnalysisService, FakeDemeanorRepository, UUID, UUID]:
    user_id = uuid4()
    session = InterviewSession.new(
        user_id=user_id,
        knowledge_base_id=uuid4(),
        job_title="后端工程师",
        job_description="负责服务端开发",
        interview_type="TECHNICAL",
        difficulty="MEDIUM",
        question_count=5,
        request_id=None,
    )
    session.status = status
    repository = FakeDemeanorRepository()
    settings = Settings(
        _env_file=None,
        demeanor_analysis_min_interval_seconds=min_interval,
        demeanor_analysis_request_timeout_seconds=timeout,
        demeanor_analysis_max_image_bytes=max_image_bytes,
    )
    service = DemeanorAnalysisService(
        FakeInterviewRepository(session),
        repository,
        provider or FakeDemeanorAnalyzer(),
        settings,
    )
    return service, repository, user_id, session.id


@pytest.mark.asyncio
async def test_valid_jpeg_and_png_are_persisted_without_raw_image() -> None:
    service, repository, user_id, session_id = _service(min_interval=0)

    jpeg_result = await service.analyze(
        user_id=user_id,
        session_id=session_id,
        image_bytes=JPEG_1X1,
        mime_type="image/jpeg",
    )
    png_result = await service.analyze(
        user_id=user_id,
        session_id=session_id,
        image_bytes=_png_1x1(),
        mime_type="image/png",
    )

    assert jpeg_result.overall_score == 82
    assert png_result.overall_score == 82
    assert len(repository.samples) == 2
    assert not any(hasattr(sample, "image_bytes") for sample in repository.samples)


@pytest.mark.asyncio
async def test_invalid_images_and_session_states_are_rejected() -> None:
    service, _, user_id, session_id = _service()
    invalid_images = [
        (b"", "image/jpeg"),
        (b"not-an-image", "image/jpeg"),
        (JPEG_1X1, "image/png"),
        (JPEG_1X1[:-2], "image/jpeg"),
    ]
    for image, mime_type in invalid_images:
        with pytest.raises(InvalidDemeanorImageError):
            await service.analyze(
                user_id=user_id,
                session_id=session_id,
                image_bytes=image,
                mime_type=mime_type,
            )

    not_started, _, other_user, other_session = _service(status=InterviewStatus.READY)
    with pytest.raises(InvalidInterviewTransitionError):
        await not_started.analyze(
            user_id=other_user,
            session_id=other_session,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )

    oversized, _, oversized_user, oversized_session = _service(max_image_bytes=1024)
    with pytest.raises(InvalidDemeanorImageError):
        await oversized.analyze(
            user_id=oversized_user,
            session_id=oversized_session,
            image_bytes=b"x" * 1025,
            mime_type="image/jpeg",
        )


@pytest.mark.asyncio
async def test_session_access_is_scoped_to_the_authenticated_user() -> None:
    service, _, _, session_id = _service()

    with pytest.raises(InterviewNotFoundError):
        await service.analyze(
            user_id=uuid4(),
            session_id=session_id,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )


@pytest.mark.asyncio
async def test_unavailable_provider_does_not_persist_or_fake_a_result() -> None:
    provider = FakeDemeanorAnalyzer(error=RuntimeError("provider unavailable"))
    service, repository, user_id, session_id = _service(provider)

    with pytest.raises(DemeanorAnalysisFailedError):
        await service.analyze(
            user_id=user_id,
            session_id=session_id,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )
    assert repository.samples == []

    unavailable, _, unavailable_user, unavailable_session = _service(
        provider=type("Unavailable", (), {"provider_name": "unavailable", "is_available": False})()
    )
    with pytest.raises(DemeanorAnalysisUnavailableError):
        await unavailable.analyze(
            user_id=unavailable_user,
            session_id=unavailable_session,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )


@pytest.mark.asyncio
async def test_duplicate_requests_are_blocked_while_provider_is_running() -> None:
    provider = FakeDemeanorAnalyzer(delay_seconds=0.05)
    service, _, user_id, session_id = _service(provider, min_interval=0)
    first = asyncio.create_task(
        service.analyze(
            user_id=user_id,
            session_id=session_id,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )
    )
    await asyncio.sleep(0)
    with pytest.raises(DemeanorAnalysisConflictError):
        await service.analyze(
            user_id=user_id,
            session_id=session_id,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )
    await first
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_requests_are_rate_limited_after_a_successful_sample() -> None:
    service, _, user_id, session_id = _service(min_interval=30)

    await service.analyze(
        user_id=user_id,
        session_id=session_id,
        image_bytes=JPEG_1X1,
        mime_type="image/jpeg",
    )
    with pytest.raises(DemeanorAnalysisRateLimitError):
        await service.analyze(
            user_id=user_id,
            session_id=session_id,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )


@pytest.mark.asyncio
async def test_invalid_provider_output_and_timeout_do_not_persist_samples() -> None:
    class InvalidOutputProvider:
        provider_name = "fake"
        is_available = True

        async def analyze(self, _request: object) -> object:
            return {"overallScore": "not-a-score"}

    invalid, invalid_repository, invalid_user, invalid_session = _service(
        provider=InvalidOutputProvider()
    )
    with pytest.raises(DemeanorAnalysisFailedError):
        await invalid.analyze(
            user_id=invalid_user,
            session_id=invalid_session,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )
    assert invalid_repository.samples == []

    timed_out, timeout_repository, timeout_user, timeout_session = _service(
        provider=FakeDemeanorAnalyzer(delay_seconds=0.05), timeout=0.01, min_interval=0
    )
    with pytest.raises(DemeanorAnalysisUnavailableError):
        await timed_out.analyze(
            user_id=timeout_user,
            session_id=timeout_session,
            image_bytes=JPEG_1X1,
            mime_type="image/jpeg",
        )
    assert timeout_repository.samples == []


def test_demeanor_capabilities_and_endpoint_use_structured_response() -> None:
    service, _, user_id, _ = _service()
    user = User(
        id=user_id,
        username="test-user",
        email="test@example.com",
        password_hash="not-used",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_demeanor_analysis_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/xunzhi/v1/interview/demeanor/capabilities")
            assert response.status_code == 200
            assert response.json()["available"] is True
            assert response.json()["analysisVersion"] == "demeanor-v1"
    finally:
        app.dependency_overrides.clear()


def test_demeanor_capabilities_endpoint_requires_authentication() -> None:
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        response = client.get("/api/xunzhi/v1/interview/demeanor/capabilities")
    assert response.status_code == 401


def test_demeanor_provider_output_is_bounded_and_structured() -> None:
    result = StructuredDemeanorEvaluation.model_validate(
        {
            "overallScore": 120,
            "dimensions": {
                "eyeContact": -5,
                "posture": 85,
                "facialVisibility": 90,
                "expressionNaturalness": 76,
            },
            "summary": "稳定",
            "suggestions": ["保持视线接近摄像头"],
            "confidence": 87,
        }
    )
    assert result.overall_score == 100
    assert result.eye_contact_score == 0
    assert 0 <= result.confidence <= 100

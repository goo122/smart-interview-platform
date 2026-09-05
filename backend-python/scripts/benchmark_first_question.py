import argparse
import asyncio
import json
import time
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.modules.interview.domain import (
    AUTO_DETECT_JOB_DESCRIPTION,
    AUTO_DETECT_JOB_TITLE,
)


def synthetic_pdf() -> bytes:
    content = (
        "BT /F1 12 Tf 72 720 Td "
        "(FastAPI Redis PostgreSQL RAG Docker backend project) Tj ET"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf.encode("ascii")))
        pdf += f"{index} 0 obj\n{obj}\nendobj\n"
    xref_offset = len(pdf.encode("ascii"))
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    pdf += "".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    )
    return pdf.encode("ascii")


async def wait_for_document(
    client: httpx.AsyncClient, headers: dict[str, str], base_id: str, document_id: str
) -> None:
    while True:
        response = await client.get(
            f"/api/xunzhi/v1/knowledge-bases/{base_id}/documents",
            headers=headers,
        )
        response.raise_for_status()
        document = next(
            item for item in response.json()["records"] if item["id"] == document_id
        )
        if document["status"] == "FAILED":
            raise RuntimeError(document.get("error_message") or "Document processing failed")
        if document["status"] == "READY":
            return
        await asyncio.sleep(0.05)


async def wait_for_first_question(
    client: httpx.AsyncClient, headers: dict[str, str], session_id: str
) -> float:
    path = f"/api/xunzhi/v1/interview/sessions/{session_id}/events/stream"
    async with client.stream("GET", path, headers=headers) as response:
        response.raise_for_status()
        event = ""
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: ") and event == "question_ready":
                payload = json.loads(line[6:])
                received_at_ms = time.time_ns() // 1_000_000
                return float(max(received_at_ms - int(payload["serverSentAtMs"]), 0))
            elif line.startswith("data: ") and event == "generation_failed":
                raise RuntimeError(json.loads(line[6:]).get("failureMessage"))
    raise RuntimeError("SSE stream ended before the first question was ready")


async def question_count(session_id: str) -> int:
    settings = Settings()
    engine = create_async_engine(str(settings.database_url))
    try:
        async with engine.connect() as connection:
            count = await connection.scalar(
                text("SELECT count(*) FROM interview_questions WHERE session_id = :id"),
                {"id": session_id},
            )
            return int(count or 0)
    finally:
        await engine.dispose()


async def main(base_url: str, auto_job: bool) -> None:
    timeout = httpx.Timeout(180)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        suffix = uuid4().hex[:12]
        username = f"bench_{suffix}"
        password = "Benchmark-Only-123!"
        register = await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": password,
            },
        )
        register.raise_for_status()
        login = await client.post(
            "/api/v1/auth/login",
            json={"account": username, "password": password},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        flow_started = time.perf_counter()
        base = await client.post(
            "/api/xunzhi/v1/knowledge-bases",
            headers=headers,
            json={"name": f"benchmark-{suffix}", "description": "latency benchmark"},
        )
        base.raise_for_status()
        base_id = base.json()["id"]
        upload = await client.post(
            f"/api/xunzhi/v1/knowledge-bases/{base_id}/documents",
            headers=headers,
            files={"file": ("resume.pdf", synthetic_pdf(), "application/pdf")},
        )
        upload.raise_for_status()
        await wait_for_document(client, headers, base_id, upload.json()["id"])
        document_ready_ms = round((time.perf_counter() - flow_started) * 1000, 2)

        session_started = time.perf_counter()
        job_title = AUTO_DETECT_JOB_TITLE if auto_job else "Python 后端工程师"
        job_description = (
            AUTO_DETECT_JOB_DESCRIPTION
            if auto_job
            else "负责 FastAPI、Redis、PostgreSQL 和 RAG 平台开发"
        )
        session = await client.post(
            "/api/xunzhi/v1/interview/sessions",
            headers=headers,
            json={
                "knowledgeBaseId": base_id,
                "jobTitle": job_title,
                "jobDescription": job_description,
                "interviewType": "TECHNICAL",
                "difficulty": "MEDIUM",
                "questionCount": 3,
                "requestId": f"benchmark-{suffix}",
            },
        )
        session.raise_for_status()
        interview_start_response_ms = round(
            (time.perf_counter() - session_started) * 1000, 2
        )
        session_id = session.json()["sessionId"]

        sse_delivery_delay_ms = await wait_for_first_question(client, headers, session_id)
        question_ready_first_ms = round((time.perf_counter() - session_started) * 1000, 2)
        start = await client.post(
            f"/api/xunzhi/v1/interview/sessions/{session_id}/start",
            headers=headers,
            json={},
        )
        start.raise_for_status()
        first_question_visible_ms = round((time.perf_counter() - flow_started) * 1000, 2)

        while await question_count(session_id) < 3:
            await asyncio.sleep(0.1)
        all_questions_ready_ms = round((time.perf_counter() - session_started) * 1000, 2)
        print(
            json.dumps(
                {
                    "interview_start_response_ms": interview_start_response_ms,
                    "resume_processing_visible_ms": document_ready_ms,
                    "question_ready_first_ms": question_ready_first_ms,
                    "sse_delivery_delay_ms": sse_delivery_delay_ms,
                    "first_question_visible_ms": first_question_visible_ms,
                    "all_questions_ready_ms": all_questions_ready_ms,
                    "session_id": session_id,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--auto-job", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(main(arguments.base_url, arguments.auto_job))

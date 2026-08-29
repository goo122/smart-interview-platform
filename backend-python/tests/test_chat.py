import asyncio
import json
from collections.abc import Iterator, Sequence
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.ai.chat import ChatMessage, FakeChatModel
from app.core.exceptions import UserAlreadyExistsError
from app.main import app
from app.modules.auth.dependencies import get_session_store, get_user_repository
from app.modules.auth.domain import User
from app.modules.chat.context import RagContext
from app.modules.chat.dependencies import (
    get_chat_model,
    get_context_provider,
    get_conversation_repository,
    get_message_repository,
)
from app.modules.chat.domain import (
    Conversation,
    ConversationStatus,
    Message,
    MessageCitation,
    MessageRole,
    MessageStatus,
    utc_now,
)
from app.modules.chat.service import CHAT_SYSTEM_PROMPT, ChatService
from app.modules.knowledge.context import ContextCitation


class ChatUserRepository:
    def __init__(self) -> None:
        self.users: list[User] = []

    async def create(self, user: User) -> User:
        if await self.get_by_username(user.username) or await self.get_by_email(user.email):
            raise UserAlreadyExistsError("Username or email already exists")
        self.users.append(user)
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    async def get_by_username(self, username: str) -> User | None:
        return next((user for user in self.users if user.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users if user.email == email), None)


class ChatSessionStore:
    def __init__(self) -> None:
        self.active: dict[UUID, UUID] = {}

    async def save_refresh_session(self, jti: UUID, user_id: UUID, ttl_seconds: int) -> None:
        self.active[jti] = user_id

    async def consume_refresh_session(self, jti: UUID) -> UUID | None:
        return self.active.pop(jti, None)

    async def revoke_refresh_session(self, jti: UUID, ttl_seconds: int) -> None:
        self.active.pop(jti, None)


class FakeConversationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Conversation] = {}

    async def create(self, conversation: Conversation) -> Conversation:
        self.items[conversation.id] = conversation
        return conversation

    async def list_for_user(
        self,
        user_id: UUID,
        current: int,
        size: int,
        ai_id: int | None = None,
        status: int | None = None,
        title: str | None = None,
    ) -> tuple[list[Conversation], int]:
        values = [item for item in self.items.values() if item.user_id == user_id]
        if status is not None:
            expected = ConversationStatus.ACTIVE if status == 1 else ConversationStatus.FINISHED
            values = [item for item in values if item.status == expected]
        if title:
            values = [item for item in values if title.lower() in item.title.lower()]
        values.sort(key=lambda item: item.updated_at, reverse=True)
        start = (current - 1) * size
        return values[start : start + size], len(values)

    async def get_for_user(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        item = self.items.get(conversation_id)
        return item if item and item.user_id == user_id else None

    async def finish(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        item = await self.get_for_user(conversation_id, user_id)
        if item is not None:
            item.status = ConversationStatus.FINISHED
            item.finished_at = utc_now()
            item.updated_at = item.finished_at
        return item

    async def delete_for_user(self, conversation_id: UUID, user_id: UUID) -> bool:
        item = await self.get_for_user(conversation_id, user_id)
        if item is None:
            return False
        del self.items[conversation_id]
        return True


class FakeMessageRepository:
    def __init__(self) -> None:
        self.items: list[Message] = []

    async def create(self, message: Message) -> Message:
        self.items.append(message)
        return message

    async def list_for_conversation(self, conversation_id: UUID) -> list[Message]:
        return sorted(
            [item for item in self.items if item.conversation_id == conversation_id],
            key=lambda item: item.sequence,
        )

    async def next_sequence(self, conversation_id: UUID) -> int:
        values = await self.list_for_conversation(conversation_id)
        return max((item.sequence for item in values), default=0) + 1

    async def get_user_message_by_request(
        self, conversation_id: UUID, request_id: str
    ) -> Message | None:
        return next(
            (
                item
                for item in self.items
                if item.conversation_id == conversation_id
                and item.request_id == request_id
                and item.role == MessageRole.USER
            ),
            None,
        )

    async def get_assistant_message_by_request(
        self, conversation_id: UUID, request_id: str
    ) -> Message | None:
        return next(
            (
                item
                for item in self.items
                if item.conversation_id == conversation_id
                and item.request_id == request_id
                and item.role == MessageRole.ASSISTANT
            ),
            None,
        )

    async def update(
        self,
        message_id: UUID,
        status: MessageStatus,
        content: str,
        error_message: str | None = None,
    ) -> Message:
        item = next(item for item in self.items if item.id == message_id)
        item.status = status
        item.content = content
        item.error_message = error_message
        item.completed_at = utc_now() if status != MessageStatus.PENDING else None
        return item

    async def complete_with_citations(
        self, message_id: UUID, content: str, citations: Sequence[ContextCitation]
    ) -> Message:
        item = await self.update(message_id, MessageStatus.COMPLETED, content)
        item.citations = [
            MessageCitation(
                id=UUID("00000000-0000-0000-0000-000000000012"),
                message_id=message_id,
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                source_id=citation.source_id,
                page_number=citation.page_number,
                score=citation.score,
                excerpt=citation.excerpt,
                ordinal=citation.ordinal,
                created_at=item.created_at,
                document_name=citation.document_name,
            )
            for citation in citations
        ]
        return item


class FakeRagContextProvider:
    async def validate_knowledge_base(self, _user_id: UUID, _knowledge_base_id: UUID) -> None:
        return None

    async def build(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        query: str,
        top_k: int | None,
        similarity_threshold: float | None,
    ) -> RagContext:
        del user_id, knowledge_base_id, query, top_k, similarity_threshold
        citation = ContextCitation(
            source_id="[S1]",
            chunk_id=UUID("00000000-0000-0000-0000-000000000010"),
            document_id=UUID("00000000-0000-0000-0000-000000000011"),
            document_name="resume.pdf",
            page_number=2,
            score=0.91,
            excerpt="Python experience",
            ordinal=0,
        )
        return RagContext("参考资料", (citation,))


@pytest.fixture
def chat_client() -> Iterator[
    tuple[
        TestClient,
        ChatUserRepository,
        FakeConversationRepository,
        FakeMessageRepository,
        FakeChatModel,
    ]
]:
    users = ChatUserRepository()
    sessions = ChatSessionStore()
    conversations = FakeConversationRepository()
    messages = FakeMessageRepository()
    model = FakeChatModel(chunks=("Hello", " world"))
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_session_store] = lambda: sessions
    app.dependency_overrides[get_conversation_repository] = lambda: conversations
    app.dependency_overrides[get_message_repository] = lambda: messages
    app.dependency_overrides[get_chat_model] = lambda: model
    with TestClient(app) as client:
        yield client, users, conversations, messages, model
    app.dependency_overrides.clear()


def _register_and_login(client: TestClient, *, username: str, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "secure-password"},
    )
    assert response.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"account": email, "password": "secure-password"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _create(client: TestClient, token: str, title: str = "My chat") -> str:
    response = client.post(
        "/api/xunzhi/v1/ai/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title},
    )
    assert response.status_code == 201
    return response.json()["sessionId"]


def test_create_and_page_are_user_scoped(chat_client) -> None:
    client, users, conversations, _, _ = chat_client
    first = _register_and_login(client, username="one", email="one@example.com")
    second = _register_and_login(client, username="two", email="two@example.com")
    session_id = _create(client, first)
    _create(client, second, "Other")

    listed = client.get(
        "/api/xunzhi/v1/ai/conversations?current=1&size=10",
        headers={"Authorization": f"Bearer {first}"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["records"][0]["sessionId"] == session_id
    assert len(conversations.items) == len(users.users)


def test_other_user_cannot_view_or_delete_conversation(chat_client) -> None:
    client, _, _, _, _ = chat_client
    owner = _register_and_login(client, username="owner", email="owner@example.com")
    other = _register_and_login(client, username="other", email="other@example.com")
    session_id = _create(client, owner)

    view = client.get(
        f"/api/xunzhi/v1/ai/conversations/{session_id}",
        headers={"Authorization": f"Bearer {other}"},
    )
    delete = client.delete(
        f"/api/xunzhi/v1/ai/conversations/{session_id}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert view.status_code == delete.status_code == 404


def test_finished_conversation_cannot_receive_message(chat_client) -> None:
    client, _, _, _, _ = chat_client
    token = _register_and_login(client, username="finish", email="finish@example.com")
    session_id = _create(client, token)
    ended = client.post(
        f"/api/xunzhi/v1/ai/conversations/{session_id}/end",
        headers={"Authorization": f"Bearer {token}"},
    )
    response = client.post(
        f"/api/xunzhi/v1/ai/sessions/{session_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"inputMessage": "hello"},
    )
    assert ended.status_code == 200
    assert response.status_code == 409


def test_sse_persists_messages_and_emits_ordered_events(chat_client) -> None:
    client, _, _, messages, model = chat_client
    token = _register_and_login(client, username="stream", email="stream@example.com")
    session_id = _create(client, token)
    response = client.post(
        f"/api/xunzhi/v1/ai/sessions/{session_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"inputMessage": "Hi", "requestId": "r-1"},
    )
    event_names = [
        line.removeprefix("event: ")
        for line in response.text.splitlines()
        if line.startswith("event:")
    ]
    assert response.status_code == 200
    assert event_names == ["start", "delta", "delta", "complete"]
    assert response.headers["content-type"].startswith("text/event-stream")
    assert model.calls == 1
    assert [item.role for item in messages.items] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert messages.items[1].status == MessageStatus.COMPLETED
    assert messages.items[1].content == "Hello world"
    assert model.received_messages[0][0] == ChatMessage(role="system", content=CHAT_SYSTEM_PROMPT)
    assert "寻知面试小助手" in model.received_messages[0][0].content
    assert "不要自称通义千问" in model.received_messages[0][0].content


def test_rag_sse_returns_citations_and_adds_context(chat_client) -> None:
    client, _, _, _, model = chat_client
    app.dependency_overrides[get_context_provider] = lambda: FakeRagContextProvider()
    token = _register_and_login(client, username="rag-http", email="rag-http@example.com")
    session_id = _create(client, token)

    response = client.post(
        f"/api/xunzhi/v1/ai/sessions/{session_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "inputMessage": "请分析项目经验",
            "knowledgeBaseId": str(UUID("00000000-0000-0000-0000-000000000001")),
            "topK": 2,
        },
    )
    complete_line = next(
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data:") and "citations" in line
    )
    complete = json.loads(complete_line)

    assert response.status_code == 200
    assert complete["citations"][0]["source_id"] == "[S1]"
    assert complete["citations"][0]["document_name"] == "resume.pdf"
    assert model.received_messages[0][0].role == "system"


def test_model_error_is_safe_and_marks_assistant_failed(chat_client) -> None:
    client, _, _, messages, model = chat_client
    model.error = RuntimeError("secret-provider-key")
    token = _register_and_login(client, username="failure", email="failure@example.com")
    session_id = _create(client, token)
    response = client.post(
        f"/api/xunzhi/v1/ai/sessions/{session_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"inputMessage": "Hi"},
    )
    assert response.status_code == 200
    assert "secret-provider-key" not in response.text
    assert 'event: error' in response.text
    assert messages.items[-1].status == MessageStatus.FAILED


def test_duplicate_request_id_is_replayed_without_second_generation(chat_client) -> None:
    client, _, _, messages, model = chat_client
    token = _register_and_login(client, username="repeat", email="repeat@example.com")
    session_id = _create(client, token)
    body = {"inputMessage": "same", "requestId": "stable-id"}
    first = client.post(
        f"/api/xunzhi/v1/ai/sessions/{session_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    second = client.post(
        f"/api/xunzhi/v1/ai/sessions/{session_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert first.status_code == second.status_code == 200
    assert model.calls == 1
    assert len(messages.items) == 2


def test_history_is_sorted_and_me_requires_authentication(chat_client) -> None:
    client, _, _, _, _ = chat_client
    assert client.get("/api/xunzhi/v1/ai/conversations").status_code == 401
    token = _register_and_login(client, username="history", email="history@example.com")
    session_id = _create(client, token)
    client.post(
        f"/api/xunzhi/v1/ai/sessions/{session_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"inputMessage": "ordered"},
    )
    response = client.get(
        f"/api/xunzhi/v1/ai/history/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.json()
    assert [item["messageSeq"] for item in body] == [1, 2]
    assert all("password_hash" not in item for item in body)
    page = client.get(
        f"/api/xunzhi/v1/ai/history/page?sessionId={session_id}&current=1&size=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert len(page.json()["records"]) == 1


@pytest.mark.asyncio
async def test_client_cancellation_cancels_fake_model() -> None:
    conversation_repository = FakeConversationRepository()
    message_repository = FakeMessageRepository()
    model = FakeChatModel(chunks=("late",), delay_seconds=10)
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    conversation = await conversation_repository.create(Conversation.new(user_id, "cancel"))
    service = ChatService(conversation_repository, message_repository, model)
    events = await service.stream_chat(user_id, conversation.id, "hello")
    await anext(events)
    task = asyncio.create_task(anext(events))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert model.cancelled is True
    assert message_repository.items[-1].status == MessageStatus.FAILED

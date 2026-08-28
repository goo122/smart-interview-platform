import asyncio
import inspect
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from app.ai.chat import ChatMessage, ChatModelPort
from app.core.exceptions import (
    ConversationFinishedError,
    ConversationNotFoundError,
    InvalidChatRequestError,
)
from app.modules.chat.domain import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    MessageStatus,
)
from app.modules.chat.repository import ConversationRepository, MessageRepository


@dataclass(frozen=True, slots=True)
class ChatEvent:
    event: str
    data: dict[str, Any]


class ChatService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        chat_model: ChatModelPort,
    ) -> None:
        self._conversations = conversation_repository
        self._messages = message_repository
        self._model = chat_model

    async def create_conversation(
        self,
        user_id: UUID,
        title: str | None = None,
        first_message: str | None = None,
        model_name: str | None = None,
    ) -> Conversation:
        chosen_title = (title or "").strip() or self._title_from_message(first_message)
        return await self._conversations.create(
            Conversation.new(user_id=user_id, title=chosen_title[:200], model_name=model_name)
        )

    async def list_conversations(
        self,
        user_id: UUID,
        current: int = 1,
        size: int = 10,
        ai_id: int | None = None,
        status: int | None = None,
        title: str | None = None,
    ) -> tuple[list[Conversation], int]:
        current = max(current, 1)
        size = min(max(size, 1), 100)
        return await self._conversations.list_for_user(user_id, current, size, ai_id, status, title)

    async def get_conversation(self, user_id: UUID, conversation_id: UUID) -> Conversation:
        conversation = await self._conversations.get_for_user(conversation_id, user_id)
        if conversation is None:
            raise ConversationNotFoundError("Conversation not found")
        return conversation

    async def finish_conversation(self, user_id: UUID, conversation_id: UUID) -> Conversation:
        conversation = await self._conversations.finish(conversation_id, user_id)
        if conversation is None:
            raise ConversationNotFoundError("Conversation not found")
        return conversation

    async def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> None:
        deleted = await self._conversations.delete_for_user(conversation_id, user_id)
        if not deleted:
            raise ConversationNotFoundError("Conversation not found")

    async def list_messages(self, user_id: UUID, conversation_id: UUID) -> list[Message]:
        await self.get_conversation(user_id, conversation_id)
        return await self._messages.list_for_conversation(conversation_id)

    async def stream_chat(
        self,
        user_id: UUID,
        conversation_id: UUID,
        content: str,
        request_id: str | None = None,
    ) -> AsyncIterator[ChatEvent]:
        """Prepare a persisted request and return an async event stream.

        Preparation happens before the StreamingResponse is created so ownership and
        conversation-state errors retain normal HTTP status codes.
        """

        conversation = await self.get_conversation(user_id, conversation_id)
        if conversation.status != ConversationStatus.ACTIVE:
            raise ConversationFinishedError("Conversation has already ended")
        text = content.strip()
        if not text:
            raise InvalidChatRequestError("Message content is required")

        request_key = request_id or str(uuid4())
        existing_user = await self._messages.get_user_message_by_request(
            conversation_id, request_key
        )
        if existing_user is not None:
            existing_assistant = await self._messages.get_assistant_message_by_request(
                conversation_id, request_key
            )
            return self._replay(existing_user, existing_assistant)

        sequence = await self._messages.next_sequence(conversation_id)
        user_message = await self._messages.create(
            Message.new(
                conversation_id,
                MessageRole.USER,
                text,
                sequence,
                request_id=request_key,
            )
        )
        assistant_message = await self._messages.create(
            Message.new(
                conversation_id,
                MessageRole.ASSISTANT,
                "",
                sequence + 1,
                request_id=request_key,
                status=MessageStatus.PENDING,
            )
        )
        history = await self._messages.list_for_conversation(conversation_id)
        return self._generate(history, user_message, assistant_message)

    async def _generate(
        self,
        history: list[Message],
        user_message: Message,
        assistant_message: Message,
    ) -> AsyncIterator[ChatEvent]:
        messages = [
            ChatMessage(role=message.role.value.lower(), content=message.content)
            for message in history
            if message.content and message.status != MessageStatus.FAILED
        ]
        yield ChatEvent(
            "start",
            {
                "conversation_id": str(user_message.conversation_id),
                "message_id": str(assistant_message.id),
            },
        )
        parts: list[str] = []
        stream: AsyncIterator[Any] | None = None
        try:
            stream = self._model.stream(messages)
            async for chunk in stream:
                value = getattr(chunk, "content", chunk)
                if not isinstance(value, str) or not value:
                    continue
                parts.append(value)
                yield ChatEvent("delta", {"content": value})
            complete = "".join(parts)
            await self._messages.update(
                assistant_message.id, MessageStatus.COMPLETED, complete
            )
            yield ChatEvent(
                "complete", {"message_id": str(assistant_message.id), "content": complete}
            )
        except asyncio.CancelledError:
            await self._messages.update(
                assistant_message.id,
                MessageStatus.FAILED,
                "".join(parts),
                error_message="AI response cancelled",
            )
            raise
        except Exception:
            await self._messages.update(
                assistant_message.id,
                MessageStatus.FAILED,
                "".join(parts),
                error_message="AI response failed",
            )
            yield ChatEvent(
                "error",
                {"code": "AI_GENERATION_FAILED", "message": "AI 回复失败"},
            )
        finally:
            if stream is not None:
                close = getattr(stream, "aclose", None)
                if close is not None:
                    result = close()
                    if inspect.isawaitable(result):
                        await result

    async def _replay(
        self, user_message: Message, assistant_message: Message | None
    ) -> AsyncIterator[ChatEvent]:
        message_id = str(assistant_message.id) if assistant_message else ""
        yield ChatEvent(
            "start",
            {"conversation_id": str(user_message.conversation_id), "message_id": message_id},
        )
        if assistant_message is None:
            yield ChatEvent("complete", {"message_id": message_id, "content": ""})
            return
        if assistant_message.status == MessageStatus.FAILED:
            yield ChatEvent(
                "error",
                {"code": "AI_GENERATION_FAILED", "message": "AI 回复失败"},
            )
            return
        if assistant_message.content:
            yield ChatEvent("delta", {"content": assistant_message.content})
        yield ChatEvent(
            "complete",
            {"message_id": str(assistant_message.id), "content": assistant_message.content},
        )

    @staticmethod
    def _title_from_message(first_message: str | None) -> str:
        text = (first_message or "").strip()
        return text[:80] or "New conversation"

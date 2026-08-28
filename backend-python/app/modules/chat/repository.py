from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.domain import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    MessageStatus,
    utc_now,
)
from app.modules.chat.models import ConversationModel, MessageModel


class ConversationRepository(Protocol):
    async def create(self, conversation: Conversation) -> Conversation: ...

    async def list_for_user(
        self,
        user_id: UUID,
        current: int,
        size: int,
        ai_id: int | None = None,
        status: int | None = None,
        title: str | None = None,
    ) -> tuple[list[Conversation], int]: ...

    async def get_for_user(self, conversation_id: UUID, user_id: UUID) -> Conversation | None: ...

    async def finish(self, conversation_id: UUID, user_id: UUID) -> Conversation | None: ...

    async def delete_for_user(self, conversation_id: UUID, user_id: UUID) -> bool: ...


class MessageRepository(Protocol):
    async def create(self, message: Message) -> Message: ...

    async def list_for_conversation(self, conversation_id: UUID) -> list[Message]: ...

    async def next_sequence(self, conversation_id: UUID) -> int: ...

    async def get_user_message_by_request(
        self, conversation_id: UUID, request_id: str
    ) -> Message | None: ...

    async def get_assistant_message_by_request(
        self, conversation_id: UUID, request_id: str
    ) -> Message | None: ...

    async def update(
        self,
        message_id: UUID,
        status: MessageStatus,
        content: str,
        error_message: str | None = None,
    ) -> Message: ...


class SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation: Conversation) -> Conversation:
        row = ConversationModel(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            status=conversation.status.value,
            model_name=conversation.model_name,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            finished_at=conversation.finished_at,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _conversation_to_domain(row)

    async def list_for_user(
        self,
        user_id: UUID,
        current: int,
        size: int,
        ai_id: int | None = None,
        status: int | None = None,
        title: str | None = None,
    ) -> tuple[list[Conversation], int]:
        query = select(ConversationModel).where(ConversationModel.user_id == user_id)
        if status is not None:
            query = query.where(
                ConversationModel.status == ("ACTIVE" if status == 1 else "FINISHED")
            )
        if title:
            query = query.where(ConversationModel.title.ilike(f"%{title}%"))
        count = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        result = await self._session.execute(
            query.order_by(ConversationModel.updated_at.desc())
            .offset((current - 1) * size)
            .limit(size)
        )
        return [_conversation_to_domain(row) for row in result.scalars().all()], int(count or 0)

    async def get_for_user(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        result = await self._session.execute(
            select(ConversationModel).where(
                ConversationModel.id == conversation_id,
                ConversationModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _conversation_to_domain(row) if row is not None else None

    async def finish(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        row = await self._get_row(conversation_id, user_id)
        if row is None:
            return None
        if row.status == ConversationStatus.ACTIVE.value:
            row.status = ConversationStatus.FINISHED.value
            row.finished_at = utc_now()
            row.updated_at = row.finished_at
            await self._session.commit()
            await self._session.refresh(row)
        return _conversation_to_domain(row)

    async def delete_for_user(self, conversation_id: UUID, user_id: UUID) -> bool:
        row = await self._get_row(conversation_id, user_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True

    async def _get_row(self, conversation_id: UUID, user_id: UUID) -> ConversationModel | None:
        result = await self._session.execute(
            select(ConversationModel).where(
                ConversationModel.id == conversation_id,
                ConversationModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


class SqlAlchemyMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, message: Message) -> Message:
        row = MessageModel(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role.value,
            content=message.content,
            status=message.status.value,
            sequence=message.sequence,
            request_id=message.request_id,
            error_message=message.error_message,
            created_at=message.created_at,
            completed_at=message.completed_at,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _message_to_domain(row)

    async def list_for_conversation(self, conversation_id: UUID) -> list[Message]:
        result = await self._session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.sequence.asc())
        )
        return [_message_to_domain(row) for row in result.scalars().all()]

    async def next_sequence(self, conversation_id: UUID) -> int:
        maximum = await self._session.scalar(
            select(func.max(MessageModel.sequence)).where(
                MessageModel.conversation_id == conversation_id
            )
        )
        return int(maximum or 0) + 1

    async def get_user_message_by_request(
        self, conversation_id: UUID, request_id: str
    ) -> Message | None:
        result = await self._session.execute(
            select(MessageModel).where(
                MessageModel.conversation_id == conversation_id,
                MessageModel.request_id == request_id,
                MessageModel.role == MessageRole.USER.value,
            )
        )
        row = result.scalar_one_or_none()
        return _message_to_domain(row) if row is not None else None

    async def get_assistant_message_by_request(
        self, conversation_id: UUID, request_id: str
    ) -> Message | None:
        result = await self._session.execute(
            select(MessageModel).where(
                MessageModel.conversation_id == conversation_id,
                MessageModel.request_id == request_id,
                MessageModel.role == MessageRole.ASSISTANT.value,
            )
        )
        row = result.scalar_one_or_none()
        return _message_to_domain(row) if row is not None else None

    async def update(
        self,
        message_id: UUID,
        status: MessageStatus,
        content: str,
        error_message: str | None = None,
    ) -> Message:
        values: dict[str, object] = {
            "status": status.value,
            "content": content,
            "error_message": error_message,
            "completed_at": utc_now() if status != MessageStatus.PENDING else None,
        }
        await self._session.execute(
            update(MessageModel).where(MessageModel.id == message_id).values(**values)
        )
        await self._session.commit()
        result = await self._session.execute(
            select(MessageModel).where(MessageModel.id == message_id)
        )
        row = result.scalar_one()
        return _message_to_domain(row)


def _conversation_to_domain(row: ConversationModel) -> Conversation:
    return Conversation(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        status=ConversationStatus(row.status),
        model_name=row.model_name,
        created_at=row.created_at,
        updated_at=row.updated_at,
        finished_at=row.finished_at,
    )


def _message_to_domain(row: MessageModel) -> Message:
    return Message(
        id=row.id,
        conversation_id=row.conversation_id,
        role=MessageRole(row.role),
        content=row.content,
        status=MessageStatus(row.status),
        sequence=row.sequence,
        request_id=row.request_id,
        error_message=row.error_message,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )

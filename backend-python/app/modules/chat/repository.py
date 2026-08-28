from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.domain import (
    Conversation,
    ConversationStatus,
    Message,
    MessageCitation,
    MessageRole,
    MessageStatus,
    utc_now,
)
from app.modules.chat.models import ConversationModel, MessageCitationModel, MessageModel
from app.modules.knowledge.context import ContextCitation
from app.modules.knowledge.models import KnowledgeDocumentModel


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

    async def complete_with_citations(
        self, message_id: UUID, content: str, citations: Sequence[ContextCitation]
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
        rows = result.scalars().all()
        messages = [_message_to_domain(row) for row in rows]
        if messages:
            citation_result = await self._session.execute(
                select(MessageCitationModel, KnowledgeDocumentModel.original_filename)
                .join(
                    KnowledgeDocumentModel,
                    KnowledgeDocumentModel.id == MessageCitationModel.document_id,
                    isouter=True,
                )
                .where(MessageCitationModel.message_id.in_([message.id for message in messages]))
                .order_by(MessageCitationModel.message_id, MessageCitationModel.ordinal)
            )
            by_message: dict[UUID, list[MessageCitation]] = {}
            for row, document_name in citation_result.all():
                by_message.setdefault(row.message_id, []).append(
                    _citation_to_domain(row, document_name or "")
                )
            for message in messages:
                message.citations = by_message.get(message.id, [])
        return messages

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
        if row is None:
            return None
        message = _message_to_domain(row)
        message.citations = await self.list_citations(message.id)
        return message

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
        if row is None:
            return None
        message = _message_to_domain(row)
        message.citations = await self.list_citations(message.id)
        return message

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
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        result = await self._session.execute(
            select(MessageModel).where(MessageModel.id == message_id)
        )
        row = result.scalar_one()
        return _message_to_domain(row)

    async def complete_with_citations(
        self, message_id: UUID, content: str, citations: Sequence[ContextCitation]
    ) -> Message:
        completed_at = utc_now()
        await self._session.execute(
            update(MessageModel)
            .where(MessageModel.id == message_id)
            .values(
                status=MessageStatus.COMPLETED.value,
                content=content,
                error_message=None,
                completed_at=completed_at,
            )
        )
        self._session.add_all(
            MessageCitationModel(
                message_id=message_id,
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                source_id=citation.source_id,
                page_number=citation.page_number,
                score=citation.score,
                excerpt=citation.excerpt,
                ordinal=citation.ordinal,
            )
            for citation in citations
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        result = await self._session.execute(
            select(MessageModel).where(MessageModel.id == message_id)
        )
        row = result.scalar_one()
        message = _message_to_domain(row)
        message.citations = [
            _citation_to_domain(row, document_name or "")
            for row, document_name in (
                await self._session.execute(
                    select(MessageCitationModel, KnowledgeDocumentModel.original_filename)
                    .join(
                        KnowledgeDocumentModel,
                        KnowledgeDocumentModel.id == MessageCitationModel.document_id,
                        isouter=True,
                    )
                    .where(MessageCitationModel.message_id == message_id)
                    .order_by(MessageCitationModel.ordinal)
                )
            ).all()
        ]
        return message

    async def list_citations(self, message_id: UUID) -> list[MessageCitation]:
        result = await self._session.execute(
            select(MessageCitationModel, KnowledgeDocumentModel.original_filename)
            .join(
                KnowledgeDocumentModel,
                KnowledgeDocumentModel.id == MessageCitationModel.document_id,
                isouter=True,
            )
            .where(MessageCitationModel.message_id == message_id)
            .order_by(MessageCitationModel.ordinal)
        )
        return [_citation_to_domain(row, name or "") for row, name in result.all()]


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


def _citation_to_domain(row: MessageCitationModel, document_name: str = "") -> MessageCitation:
    return MessageCitation(
        id=row.id,
        message_id=row.message_id,
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        source_id=row.source_id,
        page_number=row.page_number,
        score=float(row.score),
        excerpt=row.excerpt,
        ordinal=row.ordinal,
        created_at=row.created_at,
        document_name=document_name,
    )

"""All DB models related to chatbot services"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import String, Enum, select, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils.logger import logger
from api.database.db import Base


class RoleTypes(StrEnum):
    SYSTEM = "system"
    AI = "ai"
    HUMAN = "human"
    TOOL = "tool"


class Chat(Base):
    """Chats table to save all chats with AI"""

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True
    )
    role_type: Mapped[str] = mapped_column(Enum(RoleTypes), nullable=False)
    content: Mapped[str] = mapped_column(String(2048), nullable=False)
    created: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated: Mapped[datetime] = mapped_column(
        insert_default=func.now(), onupdate=func.now()
    )

    @classmethod
    async def create(cls, db: AsyncSession, **kwargs):
        try:
            new_chat = cls(**kwargs)
            db.add(new_chat)
            await db.commit()
            await db.refresh(new_chat)
            return new_chat
        except Exception as e:
            logger.exception(f"Failed to insert chat: {e}")
            raise e

    @classmethod
    async def find_by_userid(cls, db: AsyncSession, user_id: int):
        results = await db.scalars(select(cls).where(cls.user_id == user_id))
        return results.all()

    @classmethod
    async def find_recent_human_records(
        cls, db: AsyncSession, user_id: int, limit: int
    ):
        results = await db.scalars(
            select(cls)
            .where(cls.user_id == user_id, cls.role_type == RoleTypes.HUMAN)
            .order_by(cls.created.desc())
            .limit(limit)
        )
        return results.all()

    @classmethod
    async def find_recent_chat_history(
        cls, db: AsyncSession, user_id: int, limit: int
    ):
        query = await db.scalars(
            select(cls)
            .where(cls.user_id == user_id)
            .order_by(cls.created.desc())
            .limit(limit)
        )
        chat_records = query.all()
        chat_history = {}
        if not chat_records:
            return chat_history
        # If loaded last record is from AI (means answer only), discard it as we need a pair of chat messages
        while chat_records[-1].role_type == "ai":
            chat_records.pop()
        chat_records.sort(key=lambda x: x.created)

        index = 0
        while index < len(chat_records):
            human_message = chat_records[index].content
            ai_message = ""
            index += 1
            if (
                index < len(chat_records)
                and chat_records[index].role_type == "ai"
            ):
                ai_message = chat_records[index].content
                index += 1
            chat_history[human_message] = ai_message
            # discard answer without question, normally this should not happen
            while (
                index < len(chat_records)
                and chat_records[index].role_type == "ai"
            ):
                index += 1

        return chat_history


class IngestedFile(Base):
    """ingested_files table to save all ingested files for vector database"""

    __tablename__ = "ingested_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    created: Mapped[datetime] = mapped_column(insert_default=func.now())

    @classmethod
    async def create(cls, db: AsyncSession, **kwargs):
        try:
            new_record = cls(**kwargs)
            db.add(new_record)
            await db.commit()
            await db.refresh(new_record)
            return new_record
        except Exception as e:
            logger.exception(
                f"Failed to insert new record in ingested_files table: {e}"
            )
            raise e

    @classmethod
    async def find_by_file_hash(cls, db: AsyncSession, file_hash: str):
        query = await db.execute(select(cls).where(cls.file_hash == file_hash))
        return query.scalars().all()

"""All DB models related to user management"""

from enum import StrEnum
from datetime import datetime

from sqlalchemy import String, select, Enum
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database.db import Base
from api.utils.logger import logger


class Roles(StrEnum):
    """User roles enum"""

    ADMIN = "ADMIN"
    EMPLOYEE = "EMPLOYEE"


class User(Base):
    """Users table"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(Enum(Roles), nullable=False)
    created: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated: Mapped[datetime] = mapped_column(
        insert_default=func.now(), onupdate=func.now()
    )

    @classmethod
    async def create(cls, db: AsyncSession, **kwargs):
        try:
            user = cls(**kwargs)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            logger.exception(f"Failed to insert user: {e}")
            raise e

    @classmethod
    async def find_all(cls, db: AsyncSession):
        results = await db.scalars(select(cls))
        return results.all()

    @classmethod
    async def find_by_id(cls, db: AsyncSession, id: int):
        user = await db.get(cls, id)
        return user

    @classmethod
    async def find_by_name(cls, db: AsyncSession, name: str):
        results = await db.scalars(select(cls).where(cls.username == name))
        return results.first()

"""Set up DB config and instance, including sync and async ones"""

import os
import contextlib
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    AsyncConnection,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv


load_dotenv()

CHATBOT_DB_ASYNC_URL = os.environ.get("CHATBOT_DB_ASYNC_URL")
RETRIEVAL_DB_SYNC_URL = os.environ.get("RETRIEVAL_DB_SYNC_URL")


class Base(DeclarativeBase):
    """Base class for DB models"""

    # setting for execute default func under async scenario
    __mapper_args__ = {"eager_defaults": True}


class DBSessionManager:
    """DB session manager to manage all async session with DB"""

    def __init__(self, host: str, engine_kwargs: dict[str, any] = None):
        if engine_kwargs is None:
            engine_kwargs = {}
        self.engine = create_async_engine(host, **engine_kwargs)
        self._sessionmaker = async_sessionmaker(
            autocommit=False, bind=self.engine
        )

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self.engine is None:
            raise Exception("Database session manager has not initialized")

        async with self.engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception("Database session manager has not initialized")

        async with self._sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def close(self):
        if self.engine is None:
            raise Exception("Database session manager has not initialized")

        await self.engine.dispose()
        self.engine = None
        self._sessionmaker = None


chatbot_db_async_engine = create_async_engine(CHATBOT_DB_ASYNC_URL, echo=True)
session_manager = DBSessionManager(CHATBOT_DB_ASYNC_URL, {"echo": True})


async def get_db():
    """Get async DB instance with generator"""
    async with session_manager.session() as session:
        yield session


# Used during initialize backend (server.py), to create all missing tables with registered DB models
async def create_all_tables():
    """Create all tables based on schema"""
    async with chatbot_db_async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

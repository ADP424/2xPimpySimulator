from contextlib import asynccontextmanager
import os
from typing import AsyncIterator, Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker, AsyncSession

_ENGINE: Optional[AsyncEngine] = None
_SESSIONMAKER: Optional[async_sessionmaker[AsyncSession]] = None


def _get_engine() -> AsyncEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _make_engine()
    return _ENGINE


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _SESSIONMAKER
    if _SESSIONMAKER is None:
        _SESSIONMAKER = _make_sessionmaker(_get_engine())
    return _SESSIONMAKER


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    Yield an engine session and commit on success, rollback on error.
    Designed to be used like `async with session_scope() as session`.

    Returns
    -------
    AsyncIterator[AsyncSession]
        The yielded session.
    """

    sessionmaker = _get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _get_database_url() -> str:
    load_dotenv()

    db = os.environ.get("DATABASE")
    user = os.environ.get("USER")
    host = os.environ.get("HOST")
    password = os.environ.get("PASSWORD")
    port = os.environ.get("PORT", "5432")

    missing = [
        key for key, value in [("DATABASE", db), ("USER", user), ("HOST", host), ("PASSWORD", password)] if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required env var(s): {', '.join(missing)}. "
            "Provide DATABASE/USER/HOST/PASSWORD(/PORT) in a .env in root."
        )

    user_q = quote_plus(str(user))
    password_q = quote_plus(str(password))

    return f"postgresql+asyncpg://{user_q}:{password_q}@{host}:{port}/{db}"


def _make_engine() -> AsyncEngine:
    return create_async_engine(
        _get_database_url(),
        pool_pre_ping=True,
        future=True,
    )


def _make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)

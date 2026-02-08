from __future__ import annotations

import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker, AsyncSession


def get_database_url() -> str:
    """
    Builds a SQLAlchemy async URL from .env.

    Returns
    -------
    str
        The URL database connection.
    """

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


def make_engine() -> AsyncEngine:
    """
    Creates and returns a SQLAlchemy AsyncEngine to the DB.

    Returns
    -------
    AsyncEngine
        The asynchronous SQLAlchemy engine connection.
    """

    return create_async_engine(
        get_database_url(),
        pool_pre_ping=True,
        future=True,
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)

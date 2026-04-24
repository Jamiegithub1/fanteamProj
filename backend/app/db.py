from contextlib import contextmanager
from typing import Iterator

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def psycopg_url() -> str:
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def sqlalchemy_url() -> str:
    return get_settings().database_url


engine = create_engine(sqlalchemy_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(psycopg_url(), connect_timeout=3) as connection:
        yield connection


def database_ready() -> bool:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except psycopg.Error:
        return False

from contextlib import contextmanager
from typing import Iterator

import psycopg

from app.config import get_settings


def psycopg_url() -> str:
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)


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

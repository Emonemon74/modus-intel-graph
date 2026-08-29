"""Database engine + session plumbing.

SQLAlchemy gives us one API over SQLite (dev) and Postgres (prod). The rest of
the app never imports sqlite3 or psycopg directly -- it only asks for a Session.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# check_same_thread=False: FastAPI serves requests from a threadpool; SQLite's
# default guard would otherwise reject connections reused across threads.
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _rec):  # pragma: no cover
    """WAL lets readers and a writer coexist; busy_timeout makes a second writer
    wait instead of raising 'database is locked' immediately."""
    if _is_sqlite:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Parent class for every ORM model. Base.metadata knows all tables."""


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transaction boundary: commit on success, roll back on error, always close."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency form of the same thing."""
    with session_scope() as s:
        yield s


def init_db() -> None:
    """Create every table that doesn't exist yet. Import models first so they register."""
    from app import models  # noqa: F401  (side effect: populates Base.metadata)

    Base.metadata.create_all(engine)

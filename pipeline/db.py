"""SQLAlchemy engine/session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base


def _ensure_sqlite_dir(url_str: str) -> None:
    """For a file-based SQLite URL, make sure its parent directory exists.

    A fresh checkout (e.g. CI) has no data/ folder, and SQLite won't create the
    directory itself — so create it before the engine tries to connect.
    """
    url = make_url(url_str)
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)
_engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
_SessionFactoryLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


def get_engine():
    return _engine


def create_all() -> None:
    """Create tables if they don't exist. Fine for dev; use migrations later."""
    Base.metadata.create_all(_engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commit on success, rollback on error."""
    session = _SessionFactoryLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

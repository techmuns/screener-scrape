"""SQLAlchemy engine/session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base

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

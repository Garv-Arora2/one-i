"""Shared test fixtures.

API tests run against a temporary SQLite database seeded with the fictional
demo dataset through the real ingestion and analysis pipeline.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.seed.loader import load_demo_data


@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    engine = create_engine(f"sqlite+pysqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="session")
def seeded_engine(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with factory() as session:
        load_demo_data(session)
        session.commit()
    return engine


@pytest.fixture
def db_session(seeded_engine) -> Iterator[Session]:
    factory = sessionmaker(bind=seeded_engine, autoflush=False, expire_on_commit=False, future=True)
    with factory() as session:
        yield session


@pytest.fixture
def client(db_session) -> Iterator[TestClient]:
    # A developer's local .env (real Google client ID, API keys) must not
    # change what the API tests observe.
    clean_settings = Settings(_env_file=None)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: clean_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def empty_session(engine) -> Iterator[Session]:
    """A session on a second, empty database for storage-level tests."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with factory() as session:
        yield session
        session.rollback()

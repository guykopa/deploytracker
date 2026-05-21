from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from deploytracker.infrastructure.db import database as db_module
from deploytracker.infrastructure.db.orm_models import Base


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(postgres_container: PostgresContainer) -> Generator[object, None, None]:
    raw_url = postgres_container.get_connection_url()
    # Ensure psycopg2 driver specifier is present
    if "+psycopg2" not in raw_url:
        url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        url = raw_url

    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)

    # Wire the module-level singletons used by the app's get_session()
    db_module._engine = engine  # type: ignore[attr-defined]
    db_module._SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine: object) -> Generator[Session, None, None]:
    from sqlalchemy import Engine
    assert isinstance(db_engine, Engine)
    factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_tables(db_session: Session) -> Generator[None, None, None]:
    """Truncate all tables between tests to ensure test isolation."""
    yield
    db_session.execute(text("TRUNCATE deployments, services RESTART IDENTITY CASCADE"))
    db_session.commit()


@pytest.fixture()
async def test_client(db_engine: object) -> AsyncGenerator[AsyncClient, None]:
    # Import app after db_engine is wired so lifespan sees the engine already set
    from deploytracker.api.auth import create_access_token
    from deploytracker.api.main import app
    from deploytracker.infrastructure.config import Settings

    settings = Settings()
    token = create_access_token(settings, settings.admin_username)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        yield client

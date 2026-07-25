import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.main import app

# Database URL for testing (using sqlite+aiosqlite in-memory for testing environment)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    pool_pre_ping=True,
)
TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def init_db() -> AsyncGenerator[None, None]:
    # Import all models to ensure they are registered on Base.metadata
    # noqa: F401
    from app.models.cart import Cart, CartItem  # noqa: F401
    from app.models.payment import PaymentMethod, Refund, Transaction  # noqa: F401
    from app.models.user import User, UserAddress  # noqa: F401

    # noqa: F401
    from app.models.warehouse import Warehouse  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        # Mock commit to perform flush instead, avoiding closed cursors
        async def mock_commit() -> None:
            await session.flush()

        session.commit = mock_commit  # type: ignore[method-assign]
        yield session
        await session.rollback()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    # Override get_db dependency to use the test db session
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_celery_db_session(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    import contextlib

    @contextlib.asynccontextmanager
    async def mock_session_maker() -> AsyncGenerator[AsyncSession, None]:
        yield db

    import app.tasks.celery_tasks

    monkeypatch.setattr(app.tasks.celery_tasks, "AsyncSessionLocal", mock_session_maker)


@pytest.fixture(autouse=True)
def mock_celery_tasks_eager(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.tasks.celery_tasks

    def mock_delay_email(order_id: int) -> None:
        pass

    def mock_delay_index(product_id: int) -> None:
        pass

    def mock_delay_expire() -> None:
        pass

    monkeypatch.setattr(
        app.tasks.celery_tasks.send_order_confirmation_email,
        "delay",
        mock_delay_email,
    )
    monkeypatch.setattr(
        app.tasks.celery_tasks.async_update_product_search_index,
        "delay",
        mock_delay_index,
    )
    monkeypatch.setattr(
        app.tasks.celery_tasks.expire_abandoned_carts,
        "delay",
        mock_delay_expire,
    )

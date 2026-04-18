import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from src.database.base import Base

from src.models.spots import Spot           # noqa: F401
from src.models.parkings import ParkingBase # noqa: F401
from src.models.cameras import Cameras      # noqa: F401
from src.models.vehicles import Vehicles    # noqa: F401
from src.models.tracking import Tracking    # noqa: F401
from src.models.booking import Booking      # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    """Каждый тест — отдельный SAVEPOINT, откатывается после теста."""
    async with engine.begin() as conn:
        async with AsyncSession(bind=conn, expire_on_commit=False) as sess:
            await sess.begin_nested()
            yield sess
            await sess.rollback()

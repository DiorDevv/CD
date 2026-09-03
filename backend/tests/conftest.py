"""Test fixtures.

Talab: ishlaydigan PostgreSQL. Test bazasi nomini `DATABASE_URL` orqali bering,
masalan:  postgresql+asyncpg://soc:soc@localhost:5432/soc_platform_test

Testlar app'ning global engine'idan foydalanmaydi — bu yerda NullPool bilan
alohida engine yaratiladi (pytest-asyncio har bir testni yangi event loop'da
ishlatgani uchun ulanishlar qayta ishlatilmasligi kerak).
"""

import os
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only-000000")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("EXPORT_DIR", os.path.join(tempfile.gettempdir(), "sd_test_exports"))

from app.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)


async def _override_get_db():
    async with TestSession() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture(autouse=True)
async def _schema():
    """Har bir testdan oldin toza sxema."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def superadmin():
    async with TestSession() as db:
        user = User(
            username="root_admin",
            hashed_password=hash_password("RootPass123"),
            role=UserRole.super_admin,
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


ACTOR_PASSWORD = "Passw0rd!!x"


@pytest_asyncio.fixture
async def actors():
    """Har rol uchun bittadan faol foydalanuvchi (parol = ACTOR_PASSWORD)."""
    rows = {
        "root_admin": UserRole.super_admin,
        "soc_boss": UserRole.soc_admin,
        "dlp_boss": UserRole.dlp_admin,
        "watcher": UserRole.viewer,
    }
    async with TestSession() as db:
        for name, role in rows.items():
            db.add(
                User(
                    username=name,
                    hashed_password=hash_password(ACTOR_PASSWORD),
                    role=role,
                    is_active=True,
                    must_change_password=False,
                )
            )
        await db.commit()
    return list(rows)

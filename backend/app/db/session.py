from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.base import Base  # Import Base


connect_args = {}
if settings.DATABASE_URL.startswith("postgresql+asyncpg://"):
    connect_args["timeout"] = int(settings.DB_CONNECT_TIMEOUT_SECONDS)
    if settings.DATABASE_SSL is True:
        connect_args["ssl"] = True

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=bool(settings.DB_ECHO_SQL),
    pool_pre_ping=bool(settings.DB_POOL_PRE_PING),
    pool_recycle=int(settings.DB_POOL_RECYCLE_SECONDS),
    connect_args=connect_args,
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

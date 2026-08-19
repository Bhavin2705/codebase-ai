from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from sqlalchemy.util._concurrency_py3k import await_only
import pgvector.asyncpg

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)


@event.listens_for(engine.sync_engine, "connect")
def on_connect(dbapi_connection, connection_record):
    asyncpg_conn = getattr(
        dbapi_connection,
        "driver_connection",
        getattr(dbapi_connection, "_connection", None),
    )
    if asyncpg_conn:
        await_only(pgvector.asyncpg.register_vector(asyncpg_conn))


AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

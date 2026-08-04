"""
Database engine & session management — SQLAlchemy 2.0 async
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event
from app.config import settings

# SQLite specific: long timeout + WAL mode for concurrent access
_connect_args = {}
_engine_kwargs: dict = {"echo": settings.DEBUG}
if "sqlite" in settings.DATABASE_URL:
    _connect_args = {"timeout": 30}  # Wait up to 30s on lock

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    **_engine_kwargs,
)

# Enable WAL mode for better concurrent read/write
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """ORM base"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — per-request DB session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] Tables created")

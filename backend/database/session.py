from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings


# Detect connection-pooler URLs (PgBouncer transaction mode).
# Supabase uses :6543/; DigitalOcean Managed PG uses :25061/.
# Transaction-mode pooling is incompatible with SQLAlchemy's client-side
# pool, so we use NullPool to avoid double-pooling.
_POOLER_PORTS = (":6543/", ":25061/")
if any(p in settings.database_url for p in _POOLER_PORTS):
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
        echo=settings.log_level == "DEBUG",
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        echo=settings.log_level == "DEBUG",
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

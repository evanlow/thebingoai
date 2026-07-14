from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings


# A client-side pool is kept even behind a transaction-mode pooler
# (Supabase :6543, DO :25061). The pooler multiplexes server connections;
# the client pool keeps TCP+TLS warm so requests don't pay a full handshake
# per query. NullPool here caused a connection storm under load: every
# request opened a fresh TLS connection, saturating the database
# (40 concurrent users -> minutes-long request queues, ROLLBACKs stuck >100s).
# Double-pooling is safe because the ORM relies on no session state
# (no server-side prepared statements, SET vars, or advisory locks).
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=1800,
    echo=settings.log_level == "DEBUG",
)

# expire_on_commit=False: chat.py / websocket.py hand ORM rows (history Messages,
# custom agents, skills) to the orchestrator and close the session before the run
# (see the comment there). With the default True, add_message()'s commit blanks
# those rows, and the first attribute read inside the agent — on a now-detached
# instance — raises DetachedInstanceError.
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
)


def get_db() -> Session:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

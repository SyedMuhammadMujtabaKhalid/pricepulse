"""
PricePulse — Database Connection Management
=============================================

SQLAlchemy engine and session factory for PostgreSQL.

Engineering Decisions:
    1. SQLAlchemy 2.0 style:
       - Uses the modern `create_engine()` + `sessionmaker()` pattern.
       - Type-safe with `Session` objects.
       - Compatible with both sync and async (future migration path).

    2. Connection pooling:
       - SQLAlchemy manages a pool of database connections automatically.
       - pool_size=5: keeps 5 connections warm (good for small-medium workloads).
       - max_overflow=10: allows up to 15 total connections under burst load.
       - pool_pre_ping=True: validates connections before use (handles DB restarts).

    3. Session pattern:
       - get_session() is a context manager that auto-commits on success
         and auto-rollbacks on exception.
       - This prevents connection leaks and ensures transactional safety.

    4. Engine is created lazily (on first call to get_engine).
       This avoids connecting to the database on import, which would
       break unit tests that don't need a real DB.

Usage:
    from src.storage.database import get_session, get_engine

    # For queries:
    with get_session() as session:
        products = session.query(Product).all()

    # For health checks:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config.settings import get_settings
from src.core.logger import get_logger

log = get_logger(__name__)

# ── ORM Base ──────────────────────────────────────────────────
# All SQLAlchemy models inherit from this base class.
# Defined here (not in models.py) to avoid circular imports.
Base = declarative_base()

# ── Module-level singletons ───────────────────────────────────
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """
    Create or return the SQLAlchemy engine (singleton).

    Why singleton?
        The engine manages a connection pool. Creating multiple engines
        would create multiple pools, wasting database connections.
        One engine per process is the standard pattern.
    """
    global _engine

    if _engine is None:
        settings = get_settings()
        database_url = settings.get_database_url()

        log.info(
            "database.engine.creating",
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
        )

        _engine = create_engine(
            database_url,
            # ── Pool configuration ──
            pool_size=5,  # Baseline connections to keep open
            max_overflow=10,  # Extra connections under load (total max: 15)
            pool_pre_ping=True,  # Verify connection is alive before using it
            pool_recycle=3600,  # Recycle connections after 1 hour (prevents stale)
            # ── Logging ──
            echo=settings.is_development and settings.log_level == "DEBUG",
        )

        log.info("database.engine.created")

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """
    Create or return the session factory (singleton).

    Why sessionmaker?
        Creating a Session directly couples your code to a specific engine.
        sessionmaker is a factory that produces pre-configured Session objects,
        making it easy to swap engines (e.g., for testing with SQLite).
    """
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            bind=engine,
            autocommit=False,  # Explicit commits only
            autoflush=False,  # Don't auto-flush before queries (predictable behavior)
            expire_on_commit=False,  # Keep objects usable after commit
        )

    return _session_factory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Provide a transactional database session.

    Usage:
        with get_session() as session:
            session.add(product)
            # Auto-commits on clean exit
            # Auto-rollbacks on exception

    Why context manager?
        - Guarantees the session is always closed (no connection leaks).
        - Commits on success, rollbacks on failure — transactional safety.
        - Follows the "Acquire → Use → Release" pattern.
    """
    factory = get_session_factory()
    session = factory()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        log.error("database.session.rollback", exc_info=True)
        raise
    finally:
        session.close()


def check_connection() -> bool:
    """
    Verify database connectivity.

    Returns:
        True if the database is reachable, False otherwise.

    Used by:
        - scripts/test_db_connection.py
        - Pipeline health checks
        - Dashboard status page
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            value = result.scalar()
            if value == 1:
                log.info("database.health.ok")
                return True
            log.error("database.health.unexpected_result", result=value)
            return False
    except Exception as e:
        log.error("database.health.failed", error=str(e))
        return False


def get_db_version() -> str | None:
    """
    Return the PostgreSQL server version string.

    Useful for diagnostics and the dashboard health page.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            return result.scalar()
    except Exception as e:
        log.error("database.version.failed", error=str(e))
        return None

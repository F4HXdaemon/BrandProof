import os
import logging
from typing import Generator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger("brandproof.database")

db_url = settings.DATABASE_URL
has_psycopg3 = False
try:
    import psycopg  # noqa: F401
    has_psycopg3 = True
except ImportError:
    pass

if db_url.startswith("postgres://"):
    driver_prefix = "postgresql://" if has_psycopg3 else "postgresql+psycopg2://"
    db_url = db_url.replace("postgres://", driver_prefix, 1)
elif db_url.startswith("postgresql://") and not has_psycopg3:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine_kwargs: Dict[str, Any] = {
    "pool_pre_ping": True,  # Critical for Neon serverless sleep/wake and connection verification
    "echo": False,
}

if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    # Ensure parent directory exists for file-based SQLite databases (e.g. /tmp)
    if db_url.startswith("sqlite:///"):
        sqlite_file = db_url.replace("sqlite:///", "")
        if sqlite_file and sqlite_file != ":memory:":
            parent_dir = os.path.dirname(os.path.abspath(sqlite_file))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
else:
    # PostgreSQL / Neon production connection pooling & health checks
    engine_kwargs["pool_size"] = getattr(settings, "DB_POOL_SIZE", 10)
    engine_kwargs["max_overflow"] = getattr(settings, "DB_MAX_OVERFLOW", 20)
    engine_kwargs["pool_recycle"] = getattr(settings, "DB_POOL_RECYCLE", 300)
    engine_kwargs["pool_timeout"] = getattr(settings, "DB_POOL_TIMEOUT", 30)

    # Preserve SSL configuration for PostgreSQL connections
    if "sslmode" not in db_url and "ssl=" not in db_url:
        is_local = "localhost" in db_url or "127.0.0.1" in db_url or "@postgres:" in db_url
        if not is_local:
            engine_kwargs["connect_args"] = {"sslmode": "require"}

try:
    engine = create_engine(db_url, **engine_kwargs)
except Exception as e:
    logger.critical(f"Failed to initialize SQLAlchemy database engine: {e}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> Dict[str, Any]:
    """
    Verifies live database connectivity and pool health without exposing
    connection strings, credentials, or internal hosts.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        dialect_name = engine.dialect.name
        info: Dict[str, Any] = {
            "status": "healthy",
            "connected": True,
            "dialect": dialect_name,
        }
        
        # Include connection pool statistics if pooling is enabled
        pool = engine.pool
        if hasattr(pool, "size"):
            info["pool"] = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }
        return info
    except Exception as e:
        logger.error(f"Database health verification failed: {e}")
        return {
            "status": "unhealthy",
            "connected": False,
            "error": "Database connectivity check failed",
        }

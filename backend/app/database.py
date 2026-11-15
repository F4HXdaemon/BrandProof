import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine_kwargs = {
    "pool_pre_ping": True,
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
    # PostgreSQL production connection pooling & health checks
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(db_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import Base
import app.models  # Ensure all models are registered

config = context.config

# Direct unpooled connection URL takes priority for Alembic migrations,
# preventing transaction conflicts with Neon PgBouncer transaction pooling.
migration_url = (
    getattr(settings, "DIRECT_DATABASE_URL", None)
    or os.environ.get("DIRECT_DATABASE_URL")
    or settings.DATABASE_URL
)
has_psycopg3 = False
try:
    import psycopg  # noqa: F401
    has_psycopg3 = True
except ImportError:
    pass

if migration_url.startswith("postgres://"):
    driver_prefix = "postgresql://" if has_psycopg3 else "postgresql+psycopg2://"
    migration_url = migration_url.replace("postgres://", driver_prefix, 1)
elif migration_url.startswith("postgresql://") and not has_psycopg3:
    migration_url = migration_url.replace("postgresql://", "postgresql+psycopg2://", 1)

# Enforce sslmode=require for non-local PostgreSQL connections
if migration_url.startswith("postgresql://") or migration_url.startswith("postgresql+"):
    is_local = "localhost" in migration_url or "127.0.0.1" in migration_url or "@postgres:" in migration_url
    if not is_local and "sslmode=" not in migration_url and "ssl=" not in migration_url:
        delimiter = "&" if "?" in migration_url else "?"
        migration_url = f"{migration_url}{delimiter}sslmode=require"

# Override sqlalchemy.url with the determined migration URL
config.set_main_option("sqlalchemy.url", migration_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = migration_url

    connect_args = {}
    if migration_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if migration_url.startswith("sqlite:///"):
            sqlite_file = migration_url.replace("sqlite:///", "")
            if sqlite_file and sqlite_file != ":memory:":
                parent_dir = os.path.dirname(os.path.abspath(sqlite_file))
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
    else:
        if "sslmode" not in migration_url and "ssl=" not in migration_url:
            is_local = "localhost" in migration_url or "127.0.0.1" in migration_url or "@postgres:" in migration_url
            if not is_local:
                connect_args["sslmode"] = "require"

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

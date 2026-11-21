import os
import json
import tempfile
from typing import List, Union, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "BrandProof Brand Governance Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database Configuration (Neon PostgreSQL in Production; SQLite in Dev/Test)
    DATABASE_URL: str = "sqlite:///./brandproof.db"
    DIRECT_DATABASE_URL: Optional[str] = None

    # Database Connection Pooling (optimized for Neon serverless PgBouncer pooler)
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 300
    DB_POOL_TIMEOUT: int = 30

    # Security
    SECRET_KEY: str = "brandproof-super-secure-production-ready-jwt-secret-key-replace-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Storage abstraction
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    STORAGE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage_data")

    # S3 Storage (for production / S3-compatible object storage)
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET_NAME: str = "brandproof-documents"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # Controlled Demo / Testing Mode
    ENABLE_DEMO_RESET: bool = False
    ENABLE_DEMO_MODE: bool = False

    @field_validator("DATABASE_URL", "DIRECT_DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str]) -> Optional[str]:
        """Normalize Render/Neon postgres:// prefix, route to available driver, and preserve SSL."""
        if not v or not isinstance(v, str):
            return v
        cleaned = v.strip()

        # Check if psycopg (psycopg 3) is installed; if not, explicitly specify psycopg2
        has_psycopg3 = False
        try:
            import psycopg  # noqa: F401
            has_psycopg3 = True
        except ImportError:
            pass

        if cleaned.startswith("postgres://"):
            driver_prefix = "postgresql://" if has_psycopg3 else "postgresql+psycopg2://"
            cleaned = cleaned.replace("postgres://", driver_prefix, 1)
        elif cleaned.startswith("postgresql://") and not has_psycopg3:
            cleaned = cleaned.replace("postgresql://", "postgresql+psycopg2://", 1)

        # Enforce sslmode=require for cloud PostgreSQL (Neon, Render, Supabase, RDS)
        if cleaned.startswith("postgresql://") or cleaned.startswith("postgresql+"):
            is_local = "localhost" in cleaned or "127.0.0.1" in cleaned or "@postgres:" in cleaned
            if not is_local and "sslmode=" not in cleaned and "ssl=" not in cleaned:
                delimiter = "&" if "?" in cleaned else "?"
                cleaned = f"{cleaned}{delimiter}sslmode=require"
        return cleaned

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Support comma-separated string, JSON array string, or python list for CORS origins."""
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    return json.loads(v_trimmed)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(i) for i in v]
        return []

    @model_validator(mode="after")
    def validate_environment_configuration(self) -> "Settings":
        """
        Validates environment-specific configuration:
        - PREVIEW mode: permits ephemeral SQLite at /tmp/brandproof-preview.db and local storage at /tmp/brandproof-uploads
        - PRODUCTION mode: strictly enforces PostgreSQL, high-entropy JWT secrets, non-default credentials, and disables demo reset
        """
        env = self.ENVIRONMENT.lower()

        # =========================================================================
        # 1. PREVIEW DEPLOYMENT MODE (Render Free Tier + Vercel)
        # =========================================================================
        if env == "preview":
            # 1. Configure ephemeral SQLite database path
            if self.DATABASE_URL == "sqlite:///./brandproof.db" or not self.DATABASE_URL:
                # Prefer /tmp on Linux/POSIX (Render) or system tempdir on Windows
                preview_tmp = "/tmp" if (os.path.exists("/tmp") or os.name != "nt") else tempfile.gettempdir()
                db_path = os.path.join(preview_tmp, "brandproof-preview.db")
                db_path = db_path.replace("\\", "/")
                self.DATABASE_URL = f"sqlite:///{db_path}"

            # 2. Configure ephemeral uploads directory
            default_storage_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage_data")
            if self.STORAGE_DIR == default_storage_dir or not self.STORAGE_DIR:
                preview_tmp = "/tmp" if (os.path.exists("/tmp") or os.name != "nt") else tempfile.gettempdir()
                self.STORAGE_DIR = os.path.join(preview_tmp, "brandproof-uploads")

            # 3. Force LocalStorageBackend in preview mode (zero external storage required)
            self.STORAGE_BACKEND = "local"

            # 4. Prohibit demo reset in preview mode by default
            self.ENABLE_DEMO_RESET = False

            # 5. Disable debug mode in preview
            self.DEBUG = False

        # =========================================================================
        # 2. STRICT PRODUCTION SECURITY INVARIANTS
        # =========================================================================
        elif env == "production":
            # 1. Enforce non-default cryptographically secure JWT secret
            default_secret = "brandproof-super-secure-production-ready-jwt-secret-key-replace-in-prod"
            if self.SECRET_KEY == default_secret or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Production Security Invariant Violated: SECRET_KEY must be a cryptographically "
                    "secure secret with at least 32 characters in production environment."
                )

            # 2. Reject SQLite in production (PostgreSQL is required)
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(
                    "Production Database Invariant Violated: SQLite is not permitted in production. "
                    "A valid PostgreSQL connection URL must be provided."
                )

            # 3. Disable debug in production
            if self.DEBUG:
                self.DEBUG = False

            # 4. Prohibit demo reset in production
            if self.ENABLE_DEMO_RESET:
                raise ValueError(
                    "Production Invariant Violated: ENABLE_DEMO_RESET must be False in production."
                )

            # 5. If S3 storage is enabled, enforce required credentials
            if self.STORAGE_BACKEND.lower() == "s3":
                if not self.S3_BUCKET_NAME:
                    raise ValueError("S3_BUCKET_NAME is required when STORAGE_BACKEND=s3")
                if not self.S3_ACCESS_KEY or not self.S3_SECRET_KEY:
                    raise ValueError(
                        "S3_ACCESS_KEY and S3_SECRET_KEY are required when STORAGE_BACKEND=s3 in production"
                    )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

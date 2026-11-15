import os
import json
from typing import List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "BrandProof Brand Governance Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./brandproof.db"

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

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        """Fix Render's postgres:// prefix to standard postgresql:// for SQLAlchemy."""
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

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
    def validate_production_configuration(self) -> "Settings":
        """Enforce strict production security invariant: fail safe if insecure."""
        if self.ENVIRONMENT.lower() == "production":
            # 1. Enforce non-default JWT secret
            default_secret = "brandproof-super-secure-production-ready-jwt-secret-key-replace-in-prod"
            if self.SECRET_KEY == default_secret or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Production Security Invariant Violated: SECRET_KEY must be a cryptographically "
                    "secure secret with at least 32 characters in production environment."
                )

            # 2. Reject SQLite in production
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

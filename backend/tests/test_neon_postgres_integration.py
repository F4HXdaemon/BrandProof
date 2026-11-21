"""
Unit and Integration Tests for Neon PostgreSQL Configuration, Pooling,
Health Checks, and Data Migration Utilities.
"""

import os
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import check_db_health, engine
from app.main import app
from scripts.migrate_sqlite_to_postgres import extract_sqlite_data, create_json_backup, TABLE_ORDER

client = TestClient(app)


def test_neon_pooled_and_direct_url_parsing():
    """Verify Neon pooled and direct URLs are parsed, normalized, and have sslmode preserved."""
    pooled_url = "postgres://brandproof_owner:npg_secret123@ep-cool-fog-123456-pooler.us-east-2.aws.neon.tech/brandproof"
    direct_url = "postgres://brandproof_owner:npg_secret123@ep-cool-fog-123456.us-east-2.aws.neon.tech/brandproof"

    s = Settings(
        DATABASE_URL=pooled_url,
        DIRECT_DATABASE_URL=direct_url,
        ENVIRONMENT="development",
        SECRET_KEY="test-secret-key-for-unit-testing-purposes-only",
    )

    # 1. Normalizes postgres:// to postgresql://
    assert s.DATABASE_URL.startswith("postgresql://")
    assert s.DIRECT_DATABASE_URL.startswith("postgresql://")

    # 2. Automatically appends sslmode=require for cloud Neon URLs
    assert "sslmode=require" in s.DATABASE_URL
    assert "sslmode=require" in s.DIRECT_DATABASE_URL

    # 3. Connection pooling defaults
    assert s.DB_POOL_SIZE == 10
    assert s.DB_MAX_OVERFLOW == 20
    assert s.DB_POOL_RECYCLE == 300
    assert s.DB_POOL_TIMEOUT == 30


def test_neon_preserves_existing_sslmode():
    """Verify existing sslmode parameters are not duplicated."""
    url = "postgresql://user:pass@ep-cool-fog-123456-pooler.us-east-2.aws.neon.tech/brandproof?sslmode=verify-full"
    s = Settings(
        DATABASE_URL=url,
        ENVIRONMENT="development",
        SECRET_KEY="test-secret-key-for-unit-testing-purposes-only",
    )
    assert s.DATABASE_URL.count("sslmode") == 1
    assert "sslmode=verify-full" in s.DATABASE_URL


def test_secure_database_health_checks():
    """Verify health check endpoints verify connectivity without leaking credentials."""
    # Test main /api/v1/health endpoint
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "healthy"
    assert "database_dialect" in data
    # Ensure no credentials leaked
    assert "password" not in json.dumps(data).lower()
    assert "secret" not in json.dumps(data).lower()
    assert "url" not in json.dumps(data).lower()

    # Test detailed /api/v1/health/db endpoint
    res_db = client.get("/api/v1/health/db")
    assert res_db.status_code == 200
    db_data = res_db.json()
    assert db_data["status"] == "healthy"
    assert db_data["connected"] is True
    assert "dialect" in db_data


def test_sqlite_data_extraction_and_json_snapshot(tmp_path):
    """Verify data extraction and JSON backup creation from source SQLite database."""
    sqlite_path = "backend/brandproof.db"
    if not os.path.exists(sqlite_path):
        pytest.skip("Source SQLite database not present")

    data = extract_sqlite_data(sqlite_path)

    # Verify key tables exist and have records
    assert "users" in data
    assert len(data["users"]) >= 5
    assert "organizations" in data
    assert len(data["organizations"]) >= 1
    assert "facts" in data
    assert len(data["facts"]) >= 10
    assert "guidelines" in data
    assert len(data["guidelines"]) >= 5

    # Test backup JSON creation
    backup_file = str(tmp_path / "test_backup.json")
    created = create_json_backup(data, backup_file)
    assert os.path.exists(created)

    with open(created, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert "exported_at" in loaded
    assert "tables" in loaded
    assert len(loaded["tables"]["users"]) == len(data["users"])


def test_production_environment_rejects_sqlite():
    """Verify production environment strictly enforces PostgreSQL and rejects SQLite."""
    with pytest.raises(ValueError, match="SQLite is not permitted in production"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///./brandproof.db",
            SECRET_KEY="a-very-long-production-grade-secret-key-32-chars-minimum",
        )

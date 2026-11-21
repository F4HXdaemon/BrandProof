"""
BrandProof SQLite to PostgreSQL Safe Data Migration Utility.

Usage:
  # 1. Export SQLite to JSON backup only:
  python backend/scripts/migrate_sqlite_to_postgres.py --backup-only

  # 2. Migrate from SQLite to Neon PostgreSQL:
  python backend/scripts/migrate_sqlite_to_postgres.py --postgres-url "postgresql://user:pass@ep-xyz-pooler.neon.tech/dbname?sslmode=require"

  # Or using environment variable:
  TARGET_DATABASE_URL="postgresql://..." python backend/scripts/migrate_sqlite_to_postgres.py
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any

# Dependency-ordered tables (parent tables before child tables for foreign key safety)
TABLE_ORDER = [
    "organizations",
    "users",
    "organization_memberships",
    "organization_invitations",
    "facts",
    "guidelines",
    "rules",
    "terms",
    "approved_assets",
    "documents",
    "document_versions",
    "document_chunks",
    "reviews",
    "claims",
    "findings",
    "evidence",
    "review_evidence",
    "approvals",
    "comments",
    "audit_events",
    "alembic_version",
]


def extract_sqlite_data(sqlite_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Reads all tables from the source SQLite database."""
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"Source SQLite database not found at: {sqlite_path}")

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing_tables = set(r[0] for r in cursor.fetchall())

    data = {}
    print(f"\n[1/3] Reading source SQLite database: {sqlite_path}")
    for table in TABLE_ORDER:
        if table not in existing_tables:
            print(f"  - Table '{table}' not present in SQLite database (skipped)")
            data[table] = []
            continue

        cursor.execute(f'SELECT * FROM "{table}"')
        rows = [dict(r) for r in cursor.fetchall()]
        data[table] = rows
        print(f"  + Read '{table}': {len(rows)} records")

    conn.close()
    return data


def create_json_backup(data: Dict[str, List[Dict[str, Any]]], output_path: str) -> str:
    """Exports SQLite data to a formatted JSON snapshot."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    meta = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": "SQLite brandproof.db",
        "counts": {t: len(rows) for t, rows in data.items()},
        "tables": data,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"\n[2/3] Secure JSON snapshot created at: {output_path}")
    return output_path


def load_postgres_data(postgres_url: str, data: Dict[str, List[Dict[str, Any]]], dry_run: bool = False):
    """Loads extracted data into PostgreSQL using SQLAlchemy."""
    from sqlalchemy import create_engine, text, inspect

    if postgres_url.startswith("postgres://"):
        postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)

    print(f"\n[3/3] Connecting to PostgreSQL...")
    engine = create_engine(postgres_url, echo=False)

    with engine.connect() as conn:
        inspector = inspect(engine)
        pg_tables = set(inspector.get_table_names())

        # Verify alembic schema exists
        if "alembic_version" not in pg_tables:
            raise RuntimeError(
                "PostgreSQL database does not have Alembic migrations applied! "
                "Please run 'alembic upgrade head' on PostgreSQL first before migrating data."
            )

        print(f"Target PostgreSQL has {len(pg_tables)} tables initialized.")

        if dry_run:
            print("\nDRY RUN: Verification complete. No records inserted.")
            return

        print("\nBeginning transactional data transfer in foreign-key dependency order:")
        trans = conn.begin()
        try:
            for table in TABLE_ORDER:
                rows = data.get(table, [])
                if not rows:
                    continue

                if table not in pg_tables:
                    print(f"  ! Table '{table}' not in PostgreSQL schema, skipping {len(rows)} rows.")
                    continue

                inserted = 0
                for r in rows:
                    # Sanitize JSON string fields into proper Python dicts/lists for PostgreSQL JSON/JSONB
                    cleaned_row = {}
                    for k, v in r.items():
                        if isinstance(v, str) and (k.endswith("_examples") or k in ("configuration", "disallowed_variants", "intent_card", "override_finding_ids") or k == "metadata"):
                            try:
                                cleaned_row[k] = json.loads(v)
                            except Exception:
                                cleaned_row[k] = v
                        else:
                            cleaned_row[k] = v

                    columns = list(cleaned_row.keys())
                    cols_str = ", ".join(f'"{c}"' for c in columns)
                    vals_str = ", ".join(f":{c}" for c in columns)

                    # For alembic_version, use special single-column handling
                    if table == "alembic_version":
                        conn.execute(
                            text(f'INSERT INTO "{table}" ({cols_str}) VALUES ({vals_str}) ON CONFLICT DO NOTHING'),
                            cleaned_row
                        )
                        inserted += 1
                        continue

                    # Safe upsert / on conflict do nothing for tables with primary key 'id'
                    if "id" in columns:
                        sql = text(f'INSERT INTO "{table}" ({cols_str}) VALUES ({vals_str}) ON CONFLICT ("id") DO NOTHING')
                    else:
                        sql = text(f'INSERT INTO "{table}" ({cols_str}) VALUES ({vals_str})')

                    res = conn.execute(sql, cleaned_row)
                    if res.rowcount > 0:
                        inserted += 1

                print(f"  + Table '{table}': {inserted}/{len(rows)} records successfully transferred.")

            trans.commit()
            print("\nAll data successfully migrated and committed to PostgreSQL!")

        except Exception as e:
            trans.rollback()
            print(f"\nCRITICAL ERROR during migration. Rolled back transaction: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description="BrandProof SQLite to PostgreSQL migration tool.")
    parser.add_argument("--sqlite-path", default="backend/brandproof.db", help="Path to source SQLite database")
    parser.add_argument("--backup-path", default="backend/brandproof_backup.json", help="Path to write JSON backup")
    parser.add_argument("--backup-only", action="store_true", help="Only create backup JSON, do not migrate to PostgreSQL")
    parser.add_argument("--postgres-url", default=os.environ.get("TARGET_DATABASE_URL"), help="Target PostgreSQL connection URL")
    parser.add_argument("--dry-run", action="store_true", help="Verify connection and schema without inserting data")

    args = parser.parse_args()

    data = extract_sqlite_data(args.sqlite_path)
    create_json_backup(data, args.backup_path)

    if args.backup_only:
        print("\nBackup-only mode requested. Process finished.")
        return

    if not args.postgres_url:
        print("\nNotice: No --postgres-url or TARGET_DATABASE_URL supplied.")
        print("To migrate data into Neon PostgreSQL, run:")
        print(f"  python {sys.argv[0]} --postgres-url \"postgresql://<user>:<password>@<neon-host>/<db>?sslmode=require\"")
        return

    load_postgres_data(args.postgres_url, data, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

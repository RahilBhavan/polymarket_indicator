#!/usr/bin/env python3
"""Initialize CryptoSignal database schema and apply migrations."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# Load .env from project root so DATABASE_URL is available when run as script
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import asyncpg


class DatabaseError(Exception):
    """Raised when database operations fail."""
    pass


async def create_database_if_not_exists(
    url: str, target_db: str, verbose: bool = True
) -> bool:
    """
    Create database if it doesn't exist.

    Args:
        url: PostgreSQL connection URL
        target_db: Database name to create
        verbose: Print status messages

    Returns:
        True if database was created, False if it already existed
    """
    # Connect to 'postgres' database to check/create target database
    # Extract base URL without database name
    parts = url.rsplit("/", 1)
    if len(parts) != 2:
        raise DatabaseError(f"Invalid DATABASE_URL format: {url}")

    base_url = parts[0]
    admin_url = f"{base_url}/postgres"

    try:
        conn = await asyncpg.connect(admin_url)
        try:
            # Check if database exists
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", target_db
            )
            if exists:
                if verbose:
                    print(f"✅ Database '{target_db}' already exists")
                return False

            # Create database
            await conn.execute(f'CREATE DATABASE "{target_db}"')
            if verbose:
                print(f"✅ Created database '{target_db}'")
            return True
        finally:
            await conn.close()
    except Exception as e:
        raise DatabaseError(f"Failed to create database: {e}")


async def get_connection(url: str) -> asyncpg.Connection:
    """Get database connection."""
    try:
        conn = await asyncpg.connect(url)
        return conn
    except Exception as e:
        raise DatabaseError(f"Failed to connect to database: {e}")


async def create_migration_table(conn: asyncpg.Connection, verbose: bool = True):
    """Create schema_migrations table if it doesn't exist."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id SERIAL PRIMARY KEY,
            version TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            description TEXT
        )
        """
    )
    if verbose:
        print("✅ Migration tracking table ready")


async def get_applied_migrations(conn: asyncpg.Connection) -> set[str]:
    """Get set of already applied migration versions."""
    rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY id")
    return {row["version"] for row in rows}


async def apply_schema_file(
    conn: asyncpg.Connection, schema_path: Path, verbose: bool = True
):
    """Apply base schema from SQL file."""
    if not schema_path.exists():
        raise DatabaseError(f"Schema file not found: {schema_path}")

    schema_sql = schema_path.read_text()
    await conn.execute(schema_sql)

    if verbose:
        print(f"✅ Applied schema from {schema_path.name}")


async def apply_migration(
    conn: asyncpg.Connection,
    migration_path: Path,
    version: str,
    description: str,
    verbose: bool = True,
):
    """Apply a single migration file."""
    if not migration_path.exists():
        raise DatabaseError(f"Migration file not found: {migration_path}")

    migration_sql = migration_path.read_text()

    # Execute migration in a transaction
    async with conn.transaction():
        await conn.execute(migration_sql)
        await conn.execute(
            "INSERT INTO schema_migrations (version, description) VALUES ($1, $2)",
            version,
            description,
        )

    if verbose:
        print(f"✅ Applied migration {version}: {description}")


async def init_database(
    url: str,
    schema_path: Optional[Path] = None,
    migrations_dir: Optional[Path] = None,
    force_schema: bool = False,
    dry_run: bool = False,
    verbose: bool = True,
):
    """
    Initialize database with schema and migrations.

    Args:
        url: PostgreSQL connection URL
        schema_path: Path to base schema.sql file
        migrations_dir: Path to migrations directory
        force_schema: If True, always run schema (use for fresh DBs only)
        dry_run: If True, show what would be done without applying
        verbose: Print status messages
    """
    # Set default paths
    project_root = Path(__file__).parent.parent
    if schema_path is None:
        schema_path = project_root / "src" / "app" / "db" / "schema.sql"
    if migrations_dir is None:
        migrations_dir = project_root / "scripts" / "migrations"

    if verbose:
        print("\n🚀 Initializing CryptoSignal database...\n")
        if dry_run:
            print("🔍 DRY RUN MODE - no changes will be applied\n")

    # Extract database name from URL
    db_name = url.rsplit("/", 1)[-1].split("?")[0]

    # Create database if needed
    if not dry_run:
        try:
            await create_database_if_not_exists(url, db_name, verbose=verbose)
        except DatabaseError as e:
            if verbose:
                print(f"⚠️  Could not create database (may need manual creation): {e}")

    # Connect to database
    if verbose:
        print(f"🔌 Connecting to database '{db_name}'...")

    if dry_run:
        if verbose:
            print("✅ Would connect to database\n")
        return

    conn = await get_connection(url)

    try:
        # Create migration tracking table
        await create_migration_table(conn, verbose=verbose)

        # Get applied migrations
        applied = await get_applied_migrations(conn)
        if verbose and applied:
            print(f"📋 Found {len(applied)} previously applied migrations")

        # Check if we need to apply base schema
        if force_schema or not applied:
            if verbose:
                if force_schema:
                    print("⚠️  Force mode: applying schema (may fail if tables exist)")
                else:
                    print("🆕 No migrations found, applying base schema")

            await apply_schema_file(conn, schema_path, verbose=verbose)

            # Record baseline migration
            await conn.execute(
                """
                INSERT INTO schema_migrations (version, description)
                VALUES ($1, $2)
                ON CONFLICT (version) DO NOTHING
                """,
                "001_baseline",
                "Initial schema",
            )
            applied.add("001_baseline")

        # Apply pending migrations
        if migrations_dir.exists():
            migration_files = sorted(migrations_dir.glob("*.sql"))
            pending = []

            for migration_file in migration_files:
                # Extract version from filename (e.g., "002_add_asset.sql" -> "002")
                version = migration_file.stem.split("_")[0]
                description = "_".join(migration_file.stem.split("_")[1:])

                # Skip baseline (already handled above)
                if version == "001":
                    continue

                if version not in applied:
                    pending.append((version, description, migration_file))

            if pending:
                if verbose:
                    print(f"\n📦 Applying {len(pending)} pending migrations...\n")

                for version, description, migration_file in pending:
                    await apply_migration(
                        conn, migration_file, version, description, verbose=verbose
                    )
            elif verbose:
                print("\n✅ All migrations already applied\n")
        elif verbose:
            print(f"⚠️  No migrations directory found at {migrations_dir}")

        if verbose:
            # Final status
            final_applied = await get_applied_migrations(conn)
            print(f"\n✅ Database initialized successfully!")
            print(f"   Total migrations: {len(final_applied)}")
            print()

    finally:
        await conn.close()


async def show_migration_status(url: str, migrations_dir: Optional[Path] = None):
    """Show current migration status."""
    project_root = Path(__file__).parent.parent
    if migrations_dir is None:
        migrations_dir = project_root / "scripts" / "migrations"

    print("\n📊 Migration Status\n")

    conn = await get_connection(url)
    try:
        # Ensure migration table exists
        await create_migration_table(conn, verbose=False)

        # Get applied migrations
        applied_rows = await conn.fetch(
            "SELECT version, description, applied_at FROM schema_migrations ORDER BY id"
        )
        applied_versions = {row["version"] for row in applied_rows}

        print("Applied migrations:")
        if applied_rows:
            for row in applied_rows:
                print(f"  ✅ {row['version']}: {row['description']} ({row['applied_at']})")
        else:
            print("  (none)")

        # Find pending migrations
        if migrations_dir.exists():
            migration_files = sorted(migrations_dir.glob("*.sql"))
            pending = []

            for migration_file in migration_files:
                version = migration_file.stem.split("_")[0]
                description = "_".join(migration_file.stem.split("_")[1:])

                if version not in applied_versions:
                    pending.append((version, description))

            print(f"\nPending migrations:")
            if pending:
                for version, description in pending:
                    print(f"  ⏳ {version}: {description}")
            else:
                print("  (none)")
        else:
            print(f"\n⚠️  Migrations directory not found: {migrations_dir}")

        print()

    finally:
        await conn.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize CryptoSignal database")
    parser.add_argument(
        "--url",
        help="PostgreSQL connection URL (defaults to DATABASE_URL env var)",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        help="Path to schema.sql file",
    )
    parser.add_argument(
        "--migrations",
        type=Path,
        help="Path to migrations directory",
    )
    parser.add_argument(
        "--force-schema",
        action="store_true",
        help="Force schema application (use only for fresh databases)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without applying changes",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status and exit",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress status messages",
    )

    args = parser.parse_args()

    # Get DATABASE_URL
    url = args.url or os.getenv("DATABASE_URL")
    if not url:
        print("❌ Error: DATABASE_URL not set and --url not provided\n")
        print("Set DATABASE_URL in your environment or use --url flag\n")
        sys.exit(1)

    try:
        if args.status:
            asyncio.run(show_migration_status(url, args.migrations))
        else:
            asyncio.run(
                init_database(
                    url,
                    schema_path=args.schema,
                    migrations_dir=args.migrations,
                    force_schema=args.force_schema,
                    dry_run=args.dry_run,
                    verbose=not args.quiet,
                )
            )
    except DatabaseError as e:
        print(f"\n❌ Database error: {e}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

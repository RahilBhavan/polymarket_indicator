#!/usr/bin/env python3
"""Migration management CLI for CryptoSignal bot."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import asyncpg

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class MigrationManager:
    """Manage database migrations."""

    def __init__(self, url: str, migrations_dir: Path):
        self.url = url
        self.migrations_dir = migrations_dir

    async def get_connection(self) -> asyncpg.Connection:
        """Get database connection."""
        try:
            conn = await asyncpg.connect(self.url)
            return conn
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            sys.exit(1)

    async def ensure_migration_table(self, conn: asyncpg.Connection):
        """Ensure schema_migrations table exists."""
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

    async def get_applied_migrations(self, conn: asyncpg.Connection) -> list[dict]:
        """Get list of applied migrations with details."""
        rows = await conn.fetch(
            """
            SELECT version, description, applied_at
            FROM schema_migrations
            ORDER BY id
            """
        )
        return [dict(row) for row in rows]

    async def get_pending_migrations(self, conn: asyncpg.Connection) -> list[dict]:
        """Get list of pending migrations."""
        applied = await self.get_applied_migrations(conn)
        applied_versions = {m["version"] for m in applied}

        pending = []
        if self.migrations_dir.exists():
            migration_files = sorted(self.migrations_dir.glob("*.sql"))
            for migration_file in migration_files:
                version = migration_file.stem.split("_")[0]
                description = "_".join(migration_file.stem.split("_")[1:])

                if version not in applied_versions:
                    pending.append(
                        {
                            "version": version,
                            "description": description,
                            "file": migration_file,
                        }
                    )

        return pending

    async def cmd_status(self):
        """Show migration status."""
        print("\n📊 Migration Status\n")

        conn = await self.get_connection()
        try:
            await self.ensure_migration_table(conn)

            applied = await self.get_applied_migrations(conn)
            pending = await self.get_pending_migrations(conn)

            # Applied migrations
            print("✅ Applied Migrations:")
            if applied:
                for m in applied:
                    print(
                        f"  {m['version']}: {m['description']} "
                        f"(applied: {m['applied_at'].strftime('%Y-%m-%d %H:%M:%S')})"
                    )
            else:
                print("  (none)")

            # Pending migrations
            print(f"\n⏳ Pending Migrations:")
            if pending:
                for m in pending:
                    print(f"  {m['version']}: {m['description']}")
            else:
                print("  (none)")

            # Summary
            print(f"\n📈 Summary:")
            print(f"  Applied: {len(applied)}")
            print(f"  Pending: {len(pending)}")
            print()

        finally:
            await conn.close()

    async def cmd_list(self):
        """List all available migrations."""
        print("\n📋 Available Migrations\n")

        if not self.migrations_dir.exists():
            print(f"❌ Migrations directory not found: {self.migrations_dir}")
            return

        migration_files = sorted(self.migrations_dir.glob("*.sql"))
        if not migration_files:
            print("  (no migrations found)")
            return

        for migration_file in migration_files:
            version = migration_file.stem.split("_")[0]
            description = "_".join(migration_file.stem.split("_")[1:])
            print(f"  {version}: {description}")
            print(f"    File: {migration_file}")

        print()

    async def cmd_apply(self, version: Optional[str] = None, dry_run: bool = False):
        """Apply pending migrations."""
        conn = await self.get_connection()
        try:
            await self.ensure_migration_table(conn)
            pending = await self.get_pending_migrations(conn)

            if not pending:
                print("\n✅ No pending migrations\n")
                return

            # Filter by version if specified
            if version:
                pending = [m for m in pending if m["version"] == version]
                if not pending:
                    print(f"\n❌ Migration {version} not found or already applied\n")
                    return

            if dry_run:
                print("\n🔍 DRY RUN - Would apply:\n")
                for m in pending:
                    print(f"  {m['version']}: {m['description']}")
                print()
                return

            print(f"\n📦 Applying {len(pending)} migration(s)...\n")

            for m in pending:
                print(f"Applying {m['version']}: {m['description']}...", end=" ")

                # Read migration SQL
                migration_sql = m["file"].read_text()

                try:
                    async with conn.transaction():
                        await conn.execute(migration_sql)
                        await conn.execute(
                            """
                            INSERT INTO schema_migrations (version, description)
                            VALUES ($1, $2)
                            """,
                            m["version"],
                            m["description"],
                        )
                    print("✅")
                except Exception as e:
                    print(f"❌ Failed: {e}")
                    print(f"\n⚠️  Migration {m['version']} failed. Stopping.\n")
                    sys.exit(1)

            print("\n✅ All migrations applied successfully\n")

        finally:
            await conn.close()

    async def cmd_rollback(self, version: str):
        """Mark a migration as not applied (manual rollback)."""
        print(f"\n⚠️  Rolling back migration {version}...\n")
        print("This only removes the migration record.")
        print("You must manually undo the database changes!\n")

        confirm = input("Are you sure? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return

        conn = await self.get_connection()
        try:
            await self.ensure_migration_table(conn)

            # Check if migration exists
            exists = await conn.fetchval(
                "SELECT 1 FROM schema_migrations WHERE version = $1", version
            )

            if not exists:
                print(f"❌ Migration {version} not found in applied migrations")
                return

            # Delete migration record
            await conn.execute(
                "DELETE FROM schema_migrations WHERE version = $1", version
            )

            print(f"✅ Migration {version} marked as not applied")
            print("\n⚠️  Remember to manually undo the database changes!")
            print(f"    Check scripts/migrations/{version}_*.sql for what to undo\n")

        finally:
            await conn.close()

    async def cmd_validate(self):
        """Validate migration files and database state."""
        print("\n🔍 Validating Migrations\n")

        errors = []
        warnings = []

        # Check migrations directory exists
        if not self.migrations_dir.exists():
            errors.append(f"Migrations directory not found: {self.migrations_dir}")
        else:
            # Check migration files
            migration_files = sorted(self.migrations_dir.glob("*.sql"))
            if not migration_files:
                warnings.append("No migration files found")
            else:
                print(f"Found {len(migration_files)} migration file(s)")

                # Check naming convention
                for migration_file in migration_files:
                    if not migration_file.stem[0].isdigit():
                        errors.append(
                            f"Invalid migration name: {migration_file.name} "
                            f"(should start with number)"
                        )

                    # Check file is readable and contains SQL
                    try:
                        content = migration_file.read_text()
                        if not content.strip():
                            errors.append(
                                f"Empty migration file: {migration_file.name}"
                            )
                        if "CREATE" not in content.upper() and "ALTER" not in content.upper():
                            warnings.append(
                                f"No CREATE/ALTER found in {migration_file.name}"
                            )
                    except Exception as e:
                        errors.append(f"Cannot read {migration_file.name}: {e}")

        # Check database connection and schema
        try:
            conn = await self.get_connection()
            try:
                await self.ensure_migration_table(conn)
                applied = await self.get_applied_migrations(conn)
                print(f"Database has {len(applied)} applied migration(s)")

                # Check for gaps in versions
                if applied:
                    versions = [int(m["version"]) for m in applied if m["version"].isdigit()]
                    if versions:
                        expected = list(range(1, max(versions) + 1))
                        actual = sorted(versions)
                        missing = set(expected) - set(actual)
                        if missing:
                            warnings.append(
                                f"Version gaps detected: {sorted(missing)}"
                            )
            finally:
                await conn.close()
        except Exception as e:
            errors.append(f"Database validation failed: {e}")

        # Report results
        print()
        if errors:
            print("❌ Errors:")
            for error in errors:
                print(f"  - {error}")
            print()

        if warnings:
            print("⚠️  Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
            print()

        if not errors and not warnings:
            print("✅ All validations passed\n")
        elif not errors:
            print("⚠️  Validation passed with warnings\n")
        else:
            print("❌ Validation failed\n")
            sys.exit(1)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage CryptoSignal database migrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status              # Show applied and pending migrations
  %(prog)s list                # List all available migrations
  %(prog)s apply               # Apply all pending migrations
  %(prog)s apply --version 002 # Apply specific migration
  %(prog)s apply --dry-run     # Show what would be applied
  %(prog)s validate            # Validate migration files and state
  %(prog)s rollback 004        # Mark migration as not applied (manual rollback)
        """,
    )

    parser.add_argument(
        "command",
        choices=["status", "list", "apply", "rollback", "validate"],
        help="Command to execute",
    )
    parser.add_argument(
        "version",
        nargs="?",
        help="Migration version (for rollback or specific apply)",
    )
    parser.add_argument(
        "--url",
        help="PostgreSQL connection URL (defaults to DATABASE_URL env var)",
    )
    parser.add_argument(
        "--migrations",
        type=Path,
        help="Path to migrations directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without applying (for apply command)",
    )

    args = parser.parse_args()

    # Get DATABASE_URL
    url = args.url or os.getenv("DATABASE_URL")
    if not url:
        print("❌ Error: DATABASE_URL not set and --url not provided\n")
        sys.exit(1)

    # Get migrations directory
    project_root = Path(__file__).parent.parent
    migrations_dir = args.migrations or project_root / "scripts" / "migrations"

    # Create manager
    manager = MigrationManager(url, migrations_dir)

    # Execute command
    try:
        if args.command == "status":
            asyncio.run(manager.cmd_status())
        elif args.command == "list":
            asyncio.run(manager.cmd_list())
        elif args.command == "apply":
            asyncio.run(manager.cmd_apply(args.version, args.dry_run))
        elif args.command == "rollback":
            if not args.version:
                print("❌ Error: version required for rollback\n")
                print("Example: migrate.py rollback 004\n")
                sys.exit(1)
            asyncio.run(manager.cmd_rollback(args.version))
        elif args.command == "validate":
            asyncio.run(manager.cmd_validate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

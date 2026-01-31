"""Run schema.sql against DATABASE_URL. Use: uv run python scripts/run_schema.py."""

import asyncio
import os
from pathlib import Path

import asyncpg


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set")
    root = Path(__file__).resolve().parent.parent
    schema_path = root / "src" / "app" / "db" / "schema.sql"
    sql = schema_path.read_text()
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(sql)
        print("Schema applied.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

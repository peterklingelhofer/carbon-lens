"""Create all database tables. Run once on startup or via CLI."""

import asyncio

from carbon_mesh.db.engine import async_engine
from carbon_mesh.db.models import Base


async def create_tables() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(create_tables())

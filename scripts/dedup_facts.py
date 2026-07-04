#!/usr/bin/env python3
"""
dedup_facts.py — Jaccard semantic dedup
Cron: weekly Sunday 03:00
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session
from app.models.memory import Memory
from app.services.dedup_engine import find_duplicates


async def main():
    async with async_session() as db:
        stmt = select(Memory).where(Memory.tenant_id == "default", Memory.status == "active")
        result = await db.execute(stmt)
        rows = result.scalars().all()
        contents = [r.raw_content for r in rows if r.raw_content]
        ids = [r.memory_id for r in rows if r.raw_content]
        groups = find_duplicates(contents)
        archived = 0
        for group in groups:
            for idx in group[1:]:
                mid = ids[idx]
                await db.execute(
                    Memory.__table__.update().where(Memory.memory_id == mid).values(status="archived")
                )
                archived += 1
        await db.commit()
        print(f"[dedup_facts] total={len(rows)} groups={len(groups)} archived={archived}")
    return {"groups": len(groups), "archived": archived}


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)

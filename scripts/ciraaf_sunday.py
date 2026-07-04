#!/usr/bin/env python3
"""
ciraaf_sunday.py — CIRAAF Sunday macro重构
Cron: weekly Sunday 03:30
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from app.core.database import async_session
from app.models.memory import Memory
from app.services.memory_quality import MemoryQualityService


async def main():
    async with async_session() as db:
        quality = MemoryQualityService(db)
        decay_result = await quality.scan_and_decay("default")
        trust_result = await quality.recompute_all_trust()
        stmt = select(
            Memory.memory_type,
            func.count(Memory.memory_id),
            func.avg(Memory.trust_score),
        ).where(Memory.tenant_id == "default", Memory.status == "active").group_by(Memory.memory_type)
        result = await db.execute(stmt)
        clusters = [{"type": r[0], "count": r[1], "avg_trust": round(r[2], 4) if r[2] else 0} for r in result.fetchall()]
        print(f"[ciraaf] decay={decay_result} trust={trust_result} clusters={clusters}")
    return {"decay": decay_result, "trust": trust_result, "clusters": clusters}


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)

#!/usr/bin/env python3
"""
recompute_trust.py — Full trust recomputation
Cron: weekly Sunday 04:00
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session
from app.services.memory_quality import MemoryQualityService


async def main():
    async with async_session() as db:
        quality = MemoryQualityService(db)
        result = await quality.recompute_all_trust()
        print(f"[recompute_trust] total={result['total']} updated={result['updated']} archived={result['archived']}")
    return result


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)

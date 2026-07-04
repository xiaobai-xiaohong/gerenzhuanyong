#!/usr/bin/env python3
"""
decay_scanner.py — Half-life decay scanner
Cron: daily 02:30
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session
from app.services.memory_quality import MemoryQualityService


async def main():
    async with async_session() as db:
        quality = MemoryQualityService(db)
        result = await quality.scan_and_decay(tenant_id="default")
        print(f"[decay_scanner] scanned={result['scanned']} decayed={result['decayed']} archived={result['archived']}")
    return result


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)

#!/usr/bin/env python3
"""
experience_distiller.py — Pitfall experience distillation
Cron: daily 07:00
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import async_session
from app.models.memory import ToolArchive
from app.services.three_hall import ThreeHallPipeline


async def main():
    async with async_session() as db:
        pipeline = ThreeHallPipeline(db)
        stmt = select(ToolArchive).where(
            ToolArchive.success == "false",
            ToolArchive.related_memory_id.is_(None),
        ).limit(50)
        result = await db.execute(stmt)
        archives = result.scalars().all()
        created = 0
        for arc in archives:
            if arc.result:
                try:
                    memory = await pipeline.process_archive(
                        content=f"[{arc.tool_name}] {arc.result}",
                        content_type="tool_result",
                        category=f"tool/{arc.tool_name}/pitfall",
                        tags=[arc.tool_name, arc.error_type or "unknown_error", "踩坑经验"],
                        session_id=arc.session_id,
                        project_id=arc.project_id,
                        tenant_id="default",
                        source="experience_distiller",
                        memory_type="E",
                        source_authority=2,
                    )
                    arc.related_memory_id = memory.memory_id
                    created += 1
                except ValueError:
                    pass
        await db.commit()
        print(f"[experience_distiller] processed={len(archives)} created={created}")
    return {"processed": len(archives), "created": created}


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)

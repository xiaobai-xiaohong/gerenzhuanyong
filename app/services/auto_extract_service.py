"""
Auto-Extract Service — 后台自动提取对话中的关键事实
对标 duMem 的 auto_memory_background_loop()
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.memory import Memory, WALLog, AuditLog, generate_memory_id, generate_lma
from app.services.llm_service import llm_service
from app.services.vector_service import vector_service
from app.services.social_closer import is_social_closer

settings = get_settings()
logger = logging.getLogger("mnemosyne.auto_extract")


class AutoExtractService:
    """后台自动提取服务"""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """启动后台提取任务"""
        if not settings.auto_extract_enabled:
            logger.info("[AutoExtract] Disabled by config")
            return
        if not llm_service.available:
            logger.warning("[AutoExtract] LLM not configured, auto-extract disabled")
            return
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.warning(f"[AutoExtract] Started (interval={settings.auto_extract_interval}s)")

    async def stop(self):
        """停止后台任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[AutoExtract] Stopped")

    async def _loop(self):
        """主循环：定期检查并提取"""
        while self._running:
            try:
                await self._extract_pending()
            except Exception as e:
                logger.warning(f"[AutoExtract] Loop error: {e}")
            await asyncio.sleep(settings.auto_extract_interval)

    async def _extract_pending(self):
        """检查待提取的对话并处理"""
        async with AsyncSessionLocal() as db:
            # 查找最近的对话记忆（D 类型），尚未被提取
            cutoff = datetime.utcnow() - timedelta(hours=24)
            result = await db.execute(
                select(Memory)
                .where(Memory.memory_type == "D")
                .where(Memory.created_at >= cutoff)
                .where(Memory.status == "active")
                .limit(50)
            )
            conversations = result.scalars().all()

            extracted_count = 0
            for conv in conversations:
                # 跳过太短的内容
                if len(conv.raw_content.strip()) < 20:
                    continue
                # 跳过废话
                if is_social_closer(conv.raw_content):
                    continue

                facts = await llm_service.extract_facts(conv.raw_content)
                for fact in facts:
                    content = fact.get("content", "")
                    memory_type = fact.get("memory_type", "D")
                    tags = fact.get("tags", [])

                    if not content or len(content) < 10:
                        continue

                    # 去重检查（简单关键词匹配）
                    if await self._is_duplicate(db, content):
                        continue

                    await self._archive_fact(
                        db, content, memory_type, tags,
                        source="auto_extract",
                        source_authority=2,
                    )
                    extracted_count += 1

            if extracted_count > 0:
                await db.commit()
                logger.warning(f"[AutoExtract] Extracted {extracted_count} facts from {len(conversations)} conversations")

    async def _is_duplicate(self, db: AsyncSession, content: str) -> bool:
        """简单去重：检查是否已有相似内容"""
        result = await db.execute(
            select(Memory)
            .where(Memory.status == "active")
            .limit(200)
        )
        existing = result.scalars().all()
        content_lower = content.lower()
        for mem in existing:
            if mem.raw_content and content_lower in mem.raw_content.lower():
                return True
            if mem.content_summary and content_lower in mem.content_summary.lower():
                return True
        return False

    async def _archive_fact(
        self,
        db: AsyncSession,
        content: str,
        memory_type: str,
        tags: List[str],
        source: str = "auto_extract",
        source_authority: int = 2,
    ):
        """归档提取的事实"""
        memory_id = generate_memory_id()
        lma_urn = generate_lma()

        initial_trust = 0.3 + source_authority * 0.15
        decay_days_map = {"W": 365, "K": 180, "I": 90, "D": 30, "E": 60, "R": 45, "S": 120}
        decay_days = decay_days_map.get(memory_type, 30)

        vector = await vector_service.embed(content)
        vector_str = vector_service.vector_to_storage(vector)

        memory = Memory(
            memory_id=memory_id,
            content_type="text",
            title=content[:80],
            raw_content=content,
            content_summary=content[:500],
            vector=vector_str,
            category=None,
            tags=tags[:10],
            quality_score=6.0,
            hot_score=1.0,
            level=2,
            storage_medium="ssd",
            timeliness=datetime.utcnow(),
            tenant_id="default",
            status="active",
            version=1,
            lma_urn=lma_urn,
            memory_type=memory_type,
            source_authority=source_authority,
            trust_score=initial_trust,
            decay_at=datetime.utcnow() + timedelta(days=decay_days),
        )
        db.add(memory)
        await db.flush()

        db.add(WALLog(
            op_type="auto_extract",
            target_memory_id=memory_id,
            payload={"source": source},
        ))

    async def extract_from_text(
        self,
        content: str,
        memory_type: str = "D",
        tags: Optional[List[str]] = None,
    ) -> List[dict]:
        """从文本中提取事实并归档（手动触发）"""
        if not llm_service.available:
            return [{"error": "LLM not configured"}]

        facts = await llm_service.extract_facts(content)
        results = []

        async with AsyncSessionLocal() as db:
            for fact in facts:
                fact_content = fact.get("content", "")
                fact_type = fact.get("memory_type", memory_type)
                fact_tags = fact.get("tags", tags or [])

                if not fact_content or len(fact_content) < 10:
                    continue

                if await self._is_duplicate(db, fact_content):
                    results.append({"content": fact_content, "status": "duplicate"})
                    continue

                await self._archive_fact(
                    db, fact_content, fact_type, fact_tags,
                    source="manual_extract",
                    source_authority=3,
                )
                results.append({"content": fact_content, "status": "archived", "memory_type": fact_type})

            await db.commit()

        logger.warning(f"[AutoExtract] Manual extract: {len([r for r in results if r['status'] == 'archived'])} facts")
        return results


auto_extract_service = AutoExtractService()

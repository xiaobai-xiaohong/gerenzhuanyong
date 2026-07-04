"""
Memory Quality Engine — duMem Trust Scoring + Decay Engine
植入 Mnemosyne 三馆闭环的记忆质量层

Trust Scoring:
  - Bayesian 平滑: trust = (trust*n + helpful) / (n+1)
  - 4级权威加成: L1终端+0.3 / L2注入+0.2 / L3文档+0.0 / L4生成-0.1
  - Trust < 0.2 → 自动归档（不参与检索）

Decay:
  - 7种记忆类型对应7种半衰期
  - 铁律(W)永不过期
  - 过期后: 可选归档或直接删除
"""
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.memory import Memory, AuditLog

logger = logging.getLogger(__name__)

# ─── 记忆类型常量 ─────────────────────────────────────────────────────────────

MEMORY_TYPE_HALFLIFE = {
    "W": None,      # 铁律，永不衰减
    "K": 180,        # 工具知识
    "I": 365,        # 人物信息
    "D": 30,         # 对话摘要
    "E": 90,         # 踩坑经验
    "R": 60,         # 反思总结
    "S": 120,        # 研究笔记
}

MEMORY_TYPE_DEFAULT_TRUST = {
    "W": 1.0,
    "K": 0.8,
    "I": 0.7,
    "D": 0.5,
    "E": 0.8,
    "R": 0.6,
    "S": 0.5,
}

# 4级权威加成
AUTHORITY_BONUS = {
    1: 0.3,   # L1 用户终端直接指令
    2: 0.2,   # L2 显式注入/配置
    3: 0.0,   # L3 官方文档
    4: -0.1,  # L4 LLM生成/训练知识
}

BLACKLIST_THRESHOLD = 0.2


class MemoryQualityService:
    """记忆质量引擎：Trust Scoring + Decay"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Trust Scoring ────────────────────────────────────────────────────────

    def compute_initial_trust(
        self,
        memory_type: str,
        source_authority: int = 3,
    ) -> float:
        """计算初始 trust_score"""
        base = MEMORY_TYPE_DEFAULT_TRUST.get(memory_type, 0.5)
        bonus = AUTHORITY_BONUS.get(source_authority, 0.0)
        trust = min(1.0, max(0.0, base + bonus))
        return round(trust, 4)

    async def apply_feedback(
        self,
        memory_id: str,
        helpful: bool,
    ) -> float:
        """
        对记忆应用 feedback，更新 trust_score
        Bayesian 平滑: trust_new = (trust_old * n + helpful) / (n + 1)
        """
        stmt = select(Memory).where(Memory.memory_id == memory_id)
        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()
        if not memory:
            raise ValueError(f"Memory {memory_id} not found")

        n = (memory.helpful_count or 0) + (memory.unhelpful_count or 0)
        current_trust = memory.trust_score or 0.5

        if helpful:
            new_trust = (current_trust * n + 1.0) / (n + 1)
            memory.helpful_count = (memory.helpful_count or 0) + 1
        else:
            new_trust = (current_trust * n + 0.0) / (n + 1)
            memory.unhelpful_count = (memory.unhelpful_count or 0) + 1

        new_trust = round(min(1.0, max(0.0, new_trust)), 4)
        memory.trust_score = new_trust

        # Audit log
        self.db.add(AuditLog(
            memory_id=memory_id,
            operation="trust_feedback",
            operator="memory_quality",
            before_state={"trust": current_trust, "n": n},
            after_state={"trust": new_trust, "helpful": helpful},
            score_change=new_trust - current_trust,
        ))

        await self.db.commit()

        # 如果 trust < BLACKLIST_THRESHOLD，自动归档
        if new_trust < BLACKLIST_THRESHOLD:
            await self._archive_low_trust(memory)

        return new_trust

    async def _archive_low_trust(self, memory: Memory) -> None:
        """Trust < 0.2 的记忆自动归档"""
        memory.status = "archived"
        memory.updated_at = datetime.utcnow()
        logger.warning(f"[MemoryQuality] Memory {memory.memory_id} auto-archived (trust={memory.trust_score})")
        self.db.add(AuditLog(
            memory_id=memory.memory_id,
            operation="auto_archive_low_trust",
            operator="memory_quality",
            after_state={"reason": "trust_below_threshold", "trust": memory.trust_score},
        ))

    async def recompute_all_trust(self) -> dict:
        """
        全量 Trust 重算（供 cron 调用）
        """
        stmt = select(Memory).where(Memory.status == "active")
        result = await self.db.execute(stmt)
        memories = result.scalars().all()

        updated = 0
        archived = 0
        for m in memories:
            old_trust = m.trust_score
            new_trust = self.compute_initial_trust(
                m.memory_type or "D",
                m.source_authority or 3,
            )
            n = (m.helpful_count or 0) + (m.unhelpful_count or 0)
            if n > 0:
                new_trust = (new_trust * n + (m.helpful_count or 0)) / (n + 1)
                new_trust = round(min(1.0, max(0.0, new_trust)), 4)

            m.trust_score = new_trust
            if new_trust < BLACKLIST_THRESHOLD:
                m.status = "archived"
                archived += 1
            updated += 1

        await self.db.commit()
        return {"updated": updated, "archived": archived, "total": len(memories)}

    # ─── Trust Stats ─────────────────────────────────────────────────────────

    async def trust_stats(self, tenant_id: str = "default") -> dict:
        """返回记忆质量统计"""
        stmt = select(
            func.count(Memory.memory_id).label("total"),
            func.avg(Memory.trust_score).label("avg_trust"),
        ).where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
        )
        result = await self.db.execute(stmt)
        row = result.fetchone()

        type_stmt = select(
            Memory.memory_type,
            func.count(Memory.memory_id),
        ).where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
        ).group_by(Memory.memory_type)
        type_result = await self.db.execute(type_stmt)
        type_dist = {r[0]: r[1] for r in type_result.fetchall()}

        low_trust_stmt = select(func.count(Memory.memory_id)).where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
            Memory.trust_score < BLACKLIST_THRESHOLD,
        )
        low_result = await self.db.execute(low_trust_stmt)
        low_count = low_result.scalar() or 0

        return {
            "total": row.total or 0,
            "avg_trust": round(row.avg_trust or 0, 4),
            "low_trust_count": low_count,
            "type_distribution": type_dist,
            "threshold_blacklist": BLACKLIST_THRESHOLD,
        }

    # ─── Decay Engine ────────────────────────────────────────────────────────

    def compute_decay_at(
        self,
        memory_type: str,
        created_at: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """根据记忆类型计算半衰期到期日"""
        halflife_days = MEMORY_TYPE_HALFLIFE.get(memory_type)
        if halflife_days is None:
            return None  # 永不过期（W类）
        if created_at is None:
            created_at = datetime.utcnow()
        decay_at = created_at + timedelta(days=halflife_days)
        return decay_at

    async def scan_and_decay(self, tenant_id: str = "default") -> dict:
        """
        扫描所有到期记忆，执行衰减或归档
        """
        now = datetime.utcnow()
        stmt = select(Memory).where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
            Memory.decay_at.isnot(None),
        )
        result = await self.db.execute(stmt)
        memories = result.scalars().all()

        decayed = 0
        archived = 0
        for m in memories:
            if m.decay_at and m.decay_at <= now:
                mem_type = m.memory_type or "D"
                if mem_type in ("D", "R"):
                    m.status = "archived"
                    archived += 1
                    logger.info(f"[Decay] Archived {m.memory_id} type={mem_type}")
                else:
                    m.trust_score = round((m.trust_score or 0.5) * 0.5, 4)
                    halflife = MEMORY_TYPE_HALFLIFE.get(mem_type, 90)
                    m.decay_at = now + timedelta(days=halflife)
                    m.decay_version = (m.decay_version or 0) + 1
                    decayed += 1
                    logger.info(f"[Decay] Decayed {m.memory_id} trust={m.trust_score}")

                m.updated_at = now
                self.db.add(AuditLog(
                    memory_id=m.memory_id,
                    operation="decay_scan",
                    operator="memory_quality",
                    after_state={"type": mem_type, "trust": m.trust_score, "action": "decayed" if mem_type not in ("D","R") else "archived"},
                ))

        await self.db.commit()
        return {"scanned": len(memories), "decayed": decayed, "archived": archived}

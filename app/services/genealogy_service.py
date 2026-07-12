"""
Knowledge Genealogy — 知识谱系
记录"哪个方案在什么场景下最好"
"""
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, Column, String, Float, JSON, DateTime, Text, Integer
from app.core.database import Base


class KnowledgeGenealogy(Base):
    """知识谱系表"""
    __tablename__ = "knowledge_genealogy"

    id = Column(String(64), primary_key=True, default=lambda: f"genealogy_{uuid.uuid4().hex[:16]}")
    knowledge_id = Column(String(64), nullable=False, index=True)  # 关联的记忆ID
    scenario = Column(String(255), nullable=False, index=True)  # 适用场景
    solution = Column(Text, nullable=False)  # 解决方案
    success_rate = Column(Float, default=0.5)  # 成功率
    use_count = Column(Integer, default=0)  # 使用次数
    success_count = Column(Integer, default=0)  # 成功次数
    environment = Column(JSON, default={})  # 适用环境（OS/硬件/版本等）
    tags = Column(JSON, default=[])  # 标签
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


from sqlalchemy import Integer


class GenealogyService:
    """知识谱系服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_genealogy(
        self,
        knowledge_id: str,
        scenario: str,
        solution: str,
        environment: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """添加知识谱系"""
        genealogy = KnowledgeGenealogy(
            knowledge_id=knowledge_id,
            scenario=scenario,
            solution=solution,
            environment=environment or {},
            tags= tags or [],
        )
        self.db.add(genealogy)
        await self.db.commit()
        return {"id": genealogy.id, "status": "created"}

    async def record_usage(
        self,
        genealogy_id: str,
        success: bool,
    ) -> Dict[str, Any]:
        """记录使用结果"""
        result = await self.db.execute(
            select(KnowledgeGenealogy).where(KnowledgeGenealogy.id == genealogy_id)
        )
        genealogy = result.scalar_one_or_none()
        if not genealogy:
            return {"error": "not found"}

        genealogy.use_count += 1
        if success:
            genealogy.success_count += 1
        genealogy.success_rate = genealogy.success_count / genealogy.use_count
        genealogy.updated_at = datetime.utcnow()
        await self.db.commit()
        return {
            "id": genealogy.id,
            "success_rate": genealogy.success_rate,
            "use_count": genealogy.use_count,
        }

    async def find_best(
        self,
        scenario: str,
        top_k: int = 3,
    ) -> List[Dict]:
        """查找最佳方案"""
        result = await self.db.execute(
            select(KnowledgeGenealogy)
            .where(KnowledgeGenealogy.scenario.contains(scenario))
            .order_by(KnowledgeGenealogy.success_rate.desc())
            .limit(top_k)
        )
        genealogies = result.scalars().all()
        return [{
            "id": g.id,
            "knowledge_id": g.knowledge_id,
            "scenario": g.scenario,
            "solution": g.solution,
            "success_rate": g.success_rate,
            "use_count": g.use_count,
        } for g in genealogies]

    async def get_by_knowledge(self, knowledge_id: str) -> List[Dict]:
        """获取某条知识的所有谱系"""
        result = await self.db.execute(
            select(KnowledgeGenealogy)
            .where(KnowledgeGenealogy.knowledge_id == knowledge_id)
            .order_by(KnowledgeGenealogy.success_rate.desc())
        )
        genealogies = result.scalars().all()
        return [{
            "id": g.id,
            "scenario": g.scenario,
            "solution": g.solution,
            "success_rate": g.success_rate,
            "use_count": g.use_count,
        } for g in genealogies]

    async def stats(self) -> Dict[str, Any]:
        """谱系统计"""
        from sqlalchemy import func
        result = await self.db.execute(
            select(
                func.count(KnowledgeGenealogy.id),
                func.avg(KnowledgeGenealogy.success_rate),
            )
        )
        row = result.one()
        return {
            "total_genealogies": row[0] or 0,
            "avg_success_rate": round(row[1] or 0, 2),
        }

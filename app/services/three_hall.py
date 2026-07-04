"""
Three-Hall Pipeline: Archive馆 → Research馆 → Engineering馆
Implements the core knowledge production流水线 of Mnemosyne v5.2
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.memory import (
    Memory, WALLog, ToolArchive, AuditLog,
    generate_memory_id, generate_lma
)
from app.services.vector_service import vector_service


class ThreeHallPipeline:
    """
    三馆闭环知识生产流水线：

    1. 入馆闸 (Archive馆 Gate0): 规则过滤 + 结构化提取
    2. 研究馆 (Research馆): 多源素材整合 + 知识提炼 + 方案生成
    3. 工程馆 (Engineering馆): 模拟验证（沙盒隔离）
    4. 验收闸 (Archive馆 Gate2): AI自检 + 结果复核 → 正式归档
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_archive(
        self,
        content: str,
        content_type: str = "text",
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tenant_id: str = "default",
        source: str = "api",
        memory_type: str = "D",
        source_authority: int = 3,
    ) -> Memory:
        """
        Execute the full 3-hall pipeline:
        Gate0 (入馆闸) → Research馆 → Engineering馆 → Gate2 (验收闸) → Archive馆

        memory_type: W(铁律)/K(工具)/I(人物)/D(对话)/E(踩坑)/R(反思)/S(研究)
        source_authority: 1=L3文档/2=L2注入/3=L1终端/4=L0 Shell Hook
        """
        memory_id = generate_memory_id()
        lma_urn = generate_lma()

        # ── Gate0: 入馆闸 - 结构化提取 & 规则过滤 ──────────────────
        title = self._extract_title(content)
        summary = await self._gate0_filter(content)
        if summary is None:
            # Filtered out by rules
            raise ValueError("Content filtered by 入馆闸 rules")

        # ── Research馆: 知识提炼 ───────────────────────────────────
        refined_tags = self._refine_tags(content, tags)
        quality_base = self._compute_quality_base(content, category)

        # ── Engineering馆: 模拟验证（记录留痕）─────────────────────
        validation_passed = await self._engineering_validation(content, category)

        # ── Gate2: 验收闸 - 最终确认 ───────────────────────────────
        if not validation_passed:
            # 验收不通过，降级为低置信度
            quality_base *= 0.5

        # ── duMem Trust Scoring: 初始 trust 基于 source_authority ──
        initial_trust = 0.3 + source_authority * 0.15  # 0.45~0.9

        # ── duMem Decay: 计算衰减时间 ──────────────────────────────
        decay_days_map = {"W": 365, "K": 180, "I": 90, "D": 30, "E": 60, "R": 45, "S": 120}
        decay_days = decay_days_map.get(memory_type, 30)
        decay_at = datetime.utcnow() + timedelta(days=decay_days)

        # ── 生成向量 ──────────────────────────────────────────────
        vector = await vector_service.embed(content)
        vector_str = vector_service.vector_to_storage(vector)

        # ── 写入档案馆 ─────────────────────────────────────────────
        memory = Memory(
            memory_id=memory_id,
            content_type=content_type,
            title=title,
            raw_content=content,
            content_summary=summary,
            vector=vector_str,
            category=category,
            tags=refined_tags,
            quality_score=quality_base,
            hot_score=1.0,
            level=2,
            storage_medium="ssd",
            timeliness=datetime.utcnow(),
            tenant_id=tenant_id,
            status="active",
            version=1,
            lma_urn=lma_urn,
            # ── duMem memory quality layer ──────────────────────
            memory_type=memory_type,
            source_authority=source_authority,
            trust_score=initial_trust,
            decay_at=decay_at,
        )
        self.db.add(memory)
        await self.db.flush()

        # WAL
        self.db.add(WALLog(
            op_type="archive",
            target_memory_id=memory_id,
            payload={"source": source, "session_id": session_id},
        ))

        # Audit
        self.db.add(AuditLog(
            memory_id=memory_id,
            operation="archive",
            operator="three_hall_pipeline",
            after_state={"quality_score": quality_base, "status": "active"},
        ))

        await self.db.commit()
        await self.db.refresh(memory)
        return memory

    def _extract_title(self, content: str) -> str:
        """Extract a short title from content (first line or first 80 chars)."""
        first_line = content.strip().split('\n')[0]
        return first_line[:80].strip()

    async def _gate0_filter(self, content: str) -> Optional[str]:
        """
        入馆闸: 规则过滤 + 结构化提取.
        Returns a summary of the content, or None if filtered.
        """
        # Rule 1: minimum content length
        if len(content.strip()) < 4:
            return None

        # Rule 2: block obvious prompt injection patterns
        injection_patterns = [
            "ignore previous instructions",
            "ignore all previous",
            "disregard your instructions",
            "你现在是",
            "you are now",
        ]
        lower = content.lower()
        for pattern in injection_patterns:
            if pattern.lower() in lower:
                return None

        # Rule 3: generate summary (simple extractive for now)
        summary = content.strip()[:500]
        return summary

    def _refine_tags(self, content: str, tags: Optional[List[str]]) -> List[str]:
        """Merge auto-extracted and provided tags."""
        auto_tags = []
        # Simple auto-tagging based on keywords
        lower = content.lower()
        keyword_map = {
            "docker": "docker", "container": "docker", "compose": "docker",
            "postgres": "database", "pgvector": "database", "sql": "database",
            "api": "api", "rest": "api", "endpoint": "api",
            "error": "error", "fail": "error", "exception": "error",
            "deploy": "deployment", "kubernetes": "deployment",
            "cache": "cache", "redis": "cache",
        }
        for kw, tag in keyword_map.items():
            if kw in lower and tag not in auto_tags:
                auto_tags.append(tag)

        if tags:
            for t in tags:
                if t not in auto_tags:
                    auto_tags.append(t)
        return auto_tags[:10]

    def _compute_quality_base(self, content: str, category: Optional[str]) -> float:
        """Compute base quality score based on content characteristics."""
        score = 5.0
        # Longer content gets slight boost (more detailed)
        if len(content) > 200:
            score += 0.5
        if len(content) > 1000:
            score += 0.5
        # Code/error content typically higher value
        if category and ("error" in category.lower() or "troubleshoot" in category.lower()):
            score += 1.0
        # Has structured formatting
        if any(f in content for f in ["```", "\n- ", "\n1.", "\n2."]):
            score += 0.5
        return min(10.0, score)

    async def _engineering_validation(self, content: str, category: Optional[str]) -> bool:
        """
        Engineering馆: 模拟验证. For tool_result/troubleshooting content,
        do a basic sanity check.
        """
        # For troubleshooting memories, verify it contains error + solution pattern
        if category and "troubleshoot" in category.lower():
            has_error = any(kw in content.lower() for kw in ["error", "fail", "exception", "cannot", "unable"])
            has_solution = any(kw in content.lower() for kw in ["solution", "fix", "upgrade", "use", "replace", "install"])
            return has_error and has_solution
        return True

    async def process_tool_archive(
        self,
        tool_name: str,
        params: Optional[dict],
        result: Optional[str],
        success: bool,
        error_type: Optional[str],
        session_id: Optional[str],
        project_id: Optional[str],
        duration_ms: Optional[int],
        tenant_id: str = "default",
    ) -> ToolArchive:
        """Tool result归档: success → skill, failure → pitfall"""
        archive_id = f"tool_arc_{uuid.uuid4().hex[:16]}"
        knowledge_type = "skill" if success else "pitfall"

        # Generate related memory from tool failure
        related_memory_id = None
        if not success and result:
            try:
                memory = await self.process_archive(
                    content=f"[{tool_name}] {result}",
                    content_type="tool_result",
                    category=f"tool/{tool_name}/pitfall",
                    tags=[tool_name, error_type or "unknown_error"],
                    session_id=session_id,
                    project_id=project_id,
                    tenant_id=tenant_id,
                    source="tool_archive",
                )
                related_memory_id = memory.memory_id
            except ValueError:
                pass  # filtered, skip

        archive = ToolArchive(
            archive_id=archive_id,
            tool_name=tool_name,
            params=params,
            result=result,
            success="true" if success else "false",
            error_type=error_type,
            session_id=session_id,
            project_id=project_id,
            duration_ms=duration_ms,
            knowledge_type=knowledge_type,
            related_memory_id=related_memory_id,
        )
        self.db.add(archive)
        await self.db.commit()
        await self.db.refresh(archive)
        return archive

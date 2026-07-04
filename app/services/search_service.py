"""
Triple Recall Engine:
  1. Vector semantic recall (ZVEC/DiskANN equivalent)
  2. Full-text keyword recall
  3. Knowledge-graph lightweight recall (category/tag)

Hybrid scoring formula from whitepaper:
  Score_final = w1·Sim_vector + w2·Q_quality + w3·Shot + w4·T_timeliness
"""
import json
import time
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from app.models.memory import Memory, AuditLog
from app.services.vector_service import vector_service


class SearchService:
    # Weights from whitepaper
    W_VECTOR = 0.50
    W_QUALITY = 0.20
    W_HOT = 0.20
    W_TIMELINESS = 0.10

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        query: str,
        depth: str = "auto",
        top_k: int = 5,
        category_filter: Optional[List[str]] = None,
        quality_min: float = 0.0,
        tenant_id: str = "default",
    ) -> Tuple[str, List[dict]]:
        """
        Execute triple recall and return (depth_used, results).
        """
        # Determine actual recall depth
        depth_used = self._resolve_depth(depth, top_k)

        # Get query vector
        query_vec = await vector_service.embed(query)

        # ── Layer 1: Vector semantic recall ────────────────────────
        vector_candidates = await self._vector_recall(query_vec, tenant_id, top_k * 4)

        # ── Layer 2: Full-text keyword recall ───────────────────────
        text_candidates = await self._text_recall(query, tenant_id, top_k * 3)

        # ── Layer 3: Merge + score ──────────────────────────────────
        candidate_ids = set(v["memory_id"] for v in vector_candidates) | set(t["memory_id"] for t in text_candidates)

        scored = []
        for cid in candidate_ids:
            result = await self._fetch_and_score(
                cid, query, query_vec, tenant_id, quality_min, category_filter, depth_used
            )
            if result:
                scored.append(result)

        # Sort by final score descending
        scored.sort(key=lambda x: x["final_score"], reverse=True)
        results = scored[:top_k]

        # Audit log
        for r in results:
            self.db.add(AuditLog(
                memory_id=r["memory_id"],
                operation="search_recall",
                operator="search_service",
                after_state={"depth": depth_used, "query": query[:100], "final_score": r["final_score"]},
            ))
        await self.db.commit()

        return depth_used, results

    def _resolve_depth(self, depth: str, top_k: int) -> str:
        if depth != "auto":
            return depth
        if top_k <= 3:
            return "L0"
        elif top_k <= 10:
            return "L1"
        return "L2"

    async def _vector_recall(
        self, query_vec: List[float], tenant_id: str, limit: int
    ) -> List[dict]:
        """
        Vector similarity recall.
        Since we don't have pgvector extension installed,
        we fetch all active memories and compute similarity in Python.
        For production, use SQL similarity functions or plug in pgvector.
        """
        stmt = select(Memory).where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
            Memory.vector.isnot(None),
        ).limit(limit * 5)  # over-fetch, filter in Python

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        scored = []
        for row in rows:
            try:
                vec = vector_service.vector_from_storage(row.vector)
                sim = vector_service.cosine_sim(query_vec, vec)
            except Exception:
                sim = 0.0
            if sim > 0.1:
                scored.append({
                    "memory_id": row.memory_id,
                    "sim": sim,
                    "row": row,
                })

        scored.sort(key=lambda x: x["sim"], reverse=True)
        return scored[:limit]

    async def _text_recall(
        self, query: str, tenant_id: str, limit: int
    ) -> List[dict]:
        """Full-text recall via LIKE matching on title and raw_content."""
        pattern = f"%{query}%"
        stmt = select(Memory).where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
            or_(
                Memory.title.ilike(pattern),
                Memory.raw_content.ilike(pattern),
                Memory.content_summary.ilike(pattern),
            ),
        ).limit(limit)

        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [
            {"memory_id": row.memory_id, "text_hit": True, "row": row}
            for row in rows
        ]

    async def _fetch_and_score(
        self,
        memory_id: str,
        query: str,
        query_vec: List[float],
        tenant_id: str,
        quality_min: float,
        category_filter: Optional[List[str]],
        depth: str,
    ) -> Optional[dict]:
        stmt = select(Memory).where(
            Memory.memory_id == memory_id,
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None

        # Quality filter
        if row.quality_score < quality_min:
            return None

        # Category filter
        if category_filter and row.category not in category_filter:
            return None

        # ── Compute score components ──────────────────────────────
        try:
            vec = vector_service.vector_from_storage(row.vector)
            sim_vector = vector_service.cosine_sim(query_vec, vec)
        except Exception:
            sim_vector = 0.0

        q_quality = row.quality_score / 10.0
        w_hot = min(1.0, row.hot_score / 10.0)
        w_timeliness = self._timeliness_score(row)

        score_final = (
            self.W_VECTOR * sim_vector
            + self.W_QUALITY * q_quality
            + self.W_HOT * w_hot
            + self.W_TIMELINESS * w_timeliness
        )

        # ── Depth-specific content ────────────────────────────────
        if depth == "L0":
            summary = row.content_summary[:200] if row.content_summary else ""
            title = row.title or ""
        elif depth == "L1":
            summary = row.content_summary or ""
            title = row.title or ""
        else:  # L2 full
            summary = row.raw_content or row.content_summary or ""
            title = row.title or ""

        return {
            "memory_id": row.memory_id,
            "title": title[:120],
            "summary": summary[:300],
            "content_type": row.content_type,
            "category": row.category,
            "tags": row.tags or [],
            "final_score": round(score_final, 4),
            "score_detail": {
                "vector_similarity": round(sim_vector, 4),
                "quality_score": round(q_quality, 4),
                "hot_score": round(w_hot, 4),
                "timeliness": round(w_timeliness, 4),
            },
            "level": row.level,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            # duMem memory quality layer
            "trust_score": row.trust_score,
            "memory_type": getattr(row, "memory_type", "D"),
        }

    def _timeliness_score(self, row) -> float:
        """Timeliness: newer content scores higher, decaying over 90 days."""
        if not row.updated_at:
            return 0.5
        age_days = (time.time() - row.updated_at.timestamp()) / 86400
        return max(0.1, 1.0 - age_days / 90.0)

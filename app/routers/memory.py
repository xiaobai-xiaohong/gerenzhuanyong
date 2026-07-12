import uuid
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.config import get_settings
from app.schemas.memory import (
    APIResponse, MemoryArchiveRequest,
    MemorySearchRequest, ToolArchiveRequest,
    ProjectCreateRequest, ProfileUpdateRequest,
    SyncPullRequest, SyncPushRequest,
)
from app.services.three_hall import ThreeHallPipeline
from app.services.search_service import SearchService
from app.services.inject_service import InjectService
from app.services.memory_quality import MemoryQualityService
from app.services.dedup_engine import dedup_report
from app.models.memory import Memory, Project, AgentProfile, SyncVersion

router = APIRouter()
_request_id = "req_" + uuid.uuid4().hex[:12]
settings = get_settings()


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """API Key 认证（可选，通过 MNEMOSYNE_API_KEY 配置）"""
    if settings.api_key and settings.api_key != "mnemosyne-api-key-change-me":
        if not x_api_key or x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")


def api_response(data, message="success", code=0, request_id: Optional[str] = None):
    return {
        "code": code,
        "message": message,
        "data": data,
        "request_id": request_id or (_request_id + str(int(time.time() * 1000))),
    }


def _get_request_id():
    return "req_" + uuid.uuid4().hex[:12]


# ─── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "version": "6.0.0", "service": "mnemosyne-core"}


@router.get("/api/v5/health/full")
async def health_full(db: AsyncSession = Depends(get_db)):
    quality = MemoryQualityService(db)
    stats = await quality.trust_stats()
    return api_response({
        "status": "ok",
        "version": "6.0.0",
        "service": "mnemosyne-core",
        "memory_stats": stats,
        "features": ["trust_scoring", "social_closer", "jaccard_dedup", "decay", "7_memory_types"],
    })


# ─── Memory Archive ────────────────────────────────────────────────────────────

@router.post("/api/v5/memory/archive", response_model=APIResponse)
async def memory_archive(
    req: MemoryArchiveRequest,
    x_tenant_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    rid = _get_request_id()
    tenant_id = x_tenant_id or req.tenant_id
    pipeline = ThreeHallPipeline(db)
    try:
        memory = await pipeline.process_archive(
            content=req.content,
            content_type=req.content_type,
            category=req.category,
            tags=req.tags,
            session_id=req.session_id,
            project_id=req.project_id,
            tenant_id=tenant_id,
            source=req.source or "api",
            memory_type=getattr(req, "memory_type", "D"),
            source_authority=getattr(req, "source_authority", 3),
        )
        return api_response({
            "memory_id": memory.memory_id,
            "status": "success",
            "trust_score": memory.trust_score,
            "memory_type": memory.memory_type,
            "decay_at": memory.decay_at.isoformat() if memory.decay_at else None,
        }, request_id=rid)
    except ValueError as e:
        return api_response(
            {"memory_id": None, "status": "failed", "estimated_time": 0},
            message=str(e), code=40001, request_id=rid,
        )
    except Exception as e:
        return api_response(
            {"memory_id": None, "status": "failed", "estimated_time": 0},
            message=f"Internal error: {e}", code=50001, request_id=rid,
        )


# ─── Memory Search ────────────────────────────────────────────────────────────

@router.post("/api/v5/memory/search", response_model=APIResponse)
async def memory_search(
    req: MemorySearchRequest,
    x_tenant_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    rid = _get_request_id()
    tenant_id = x_tenant_id or req.tenant_id
    search = SearchService(db)
    try:
        depth_used, results = await search.search(
            query=req.query, depth=req.depth, top_k=req.top_k,
            category_filter=req.category_filter, quality_min=req.quality_min,
            tenant_id=tenant_id,
        )
        return api_response({
            "depth_used": depth_used,
            "total": len(results),
            "results": [
                {
                    "memory_id": r["memory_id"], "title": r["title"], "summary": r["summary"],
                    "content_type": r["content_type"], "category": r["category"],
                    "tags": r["tags"], "final_score": r["final_score"],
                    "score_detail": r["score_detail"], "level": r["level"],
                    "memory_type": r.get("memory_type", "D"),
                    "trust_score": r.get("trust_score", 0.0),
                    "updated_at": r["updated_at"],
                }
                for r in results
            ],
        }, request_id=rid)
    except Exception as e:
        return api_response(None, message=str(e), code=50001, request_id=rid)


# ─── Inject Context (pre-LLM hook) ────────────────────────────────────────────

@router.post("/api/v5/memory/inject-context")
async def inject_context(
    query: str,
    depth: str = "auto",
    top_k: int = 5,
    x_tenant_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """pre-LLM Hook 注入端点"""
    rid = _get_request_id()
    tenant_id = x_tenant_id or "default"
    try:
        service = InjectService(db)
        result = await service.inject(query=query, depth=depth, top_k=top_k, tenant_id=tenant_id)
        return api_response(result, request_id=rid)
    except Exception as e:
        return api_response(None, message=str(e), code=50001, request_id=rid)


# ─── Trust Feedback ────────────────────────────────────────────────────────────

@router.post("/api/v5/memory/feedback")
async def memory_feedback(
    memory_id: str,
    helpful: bool,
    x_tenant_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """对记忆提交反馈，驱动 trust 调整"""
    rid = _get_request_id()
    quality = MemoryQualityService(db)
    try:
        new_trust = await quality.apply_feedback(memory_id, helpful)
        return api_response({"memory_id": memory_id, "new_trust": new_trust, "helpful": helpful}, request_id=rid)
    except ValueError as e:
        return api_response(None, message=str(e), code=40401, request_id=rid)
    except Exception as e:
        return api_response(None, message=str(e), code=50001, request_id=rid)


# ─── Trust Stats ───────────────────────────────────────────────────────────────

@router.get("/api/v5/memory/trust-stats")
async def trust_stats(x_tenant_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    quality = MemoryQualityService(db)
    return api_response(await quality.trust_stats(x_tenant_id or "default"), request_id=rid)


# ─── Decay Scan ───────────────────────────────────────────────────────────────

@router.post("/api/v5/memory/decay")
async def decay_scan(x_tenant_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    quality = MemoryQualityService(db)
    return api_response(await quality.scan_and_decay(x_tenant_id or "default"), request_id=rid)


# ─── Dedup Report ─────────────────────────────────────────────────────────────

@router.get("/api/v5/memory/dedup-report")
async def dedup_report_endpoint(x_tenant_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    tenant_id = x_tenant_id or "default"
    stmt = Memory.__table__.select().where(Memory.tenant_id == tenant_id, Memory.status == "active")
    result = await db.execute(stmt)
    rows = result.fetchall()
    contents = [r.raw_content for r in rows if r.raw_content]
    titles = [r.title for r in rows if r.title]
    return api_response(dedup_report(contents, titles), request_id=rid)


# ─── CIRAAF Maintenance ──────────────────────────────────────────────────────

@router.post("/api/v5/maintenance/ciraaf")
async def ciraaf_maintenance(x_tenant_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    tenant_id = x_tenant_id or "default"
    quality = MemoryQualityService(db)
    dedup_result = await quality.scan_and_decay(tenant_id)
    trust_result = await quality.recompute_all_trust()
    return api_response({
        "ciraaf_status": "completed",
        "decay_scan": dedup_result,
        "trust_recompute": trust_result,
        "next_run": "next Sunday 03:30",
    }, request_id=rid)


# ─── Memory Detail ────────────────────────────────────────────────────────────

@router.get("/api/v5/memory/{memory_id}", response_model=APIResponse)
async def memory_detail(memory_id: str, x_tenant_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    tenant_id = x_tenant_id or "default"
    stmt = Memory.__table__.select().where(Memory.memory_id == memory_id, Memory.tenant_id == tenant_id)
    result = await db.execute(stmt)
    row = result.fetchone()
    if not row:
        return api_response(None, message="Memory not found", code=40401, request_id=rid)
    return api_response({
        "memory_id": row.memory_id, "title": row.title, "raw_content": row.raw_content,
        "content_summary": row.content_summary, "category": row.category, "tags": row.tags or [],
        "quality_score": row.quality_score, "level": row.level, "status": row.status,
        "trust_score": row.trust_score, "memory_type": row.memory_type,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }, request_id=rid)


# ─── Tool Archive ─────────────────────────────────────────────────────────────

@router.post("/api/v5/tool/archive", response_model=APIResponse)
async def tool_archive(req: ToolArchiveRequest, x_tenant_id: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    tenant_id = x_tenant_id or "default"
    pipeline = ThreeHallPipeline(db)
    archive = await pipeline.process_tool_archive(
        tool_name=req.tool_name, params=req.params, result=req.result,
        success=req.success, error_type=req.error_type,
        session_id=req.session_id, project_id=req.project_id,
        duration_ms=req.duration_ms, tenant_id=tenant_id,
    )
    return api_response({
        "archive_id": archive.archive_id, "knowledge_type": archive.knowledge_type,
        "related_memory_id": archive.related_memory_id,
    }, request_id=rid)


# ─── Project ──────────────────────────────────────────────────────────────────

@router.post("/api/v5/project/create", response_model=APIResponse)
async def project_create(req: ProjectCreateRequest, db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    import uuid as uuid_mod
    project_id = f"proj_{uuid_mod.uuid4().hex[:16]}"
    project = Project(project_id=project_id, name=req.name, description=req.description, tenant_id=req.tenant_id)
    db.add(project)
    await db.commit()
    return api_response({"project_id": project_id, "name": req.name, "status": "active"}, request_id=rid)


@router.get("/api/v5/project/{project_id}", response_model=APIResponse)
async def project_get(project_id: str, db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    stmt = Project.__table__.select().where(Project.project_id == project_id)
    result = await db.execute(stmt)
    row = result.fetchone()
    if not row:
        return api_response(None, message="Project not found", code=40401, request_id=rid)
    return api_response({
        "project_id": row.project_id, "name": row.name, "description": row.description,
        "status": row.status, "created_at": row.created_at.isoformat() if row.created_at else None,
    }, request_id=rid)


@router.post("/api/v5/project/{project_id}/archive", response_model=APIResponse)
async def project_archive(project_id: str, db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    stmt = Project.__table__.select().where(Project.project_id == project_id)
    result = await db.execute(stmt)
    row = result.fetchone()
    if not row:
        return api_response(None, message="Project not found", code=40401, request_id=rid)
    await db.execute(Project.__table__.update().where(Project.project_id == project_id).values(
        status="archived", archived_at=datetime.utcnow()))
    await db.commit()
    return api_response({"project_id": project_id, "status": "archived"}, request_id=rid)


@router.post("/api/v5/project/{project_id}/destroy", response_model=APIResponse)
async def project_destroy(project_id: str, db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    await db.execute(Project.__table__.update().where(Project.project_id == project_id).values(status="destroyed"))
    await db.commit()
    return api_response({"project_id": project_id, "status": "destroyed"}, request_id=rid)


# ─── Profile ───────────────────────────────────────────────────────────────────

@router.get("/api/v5/profile", response_model=APIResponse)
async def profile_get(agent_id: str = "hermes-main", db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    stmt = AgentProfile.__table__.select().where(AgentProfile.agent_id == agent_id)
    result = await db.execute(stmt)
    row = result.fetchone()
    if not row:
        profile = AgentProfile(agent_id=agent_id, decision_level="L0")
        db.add(profile)
        await db.commit()
        return api_response({"agent_id": agent_id, "decision_level": "L0", "preferences": {}, "attributes": {}}, request_id=rid)
    return api_response({
        "agent_id": row.agent_id, "decision_level": row.decision_level,
        "preferences": row.preferences or {}, "attributes": row.attributes or {},
    }, request_id=rid)


@router.put("/api/v5/profile", response_model=APIResponse)
async def profile_update(req: ProfileUpdateRequest, agent_id: str = "hermes-main", db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    stmt = AgentProfile.__table__.select().where(AgentProfile.agent_id == agent_id)
    result = await db.execute(stmt)
    row = result.fetchone()
    if row:
        updates = {}
        if req.decision_level is not None: updates["decision_level"] = req.decision_level
        if req.preferences is not None: updates["preferences"] = req.preferences
        if req.attributes is not None: updates["attributes"] = req.attributes
        if updates:
            await db.execute(AgentProfile.__table__.update().where(AgentProfile.agent_id == agent_id).values(**updates))
        await db.commit()
    else:
        profile = AgentProfile(agent_id=agent_id, decision_level=req.decision_level or "L0",
                              preferences=req.preferences or {}, attributes=req.attributes or {})
        db.add(profile)
        await db.commit()
    return api_response({"agent_id": agent_id, "status": "updated"}, request_id=rid)


# ─── Sync ─────────────────────────────────────────────────────────────────────

@router.post("/api/v5/sync/pull", response_model=APIResponse)
async def sync_pull(req: SyncPullRequest, db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    stmt = SyncVersion.__table__.select().where(
        SyncVersion.tenant_id == req.tenant_id, SyncVersion.version > req.last_version,
    ).order_by(SyncVersion.version).limit(100)
    result = await db.execute(stmt)
    rows = result.fetchall()
    changes = []
    max_ver = req.last_version
    for row in rows:
        changes.append({"entity_type": row.entity_type, "entity_id": row.entity_id,
                        "version": row.version, "operation": row.operation, "payload": row.payload})
        max_ver = max(max_ver, row.version)
    return api_response({"current_version": max_ver, "changes": changes, "has_more": len(changes) == 100}, request_id=rid)


@router.post("/api/v5/sync/push", response_model=APIResponse)
async def sync_push(req: SyncPushRequest, db: AsyncSession = Depends(get_db)):
    rid = _get_request_id()
    from sqlalchemy import func as sa_func
    stmt = db.query(sa_func.max(SyncVersion.version)).where(SyncVersion.tenant_id == req.tenant_id)
    result = await db.execute(stmt)
    max_ver = result.scalar() or 0
    for change in req.changes:
        max_ver += 1
        sv = SyncVersion(tenant_id=req.tenant_id, entity_type=change.get("entity_type", "memory"),
                         entity_id=change.get("entity_id", ""), version=max_ver,
                         operation=change.get("operation", "create"), payload=change.get("payload"))
        db.add(sv)
    await db.commit()
    return api_response({"accepted": len(req.changes), "current_version": max_ver}, request_id=rid)


# ─── Inject (Shell Hook) ────────────────────────────────────────────────────

@router.post("/api/v5/memory/inject", response_model=APIResponse)
async def memory_inject(
    query: str = "",
    depth: str = "L0",
    top_k: int = 5,
    x_tenant_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    """Shell Hook 注入：返回格式化的记忆上下文，供 LLM pre_llm_call 使用"""
    rid = _get_request_id()
    tenant_id = x_tenant_id or "default"
    inject_service = InjectService(db)
    try:
        context = await inject_service.inject_context(
            query=query, depth=depth, top_k=top_k, tenant_id=tenant_id
        )
        return api_response(context, request_id=rid)
    except Exception as e:
        return api_response({"context": "", "error": str(e)}, code=50001, request_id=rid)


# ─── Auto Extract ───────────────────────────────────────────────────────────

from app.services.auto_extract_service import auto_extract_service

@router.post("/api/v5/memory/extract", response_model=APIResponse)
async def memory_extract(
    content: str,
    memory_type: str = "D",
    tags: Optional[str] = None,
    _: None = Depends(verify_api_key),
):
    """手动触发 LLM 提取：从文本中自动提取关键事实并归档"""
    rid = _get_request_id()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    results = await auto_extract_service.extract_from_text(
        content=content, memory_type=memory_type, tags=tag_list
    )
    archived = [r for r in results if r.get("status") == "archived"]
    return api_response({
        "total": len(results),
        "archived": len(archived),
        "results": results,
    }, request_id=rid)


@router.get("/api/v5/memory/extract/status")
async def extract_status():
    """查看自动提取服务状态"""
    return api_response({
        "enabled": auto_extract_service._running,
        "llm_available": auto_extract_service._running,
    })

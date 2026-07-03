from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# ─── Common ─────────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None
    request_id: Optional[str] = None


# ─── Memory Archive ──────────────────────────────────────────────────────────

class MemoryArchiveRequest(BaseModel):
    content: str
    content_type: str = "text"
    memory_type: Optional[str] = "general"
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    tenant_id: str = "default"
    source: Optional[str] = "api"


class MemoryArchiveData(BaseModel):
    memory_id: str
    status: str  # processing / success / failed
    estimated_time: int


# ─── Memory Search ────────────────────────────────────────────────────────────

class MemorySearchRequest(BaseModel):
    query: str
    depth: str = "auto"  # auto / L0 / L1 / L2
    top_k: int = 5
    category_filter: Optional[List[str]] = None
    quality_min: float = 0.0
    tenant_id: str = "default"
    return_detail: bool = False


class ScoreDetail(BaseModel):
    vector_similarity: float
    quality_score: float
    hot_score: float
    timeliness: float


class SearchResult(BaseModel):
    memory_id: str
    title: Optional[str]
    summary: Optional[str]
    content_type: str
    category: Optional[str]
    tags: Optional[List[str]]
    final_score: float
    score_detail: ScoreDetail
    level: int
    updated_at: Optional[str]


class MemorySearchData(BaseModel):
    depth_used: str
    total: int
    results: List[SearchResult]


# ─── Tool Archive ─────────────────────────────────────────────────────────────

class ToolArchiveRequest(BaseModel):
    tool_name: str
    params: Optional[dict] = None
    result: Optional[str] = None
    success: bool
    error_type: Optional[str] = None
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    duration_ms: Optional[int] = None


class ToolArchiveData(BaseModel):
    archive_id: str
    knowledge_type: str  # skill / pitfall
    related_memory_id: Optional[str]


# ─── Project ──────────────────────────────────────────────────────────────────

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tenant_id: str = "default"


class ProjectData(BaseModel):
    project_id: str
    name: str
    description: Optional[str]
    status: str
    created_at: Optional[str]


# ─── Profile ──────────────────────────────────────────────────────────────────

class ProfileData(BaseModel):
    agent_id: str
    decision_level: str
    preferences: dict
    attributes: dict


class ProfileUpdateRequest(BaseModel):
    decision_level: Optional[str] = None
    preferences: Optional[dict] = None
    attributes: Optional[dict] = None


# ─── Sync ─────────────────────────────────────────────────────────────────────

class SyncPullRequest(BaseModel):
    tenant_id: str = "default"
    last_version: int = 0
    entity_type: Optional[str] = None


class SyncPullData(BaseModel):
    current_version: int
    changes: List[dict]
    has_more: bool


class SyncPushRequest(BaseModel):
    tenant_id: str = "default"
    changes: List[dict]


class SyncResolveRequest(BaseModel):
    tenant_id: str = "default"
    conflicts: List[dict]

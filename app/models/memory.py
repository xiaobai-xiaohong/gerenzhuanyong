import uuid
import secrets
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Float, Integer, SmallInteger,
    DateTime, Index, JSON, BigInteger, text
)
from app.core.database import Base


def generate_memory_id() -> str:
    return f"mem_{uuid.uuid4().hex[:16]}"

def generate_archive_id() -> str:
    return f"tool_arc_{uuid.uuid4().hex[:16]}"

def generate_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:16]}"

def generate_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:16]}"

def generate_lma() -> str:
    return f"lma://mnemosyne/{uuid.uuid4().urn[9:]}"


class Memory(Base):
    __tablename__ = "memories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    memory_id = Column(String(64), unique=True, nullable=False, default=generate_memory_id)
    content_type = Column(String(32), nullable=False, default="text")
    title = Column(String(255), nullable=True)
    raw_content = Column(Text, nullable=True)
    content_summary = Column(Text, nullable=True)
    vector = Column("vector", Text, nullable=True)  # stored as JSON string
    category = Column(String(64), nullable=True)
    tags = Column(JSON, nullable=True)
    quality_score = Column(Float, default=5.0)
    hot_score = Column(Float, default=1.0)
    level = Column(SmallInteger, default=2)
    storage_medium = Column(String(16), default="ssd")
    timeliness = Column(DateTime, nullable=True)
    tenant_id = Column(String(64), default="default")
    status = Column(String(16), default="active")  # active/processing/failed/archived
    version = Column(Integer, default=1)
    lma_urn = Column(String(128), unique=True, nullable=False, default=generate_lma)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_access_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_memories_category", "category"),
        Index("ix_memories_tenant", "tenant_id"),
        Index("ix_memories_status", "status"),
    )


class WALLog(Base):
    __tablename__ = "wal_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    op_type = Column(String(32), nullable=False)
    target_memory_id = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=True)
    checkpoint_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(String(64), unique=True, nullable=False)
    tenant_id = Column(String(64), default="default")
    preferences = Column(JSON, default=dict)
    attributes = Column(JSON, default=dict)
    confidence = Column(JSON, default=dict)
    decision_level = Column(String(16), default="L0")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    memory_id = Column(String(64), nullable=False)
    operation = Column(String(32), nullable=False)
    operator = Column(String(64), nullable=False)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    score_change = Column(Float, nullable=True)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ToolArchive(Base):
    __tablename__ = "tool_archives"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    archive_id = Column(String(64), unique=True, nullable=False, default=generate_archive_id)
    tool_name = Column(String(128), nullable=False)
    params = Column(JSON, nullable=True)
    result = Column(Text, nullable=True)
    success = Column(String(8), nullable=False)  # "true" / "false"
    error_type = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=True)
    project_id = Column(String(64), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    knowledge_type = Column(String(32), default="skill")  # skill/pitfall
    related_memory_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(String(64), unique=True, nullable=False, default=generate_project_id)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tenant_id = Column(String(64), default="default")
    status = Column(String(16), default="active")  # active/archived/destroyed
    session_ids = Column(JSON, default=list)
    memory_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)


class SyncVersion(Base):
    __tablename__ = "sync_versions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), default="default")
    entity_type = Column(String(32), nullable=False)  # memory/project/profile
    entity_id = Column(String(64), nullable=False)
    version = Column(BigInteger, nullable=False)
    operation = Column(String(16), nullable=False)  # create/update/delete
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

#!/usr/bin/env python3
"""
migrate_v6.py — 添加 v6.0 新字段到已有数据库
一次性迁移，无需回滚（新增列+默认值）
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import async_engine


async def migrate():
    async with async_engine.connect() as conn:
        # 检查 trust_score 列是否已存在
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'memories' AND column_name = 'trust_score'
        """))
        if result.fetchone():
            print("[migrate_v6] trust_score already exists, skipping")
        else:
            print("[migrate_v6] adding columns to memories table...")
            await conn.execute(text("""
                ALTER TABLE memories
                ADD COLUMN IF NOT EXISTS trust_score FLOAT DEFAULT 0.5,
                ADD COLUMN IF NOT EXISTS source_authority SMALLINT DEFAULT 3,
                ADD COLUMN IF NOT EXISTS decay_at TIMESTAMP NULL,
                ADD COLUMN IF NOT EXISTS memory_type VARCHAR(8) DEFAULT 'D',
                ADD COLUMN IF NOT EXISTS helpful_count INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS unhelpful_count INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS is_semantic_deduped SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS decay_version INTEGER DEFAULT 0;
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_memories_decay_at ON memories(decay_at);
                CREATE INDEX IF NOT EXISTS ix_memories_type ON memories(memory_type);
            """))
            await conn.commit()
            print("[migrate_v6] columns added successfully")

        # 初始化 decay_at（为已有活跃记忆设置 decay_at）
        result2 = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'memories' AND column_name = 'decay_at'
        """))
        if result2.fetchone():
            # 只更新那些 decay_at 为 NULL 的记录
            update_result = await conn.execute(text("""
                UPDATE memories SET decay_at = updated_at + INTERVAL '30 days'
                WHERE status = 'active' AND decay_at IS NULL;
            """))
            await conn.commit()
            print(f"[migrate_v6] initialized decay_at for existing memories")

        # 创建 audit_log 表（如果不存在）
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id BIGSERIAL PRIMARY KEY,
                memory_id VARCHAR(64) NOT NULL,
                operation VARCHAR(32) NOT NULL,
                operator VARCHAR(64) NOT NULL,
                before_state JSONB,
                after_state JSONB,
                score_change FLOAT,
                remark TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))
        await conn.commit()
        print("[migrate_v6] audit_log table ready")
        print("[migrate_v6] migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
    sys.exit(0)

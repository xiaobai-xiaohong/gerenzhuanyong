import asyncio, sys
sys.path.insert(0, '/app')

from sqlalchemy import text
from app.core.database import async_engine


async def migrate():
    async with async_engine.connect() as conn:
        r = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'memories' AND column_name = 'trust_score'"
        ))
        if r.fetchone():
            print("[migrate] trust_score already exists, skipping")
        else:
            print("[migrate] adding columns to memories table...")
            await conn.execute(text("""
                ALTER TABLE memories
                ADD COLUMN IF NOT EXISTS trust_score FLOAT DEFAULT 0.5,
                ADD COLUMN IF NOT EXISTS source_authority SMALLINT DEFAULT 3,
                ADD COLUMN IF NOT EXISTS decay_at TIMESTAMP NULL,
                ADD COLUMN IF NOT EXISTS memory_type VARCHAR(8) DEFAULT 'D',
                ADD COLUMN IF NOT EXISTS helpful_count INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS unhelpful_count INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS is_semantic_deduped SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS decay_version INTEGER DEFAULT 0
            """))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_memories_decay_at ON memories(decay_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_memories_type ON memories(memory_type)"))
            await conn.execute(text("UPDATE memories SET decay_at = updated_at + INTERVAL '30 days' WHERE status = 'active' AND decay_at IS NULL"))
            await conn.commit()
            print("[migrate] columns added successfully")

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
            )
        """))
        await conn.commit()
        print("[migrate] audit_log table ready")
        print("[migrate] done!")


asyncio.run(migrate())

import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.routers.memory import router
from app.core.database import async_engine, Base
from app.core.config import get_settings

# Configure logging so WARNING+ goes to stdout (container log)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("mnemosyne")

settings = get_settings()


async def init_db():
    """Initialize database tables and pgvector extension."""
    from sqlalchemy import text
    async with async_engine.begin() as conn:
        # Enable pgvector extension
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass  # Extension may not exist in all PostgreSQL builds
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    # Start auto-extract service
    from app.services.auto_extract_service import auto_extract_service
    await auto_extract_service.start()
    yield
    # Shutdown
    from app.services.auto_extract_service import auto_extract_service
    await auto_extract_service.stop()
    await async_engine.dispose()


app = FastAPI(
    title="Mnemosyne v5.2",
    description="Cognitive Memory Operating System",
    version="5.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "Mnemosyne v5.2",
        "version": "5.2.0",
        "status": "running",
    }

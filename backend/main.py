from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router as api_router
from app.logging_config import logger
from app.config import settings
from app.database import Base, engine
import app.modules.media.models  # Enforce metadata registration

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle actions
    logger.info("====================================================")
    logger.info(f"PhotoMind AI Backend starting in {settings.ENV_MODE} mode.")
    logger.info(f"Storage path initialized at: {settings.STORAGE_PATH}")
    logger.info("====================================================")
    
    # Initialize PostgreSQL tables asynchronously
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from sqlalchemy import text
        await conn.execute(text("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;"))
        await conn.execute(text("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE NULL;"))
        await conn.execute(text("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS deleted_from VARCHAR(255) NULL;"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_media_assets_is_deleted ON media_assets (is_deleted);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_media_assets_deleted_at ON media_assets (deleted_at);"))
    logger.info("Database tables & soft deletion columns initialized successfully.")
    
    yield
    
    # Shutdown lifecycle actions
    logger.info("PhotoMind AI Backend shutting down.")

# Initialize FastAPI application with lifespan context manager
app = FastAPI(
    title="PhotoMind AI Backend",
    description="Multimodal Personal Memory Assistant API Service",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production security if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register central routers
app.include_router(api_router, prefix="/api")

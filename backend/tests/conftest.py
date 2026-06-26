import os
import shutil
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from qdrant_client import QdrantClient

# 1. Override env configs before importing app modules
os.environ["STORAGE_PATH"] = "./test_storage"
os.environ["LOG_LEVEL"] = "WARNING"

# 2. Initialize in-memory SQLite for test database
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
test_session_local = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. Patch app.database module parameters to direct writes to test SQLite engine
import app.database
app.database.async_session = test_session_local
app.database.engine = test_engine

# 4. Patch app.qdrant_client_helper to return in-memory Qdrant client
import app.qdrant_client_helper
mock_qdrant_client = QdrantClient(location=":memory:")
app.qdrant_client_helper.get_qdrant_client = lambda: mock_qdrant_client

# 5. Define dependency override function
async def override_get_db():
    async with test_session_local() as session:
        try:
            yield session
        finally:
            await session.close()

# 6. Apply dependency overrides to FastAPI application
from main import app
from app.database import Base, get_db
app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
async def setup_test_environment():
    """
    Cleans up any pre-existing test directories, configures paths, and builds
    the mock database schemas before executing tests.
    """
    # Create test storage hierarchy
    shutil.rmtree("./test_storage", ignore_errors=True)
    Path("./test_storage/originals").mkdir(parents=True, exist_ok=True)
    Path("./test_storage/thumbnails").mkdir(parents=True, exist_ok=True)
    Path("./test_storage/logs").mkdir(parents=True, exist_ok=True)
    
    # Initialize SQLite database structures
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield
    
    # Teardown storage structure
    shutil.rmtree("./test_storage", ignore_errors=True)

@pytest.fixture
async def async_client():
    """
    Provides a configured AsyncClient referencing the FastAPI app with dependency overrides.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

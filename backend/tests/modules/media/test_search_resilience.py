import pytest
from unittest.mock import patch
from app.exceptions import QdrantConnectionError, EmbeddingModelError, InvalidSearchQueryError
from app.modules.media.services.search_service import SearchService
from tests.conftest import test_session_local


@pytest.fixture
async def db():
    async with test_session_local() as session:
        yield session


@pytest.mark.asyncio
async def test_search_service_invalid_query(db):
    with pytest.raises(InvalidSearchQueryError):
        await SearchService.search_media(db, "")


@pytest.mark.asyncio
async def test_search_service_qdrant_connection_error(db):
    with patch("app.modules.media.services.embedding_service.EmbeddingService.generate_text_embedding", return_value=[0.1] * 512):
        with patch("app.modules.media.services.qdrant_service.QdrantService.search_vectors", side_effect=QdrantConnectionError("Unable to connect to Qdrant.")):
            with pytest.raises(QdrantConnectionError) as exc_info:
                await SearchService.search_media(db, "beach")
            assert exc_info.value.status_code == 503
            assert "Unable to connect to Qdrant." in exc_info.value.message


@pytest.mark.asyncio
async def test_search_service_embedding_model_error(db):
    with patch("app.modules.media.services.embedding_service.EmbeddingService.generate_text_embedding", side_effect=EmbeddingModelError("Embedding model failed to initialize.")):
        with pytest.raises(EmbeddingModelError) as exc_info:
            await SearchService.search_media(db, "beach")
        assert exc_info.value.status_code == 503
        assert "Embedding model failed to initialize." in exc_info.value.message


@pytest.mark.asyncio
async def test_search_router_qdrant_error_endpoint(async_client):
    with patch("app.modules.media.services.embedding_service.EmbeddingService.generate_text_embedding", return_value=[0.1] * 512):
        with patch("app.modules.media.services.qdrant_service.QdrantService.search_vectors", side_effect=QdrantConnectionError("Unable to connect to Qdrant.")):
            response = await async_client.get("/api/media/search?q=beach")
            assert response.status_code == 503
            assert response.json()["detail"] == "Unable to connect to Qdrant."


@pytest.mark.asyncio
async def test_search_router_embedding_error_endpoint(async_client):
    with patch("app.modules.media.services.embedding_service.EmbeddingService.generate_text_embedding", side_effect=EmbeddingModelError("Embedding model failed to initialize.")):
        response = await async_client.get("/api/media/search?q=beach")
        assert response.status_code == 503
        assert response.json()["detail"] == "Embedding model failed to initialize."

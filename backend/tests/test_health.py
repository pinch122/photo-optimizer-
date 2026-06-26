import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """
    Test the health check endpoint returns 200 OK and matches expected JSON keys.
    """
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "postgres" in data
    assert "qdrant" in data
    assert "version" in data
    assert data["version"] == "0.1.0"

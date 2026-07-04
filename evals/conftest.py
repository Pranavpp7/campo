# evals/conftest.py
import os
import pytest
import pytest_asyncio
import asyncio
import uuid
import httpx
from dotenv import load_dotenv
from redis.asyncio import Redis

load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8000"
REDIS_URL = "redis://localhost:6379"
QDRANT_URL = f"http://localhost:{os.getenv('QDRANT_PORT', '6335')}"

# ── Pytest configuration ───────────────────────────────────────────────────────
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast, no external services needed")
    config.addinivalue_line("markers", "integration: requires Redis + Qdrant running")
    config.addinivalue_line("markers", "e2e: requires full stack (services + uvicorn)")

# ── Service health checks ──────────────────────────────────────────────────────
async def _is_api_up() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{API_BASE_URL}/health")
            return r.status_code == 200
    except Exception:
        return False

async def _is_redis_up() -> bool:
    try:
        redis = Redis.from_url(REDIS_URL)
        await redis.ping()
        await redis.aclose()
        return True
    except Exception:
        return False

async def _is_qdrant_up() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{QDRANT_URL}/collections")
            return r.status_code == 200
    except Exception:
        return False

# ── Pytest fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def session_id() -> str:
    """Fresh session ID per test — prevents history pollution between tests."""
    return f"eval-{uuid.uuid4().hex[:8]}"

@pytest.fixture
def user_id() -> str:
    return "eval-user"

@pytest_asyncio.fixture
async def api_client():
    """Async HTTP client pointed at the Campo API."""
    async with httpx.AsyncClient(
        base_url=API_BASE_URL,
        timeout=180.0,  # agents can take up to ~90s
    ) as client:
        yield client

@pytest_asyncio.fixture(scope="session")
async def redis_client():
    """Redis client for inspecting state in integration tests."""
    redis = Redis.from_url(REDIS_URL)
    yield redis
    await redis.aclose()

# ── Skip decorators — applied per test file ───────────────────────────────────
@pytest.fixture(autouse=False)
async def require_services(request):
    """Skip a test if Redis or Qdrant aren't reachable."""
    if not await _is_redis_up():
        pytest.skip("Redis not reachable — start services with: docker compose up -d")
    if not await _is_qdrant_up():
        pytest.skip("Qdrant not reachable — start services with: docker compose up -d")

@pytest.fixture(autouse=False)
async def require_api(request):
    """Skip a test if the FastAPI server isn't running."""
    if not await _is_api_up():
        pytest.skip("API not reachable — start with: uv run uvicorn api.main:app --reload")
    if not await _is_redis_up():
        pytest.skip("Redis not reachable — start services with: docker compose up -d")
    if not await _is_qdrant_up():
        pytest.skip("Qdrant not reachable — start services with: docker compose up -d")
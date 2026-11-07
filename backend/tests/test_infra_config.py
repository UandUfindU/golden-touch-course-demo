import pytest
from app.core.config import settings
from app.db.session import engine

def test_settings_load():
    """Test that settings are loaded correctly."""
    assert settings.PROJECT_NAME == "Golden Touch"
    assert "postgresql+asyncpg" in settings.DATABASE_URL
    assert "redis" in settings.REDIS_URL

@pytest.mark.asyncio
async def test_db_engine_creation():
    """Test that the DB engine is created with correct connection info."""
    # engine.url may mask password, so we check key parts
    engine_url = str(engine.url)
    assert "postgresql+asyncpg" in engine_url
    assert "golden_touch" in engine_url or "localhost" in engine_url

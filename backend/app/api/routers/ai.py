from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["AI"])

@router.get("/models")
async def get_models():
    """
    Get available LLM models.
    """
    params = settings.LLM_AVAILABLE_MODELS.split(",")
    models = [m.strip() for m in params if m.strip()]
    return {
        "models": models,
        "default": settings.LLM_DEFAULT_MODEL
    }

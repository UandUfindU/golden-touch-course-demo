from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

# Explicitly load .env to os.environ so os.getenv works everywhere
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Golden Touch"
    
    # Database (PostgreSQL + TimescaleDB + pgvector)
    DATABASE_URL: str = "postgresql+asyncpg://golden_user:golden_password@localhost:5432/golden_db"
    
    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    
    US_STOCK_DATA_PROVIDER: str = "akshare"

    # External APIs
    ZHIPU_API_KEY: str = ""
    ZAI_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    
    # LLM Configuration
    LLM_DEFAULT_MODEL: str = "cerebras/zai-glm-4.7"
    LLM_AVAILABLE_MODELS: str = "cerebras/zai-glm-4.7,zai/glm-4.5-flash"
    
    model_config = SettingsConfigDict(env_file=(".env", "test.env"), extra="ignore")

settings = Settings()

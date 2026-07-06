import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Base path definition
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # Environment settings
    ENV_MODE: str = "development"

    # Database Settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "photomind_secure_pass"
    POSTGRES_DB: str = "photomind"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    # Qdrant Vector Settings
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333

    # AI Model Settings
    GEMINI_API_KEY: str = ""
    CLIP_MODEL_NAME: str = "clip-ViT-B-32"
    HUGGINGFACE_CACHE_DIR: str = "/storage/hf_cache"

    # Storage Settings
    STORAGE_PATH: str = "/storage"
    THUMBNAIL_SIZE: int = 300
    LOG_LEVEL: str = "INFO"
    SEARCH_SIMILARITY_THRESHOLD: float = 0.22
    SEARCH_CANDIDATE_LIMIT: int = 20



    # Database URL helper
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Qdrant URL helper
    @property
    def qdrant_url(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # Load from .env file if available
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

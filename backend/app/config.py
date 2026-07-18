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
    SEARCH_CANDIDATE_LIMIT: int = 20

    # AI Understanding Engine Settings
    VISION_PROVIDER: str = "gemini"     # gemini | null — future: gpt4v | claude | florence
    AI_ANALYSIS_ENABLED: bool = True
    AI_ANALYSIS_MAX_RETRIES: int = 3

    # Hybrid Search Weights (must sum ≤ 1.0; embedding is always the primary signal)
    # Override any value in .env to tune ranking behaviour without code changes.
    HYBRID_WEIGHT_EMBEDDING: float = 0.55   # CLIP vector cosine similarity
    HYBRID_WEIGHT_CAPTION: float = 0.15     # Caption text keyword match
    HYBRID_WEIGHT_OBJECTS: float = 0.10     # Object list match
    HYBRID_WEIGHT_KEYWORDS: float = 0.08    # Semantic keyword/tag match
    HYBRID_WEIGHT_SCENE: float = 0.06       # Scene classification match
    HYBRID_WEIGHT_OCR: float = 0.05         # Detected OCR text match
    HYBRID_WEIGHT_EVENT: float = 0.03       # Event type match
    HYBRID_WEIGHT_PEOPLE: float = 0.03      # People count boost (people-related queries)
    HYBRID_WEIGHT_DOCUMENT: float = 0.03    # Document type boost (doc-related queries)



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

import os
import threading
import asyncio
from typing import List, Optional
from PIL import Image
from sentence_transformers import SentenceTransformer
from app.config import settings
from app.logging_config import logger

from app.exceptions import EmbeddingModelError

class EmbeddingService:
    _model: Optional[SentenceTransformer] = None
    _lock = threading.Lock()

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """
        Thread-safe singleton getter returning the cached SentenceTransformer model instance.
        Loads model weights from settings cache on first invocation.
        """
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    try:
                        logger.info(f"CLIP Model: Loading weights for model '{settings.CLIP_MODEL_NAME}'...")
                        os.makedirs(settings.HUGGINGFACE_CACHE_DIR, exist_ok=True)

                        # Instantiate SentenceTransformer pointing to persistent volume cache
                        cls._model = SentenceTransformer(
                            model_name_or_path=settings.CLIP_MODEL_NAME,
                            cache_folder=settings.HUGGINGFACE_CACHE_DIR
                        )
                        logger.info("CLIP Model: Initialized and weights loaded successfully.")
                    except Exception as e:
                        logger.exception(f"CLIP Model: Critical initialization failure for model '{settings.CLIP_MODEL_NAME}': {e}")
                        raise EmbeddingModelError("Embedding model failed to initialize.") from e
        return cls._model

    @classmethod
    def generate_embedding_sync(cls, file_path: str) -> List[float]:
        """
        Synchronously opens the file, converts format to RGB, executes CLIP encoding, 
        normalizes the output, and returns a 512-dimension float list.
        """
        try:
            model = cls.get_model()
            with Image.open(file_path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                embedding_array = model.encode(img, normalize_embeddings=True)
                return embedding_array.tolist()
        except EmbeddingModelError:
            raise
        except Exception as e:
            logger.exception(f"CLIP Model: Inference failure on target '{file_path}': {e}")
            raise EmbeddingModelError("Embedding model failed during image inference.") from e

    @classmethod
    async def generate_embedding(cls, file_path: str) -> List[float]:
        """
        Executes CPU-bound PyTorch neural network forward pass in the default thread pool.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            cls.generate_embedding_sync,
            file_path
        )

    @classmethod
    def generate_text_embedding_sync(cls, text: str) -> List[float]:
        """
        Synchronously encodes a natural language query into a 512-dimension vector.
        """
        try:
            model = cls.get_model()
            embedding_array = model.encode(text, normalize_embeddings=True)
            return embedding_array.tolist()
        except EmbeddingModelError:
            raise
        except Exception as e:
            logger.exception(f"CLIP Model: Text inference failure on '{text}': {e}")
            raise EmbeddingModelError("Embedding model failed during text query evaluation.") from e

    @classmethod
    async def generate_text_embedding(cls, text: str) -> List[float]:
        """
        Executes CPU-bound PyTorch text tokenizer and model run on thread executor.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            cls.generate_text_embedding_sync,
            text
        )


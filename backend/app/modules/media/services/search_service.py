import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.config import settings
from app.modules.media.models import MediaAsset
from app.modules.media.services.embedding_service import EmbeddingService
from app.modules.media.services.qdrant_service import QdrantService
from app.logging_config import logger

class SearchService:
    @classmethod
    async def search_media(
        cls,
        db: AsyncSession,
        query_text: str,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Orchestrates semantic text searches:
        1. Encodes query text into a 512-dimension query vector.
        2. Queries Qdrant for closest vector matches (Cosine distance).
        3. Retrieves corresponding PostgreSQL records with eager-loaded child metadata.
        4. Re-ranks PostgreSQL records according to descending Qdrant similarity scores.
        """
        if not query_text or not query_text.strip():
            raise ValueError("Query string cannot be empty.")
            
        # 1. Generate text embedding query vector
        logger.info(f"Search Service: Encoding query text: '{query_text}'")
        query_vector = await EmbeddingService.generate_text_embedding(query_text)
        
        # 2. Query Qdrant for matching points
        logger.info(f"Search Service: Querying Qdrant index (limit={limit}, offset={offset})")
        hits = QdrantService.search_vectors(
            vector=query_vector,
            model_name=settings.CLIP_MODEL_NAME,
            limit=limit,
            offset=offset
        )
        
        if not hits:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}
            
        # Map IDs and scores
        hit_ids = [hit["id"] for hit in hits]
        scores_map = {hit["id"]: hit["score"] for hit in hits}
        
        # 3. Eager load PostgreSQL assets matching the IDs
        query = (
            select(MediaAsset)
            .options(selectinload(MediaAsset.photo_metadata))
            .where(MediaAsset.id.in_(hit_ids))
        )
        
        result = await db.execute(query)
        assets = result.scalars().all()
        assets_map = {asset.id: asset for asset in assets}
        
        # 4. Sort records to match Qdrant's ordering and dynamically assign scores
        ranked_items = []
        for hit_id in hit_ids:
            asset = assets_map.get(hit_id)
            if asset:
                # Dynamically set score attribute for Pydantic schema validation mapping
                asset.score = scores_map[hit_id]
                ranked_items.append(asset)
            else:
                logger.warning(f"Search Service: Vector match [{hit_id}] found in Qdrant but missing from PostgreSQL.")
                
        # Simple pagination ceiling total calculation
        total_count = len(ranked_items) + offset
        
        return {
            "items": ranked_items,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }

import uuid
import time
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
    async def _rank_and_filter_candidates(
        cls,
        candidates: List[Dict[str, Any]],
        query_text: str,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Ranker pipeline step. Currently filters candidates below the similarity threshold
        and sorts them by vector cosine distance score.
        
        ========================================================================
        FUTURE RERANKING ARCHITECTURE
        ========================================================================
        When integrating richer AI models, this pipeline should evolve as:
        
        Retrieve Candidates (from Qdrant)
        ↓
        Threshold Filter (remove extremely low matches early)
        ↓
        [TODO: Future Gemini Reranker - re-evaluate top candidates using Gemini Vision LLM]
        ↓
        [TODO: Future Metadata Boost - boost scores based on EXIF/GPS/Date matching]
        ↓
        Return Re-ranked Results
        ========================================================================
        """
        # Step 1: Threshold Filter
        filtered = [c for c in candidates if c["score"] >= threshold]
        
        # TODO: Future Gemini Reranker will be plugged in here.
        # e.g., filtered = await GeminiReranker.rerank(filtered, query_text)
        
        # TODO: Future Metadata Boost will be plugged in here.
        # e.g., filtered = await MetadataBooster.apply_boosts(filtered, query_text)
        
        # Step 2: Sort remaining by score descending
        sorted_candidates = sorted(filtered, key=lambda x: x["score"], reverse=True)
        return sorted_candidates

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
        2. Queries Qdrant for closest vector matches (Cosine distance, top SEARCH_CANDIDATE_LIMIT candidates).
        3. Applies ranker pipeline (filtering by threshold and sorting).
        4. Hydrates PostgreSQL records for the filtered slice.
        """
        if not query_text or not query_text.strip():
            raise ValueError("Query string cannot be empty.")

        start_time = time.perf_counter()
        
        # 1. Generate text embedding query vector
        logger.info(f"Search Service: Starting embedding generation for query: '{query_text}'")
        embed_start = time.perf_counter()
        query_vector = await EmbeddingService.generate_text_embedding(query_text)
        embed_duration = time.perf_counter() - embed_start
        logger.info(f"Search Service: Embedding generation complete in {embed_duration:.4f}s")
        
        # 2. Query Qdrant for top candidate points (using configurable SEARCH_CANDIDATE_LIMIT)
        candidate_pool_size = settings.SEARCH_CANDIDATE_LIMIT
        logger.info(f"Search Service: Retrieving Top-{candidate_pool_size} candidates from Qdrant")
        candidates = QdrantService.search_vectors(
            vector=query_vector,
            model_name=settings.CLIP_MODEL_NAME,
            limit=candidate_pool_size,
            offset=0
        )
        
        # 3. Apply ranking and threshold filtering pipeline
        threshold = settings.SEARCH_SIMILARITY_THRESHOLD
        logger.info(f"Search Service: Running ranking and filtering with threshold: {threshold}")
        processed_candidates = await cls._rank_and_filter_candidates(
            candidates=candidates,
            query_text=query_text,
            threshold=threshold
        )
        
        total_filtered = len(processed_candidates)
        
        # Apply pagination (limit, offset) slicing on the filtered results
        paginated_candidates = processed_candidates[offset : offset + limit]
        
        if not paginated_candidates:
            duration = time.perf_counter() - start_time
            logger.info(
                f"Search finished (no matches): query='{query_text}', threshold={threshold}, "
                f"candidates={len(candidates)}, filtered={total_filtered}, time={duration:.4f}s"
            )
            return {
                "items": [],
                "total": total_filtered,
                "limit": limit,
                "offset": offset
            }
            
        # Map IDs and scores
        hit_ids = [hit["id"] for hit in paginated_candidates]
        scores_map = {hit["id"]: hit["score"] for hit in paginated_candidates}
        
        # 4. Eager load PostgreSQL assets matching the sliced IDs
        query = (
            select(MediaAsset)
            .options(selectinload(MediaAsset.photo_metadata))
            .where(MediaAsset.id.in_(hit_ids))
        )
        
        result = await db.execute(query)
        assets = result.scalars().all()
        assets_map = {asset.id: asset for asset in assets}
        
        # Sort records to match the ranking pipeline ordering and dynamically assign scores
        ranked_items = []
        for hit_id in hit_ids:
            asset = assets_map.get(hit_id)
            if asset:
                asset.score = scores_map[hit_id]
                
                # TODO: Future Search Explanation generation will populate this list
                # e.g., asset.explanation = await ExplanationGenerator.generate(asset, query_text)
                asset.explanation = None
                
                ranked_items.append(asset)
            else:
                logger.warning(f"Search Service: Vector match [{hit_id}] found in Qdrant but missing from PostgreSQL.")
                
        duration = time.perf_counter() - start_time
        logger.info(
            f"Search finished: query='{query_text}', threshold={threshold}, "
            f"candidates={len(candidates)}, filtered={total_filtered}, sliced={len(ranked_items)}, "
            f"time={duration:.4f}s"
        )
        
        return {
            "items": ranked_items,
            "total": total_filtered,
            "limit": limit,
            "offset": offset
        }

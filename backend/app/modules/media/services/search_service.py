"""
Search Service — Hybrid Semantic + Memory Record Search.

Pipeline (Sprint 7)
-------------------
1. Encode query text → 512-dim CLIP vector
2. Retrieve top-N candidates from Qdrant (cosine similarity)
3. Threshold-filter candidates (drop score < SEARCH_SIMILARITY_THRESHOLD)
4. Load PostgreSQL assets + AI Memory Records for ALL filtered candidates
5. HybridReranker: compute weighted hybrid score using embedding + Memory Record
6. Paginate the reranked list
7. Generate explanations and return
"""

import uuid
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.config import settings
from app.modules.media.models import MediaAsset
from app.modules.media.services.embedding_service import EmbeddingService
from app.modules.media.services.qdrant_service import QdrantService
from app.modules.media.services.hybrid_reranker import HybridReranker, HybridWeights
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
        Orchestrate a hybrid semantic + Memory Record search.

        Steps
        -----
        1. Encode query → CLIP embedding
        2. Qdrant: retrieve top-N vector candidates
        3. Threshold filter
        4. Hydrate all filtered candidates from PostgreSQL (with ai_analysis)
        5. HybridReranker: combine embedding score with AI Memory Record signals
        6. Paginate
        7. Attach explanations
        """
        if not query_text or not query_text.strip():
            raise ValueError("Query string cannot be empty.")

        # ── Special bypass for full-library analytics queries ─────────────────
        if query_text.lower() == "photo":
            logger.info("Search Service: Bypassing Qdrant for special query 'photo'")
            total_stmt = select(func.count(MediaAsset.id))
            total_result = await db.execute(total_stmt)
            total_filtered = total_result.scalar() or 0

            query = (
                select(MediaAsset)
                .options(
                    selectinload(MediaAsset.photo_metadata),
                    selectinload(MediaAsset.ai_analysis)
                )
                .order_by(MediaAsset.created_at.desc())
            )
            result = await db.execute(query)
            ranked_items = result.scalars().all()

            for item in ranked_items:
                item.score = 1.0
                item.explanation = None

            return {
                "items": ranked_items,
                "total": total_filtered,
                "limit": len(ranked_items),
                "offset": 0
            }

        start_time = time.perf_counter()

        # ── 1. Generate text embedding ────────────────────────────────────────
        logger.info(f"Search Service: Starting embedding generation for query: '{query_text}'")
        embed_start = time.perf_counter()
        query_vector = await EmbeddingService.generate_text_embedding(query_text)
        embed_duration = time.perf_counter() - embed_start
        logger.info(f"Search Service: Embedding generation complete in {embed_duration:.4f}s")

        # ── 2. Qdrant retrieval ───────────────────────────────────────────────
        candidate_pool_size = settings.SEARCH_CANDIDATE_LIMIT
        logger.info(f"Search Service: Retrieving Top-{candidate_pool_size} candidates from Qdrant")
        candidates = QdrantService.search_vectors(
            vector=query_vector,
            model_name=settings.CLIP_MODEL_NAME,
            limit=candidate_pool_size,
            offset=0
        )

        # ── 3. Threshold filter ───────────────────────────────────────────────
        threshold = settings.SEARCH_SIMILARITY_THRESHOLD
        logger.info(f"Search Service: Threshold filtering at {threshold}")
        filtered = [c for c in candidates if c["score"] >= threshold]

        total_filtered = len(filtered)

        if not filtered:
            duration = time.perf_counter() - start_time
            logger.info(
                f"Search finished (no matches): query='{query_text}', threshold={threshold}, "
                f"candidates={len(candidates)}, filtered=0, time={duration:.4f}s"
            )
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        # ── 4. Hydrate ALL filtered candidates from PostgreSQL ────────────────
        # We load all before pagination so the reranker sees the full candidate set.
        all_ids = [hit["id"] for hit in filtered]
        pg_query = (
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.photo_metadata),
                selectinload(MediaAsset.ai_analysis)
            )
            .where(MediaAsset.id.in_(all_ids))
        )
        pg_result = await db.execute(pg_query)
        assets = pg_result.scalars().all()
        assets_map = {asset.id: asset for asset in assets}

        # Warn about any Qdrant–PG orphans
        for hit_id in all_ids:
            if hit_id not in assets_map:
                logger.warning(
                    f"Search Service: Qdrant candidate [{hit_id}] not found in PostgreSQL."
                )

        # ── 5. Hybrid reranking ───────────────────────────────────────────────
        weights = HybridWeights.from_settings(settings)
        logger.info(
            f"Search Service: Running HybridReranker on {len(filtered)} candidates "
            f"(embedding={weights.embedding}, caption={weights.caption}, "
            f"objects={weights.objects}, keywords={weights.keywords})"
        )
        reranked = HybridReranker.rerank(
            candidates=filtered,
            query_text=query_text,
            assets_map=assets_map,
            weights=weights,
        )

        # ── 6. Paginate ───────────────────────────────────────────────────────
        paginated = reranked[offset: offset + limit]

        # ── 7. Build response with explanations ───────────────────────────────
        from app.modules.media.services.explanation_service import ExplanationService

        ranked_items = []
        for hit in paginated:
            asset = assets_map.get(hit["id"])
            if asset:
                asset.score = hit["hybrid_score"]
                # Merge hybrid boost reasons with the base explanation
                explanation = ExplanationService.generate_explanation(
                    query_text=query_text,
                    asset=asset,
                    score=hit["hybrid_score"],
                    boost_reasons=hit.get("boost_reasons", []),
                )
                asset.explanation = explanation
                ranked_items.append(asset)

        duration = time.perf_counter() - start_time
        logger.info(
            f"Search finished: query='{query_text}', threshold={threshold}, "
            f"candidates={len(candidates)}, filtered={total_filtered}, "
            f"sliced={len(ranked_items)}, time={duration:.4f}s"
        )

        return {
            "items": ranked_items,
            "total": total_filtered,
            "limit": limit,
            "offset": offset,
        }

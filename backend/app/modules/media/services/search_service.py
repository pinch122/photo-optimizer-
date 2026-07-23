"""
Search Service — Hybrid Semantic + Memory Record Search.

Pipeline (Sprint 7)
-------------------
1. Encode query text → 512-dim CLIP vector
2. Retrieve top-N candidates from Qdrant (cosine similarity)
3. Load PostgreSQL assets + AI Memory Records for ALL candidates
4. HybridReranker: compute weighted hybrid score using embedding + Memory Record
5. Paginate the reranked list
6. Generate explanations and return
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
            total_stmt = select(func.count(MediaAsset.id)).where(MediaAsset.is_deleted == False)
            total_result = await db.execute(total_stmt)
            total_filtered = total_result.scalar() or 0

            query = (
                select(MediaAsset)
                .options(
                    selectinload(MediaAsset.photo_metadata),
                    selectinload(MediaAsset.ai_analysis),
                    selectinload(MediaAsset.quality_assessment)
                )
                .where(MediaAsset.is_deleted == False)
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

        # ── 3. Hydrate ALL non-deleted candidates from PostgreSQL ──────────────
        total_filtered = len(candidates)
        if not candidates:
            duration = time.perf_counter() - start_time
            logger.info(
                f"Search finished (no candidates): query='{query_text}', time={duration:.4f}s"
            )
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        all_ids = [hit["id"] for hit in candidates]
        pg_query = (
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.photo_metadata),
                selectinload(MediaAsset.ai_analysis),
                selectinload(MediaAsset.quality_assessment)
            )
            .where(MediaAsset.id.in_(all_ids), MediaAsset.is_deleted == False)
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

        # ── 4. Hybrid reranking ───────────────────────────────────────────────
        weights = HybridWeights.from_settings(settings)
        logger.info(
            f"Search Service: Running HybridReranker on {len(candidates)} candidates "
            f"(embedding={weights.embedding}, caption={weights.caption}, "
            f"objects={weights.objects}, keywords={weights.keywords})"
        )
        reranked = HybridReranker.rerank(
            candidates=candidates,
            query_text=query_text,
            assets_map=assets_map,
            weights=weights,
        )

        # ── 5. Intent Detection & Unified Ranking Computation ────────────────────
        from app.modules.media.services.intent_service import IntentService, QueryIntent
        from app.modules.media.services.explanation_service import ExplanationService

        intent, target_entity = IntentService.classify_intent(query_text)
        logger.info(f"Search Service: Detected query intent [{intent}] for target entity '{target_entity}'")

        unified_candidates = []

        for hit in reranked:
            asset = assets_map.get(hit["id"])
            if not asset:
                continue

            is_valid, confidence, intent_reasons = IntentService.validate_asset_for_intent(
                asset=asset,
                intent=intent,
                target_entity=target_entity,
                score=hit["hybrid_score"]
            )

            # Filter out invalid / contradictory hits to prevent false positives
            if not is_valid and intent != QueryIntent.GENERAL:
                continue

            # Determine match_type ("Confirmed" vs "Similar")
            # Confirmed = passes intent validation & has explicit metadata evidence OR non-low confidence
            has_explicit_evidence = len(intent_reasons) > 0 or confidence in {"Very High", "High"}

            if is_valid and has_explicit_evidence:
                match_type = "Confirmed"
                boost_weight = 0.35  # Explicit metadata boost ensures confirmed results rank top
                confidence_level = confidence
                all_reasons = (hit.get("boost_reasons", []) or []) + intent_reasons
            else:
                match_type = "Similar"
                boost_weight = 0.00
                confidence_level = "Similar"
                all_reasons = ["Visual & semantic vector similarity match"]

            # Unified Score formula: final_score = hybrid_score + boost_weight
            final_score = round(hit["hybrid_score"] + boost_weight, 6)

            hit["match_type"] = match_type
            hit["final_score"] = final_score
            hit["confidence_level"] = confidence_level
            hit["all_boost_reasons"] = all_reasons

            unified_candidates.append(hit)

        # Sort all candidates by final_score descending
        unified_candidates.sort(key=lambda x: x["final_score"], reverse=True)

        total_items = len(unified_candidates)

        # If zero matching results, return contextual empty message
        if total_items == 0 and intent != QueryIntent.GENERAL:
            empty_message = IntentService.format_empty_message(query_text, intent, target_entity)
            duration = time.perf_counter() - start_time
            logger.info(f"Search finished (empty): query='{query_text}', message='{empty_message}', time={duration:.4f}s")
            return {
                "items": [],
                "excellent_matches": [],
                "similar_photos": [],
                "total": 0,
                "total_similar": 0,
                "limit": limit,
                "offset": offset,
                "message": empty_message
            }

        # ── 6. Paginate ───────────────────────────────────────────────────────
        paginated = unified_candidates[offset: offset + limit]

        # ── 7. Build response with explanations ───────────────────────────────
        ranked_items = []
        for hit in paginated:
            asset = assets_map.get(hit["id"])
            if asset:
                asset.score = hit["final_score"]
                asset.match_type = hit["match_type"]
                asset.explanation = ExplanationService.generate_explanation(
                    query_text=query_text,
                    asset=asset,
                    score=hit["final_score"],
                    boost_reasons=hit.get("all_boost_reasons", []),
                    confidence_level=hit.get("confidence_level"),
                )
                ranked_items.append(asset)

        confirmed_items = [a for a in ranked_items if getattr(a, "match_type", "") == "Confirmed"]
        similar_items = [a for a in ranked_items if getattr(a, "match_type", "") == "Similar"]

        duration = time.perf_counter() - start_time
        logger.info(
            f"Search finished (unified): query='{query_text}', "
            f"candidates={len(candidates)}, total_returned={total_items}, time={duration:.4f}s"
        )

        return {
            "items": ranked_items,
            "excellent_matches": confirmed_items,
            "similar_photos": similar_items,
            "total": total_items,
            "total_similar": len(similar_items),
            "limit": limit,
            "offset": offset,
            "message": None
        }

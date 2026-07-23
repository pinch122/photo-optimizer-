import asyncio
import time
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.modules.media.models import MediaAsset
from app.modules.media.services.search_service import SearchService
from app.modules.media.services.intent_service import IntentService, QueryIntent
from app.modules.media.services.qdrant_service import QdrantService
from app.modules.media.services.embedding_service import EmbeddingService
from app.config import settings

async def main():
    async with async_session() as db:
        query_text = "receipt"
        print(f"=== Debugging Search for: '{query_text}' ===")
        
        # 1. Intent Classification
        intent, target_entity = IntentService.classify_intent(query_text)
        print(f"1. Intent Classified: {intent} (Target Entity: '{target_entity}')")

        # 2. Embedding Generation
        t0 = time.perf_counter()
        query_vector = await EmbeddingService.generate_text_embedding(query_text)
        t1 = time.perf_counter()
        print(f"2. Embedding generation time: {t1 - t0:.4f}s")

        # 3. Qdrant candidates
        candidates = QdrantService.search_vectors(
            vector=query_vector,
            model_name=settings.CLIP_MODEL_NAME,
            limit=settings.SEARCH_CANDIDATE_LIMIT,
            offset=0
        )
        t2 = time.perf_counter()
        print(f"3. Qdrant candidates count: {len(candidates)} (retrieval time: {t2 - t1:.4f}s)")
        if candidates:
            print(f"   Top Qdrant score: {candidates[0]['score']:.4f}, Lowest Qdrant score: {candidates[-1]['score']:.4f}")

        # 4. Hydrate candidates from PostgreSQL
        all_ids = [hit["id"] for hit in candidates]
        pg_query = (
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.photo_metadata),
                selectinload(MediaAsset.ai_analysis),
                selectinload(MediaAsset.quality_assessment)
            )
            .where(MediaAsset.id.in_(all_ids))
        )
        t3_start = time.perf_counter()
        result = await db.execute(pg_query)
        assets = result.scalars().all()
        t3_end = time.perf_counter()
        print(f"4. Hydrated {len(assets)} assets from PG in {t3_end - t3_start:.4f}s")

        assets_map = {asset.id: asset for asset in assets}

        # 5. Evaluate validation on each candidate
        print("\n--- Inspecting candidates against Intent Validation ---")
        valid_count = 0
        for idx, hit in enumerate(candidates[:20]):
            asset = assets_map.get(hit["id"])
            if not asset:
                continue
            ai = asset.ai_analysis
            doc_type = ai.document_type if ai else None
            ocr_text = (ai.detected_text if ai and ai.detected_text else "")[:50]
            caption = (ai.caption if ai and ai.caption else "")[:50]
            objs = ai.objects if ai else []
            kws = list(ai.keywords.keys())[:5] if ai and ai.keywords else []

            is_valid, conf, reasons = IntentService.validate_asset_for_intent(
                asset=asset,
                intent=intent,
                target_entity=target_entity,
                score=hit["score"]
            )
            if is_valid and conf != "Low":
                valid_count += 1

            print(f"Candidate #{idx+1} [ID={str(asset.id)[:8]}]:")
            print(f"   Score: {hit['score']:.4f}")
            print(f"   DocType: {doc_type} | OCR: {ocr_text} | Caption: {caption}")
            print(f"   Objects: {objs} | Keywords: {kws}")
            print(f"   Validation Result -> is_valid: {is_valid}, conf: {conf}, reasons: {reasons}")
            print("-" * 50)

        print(f"\n5. Total valid candidates passing validation: {valid_count}")

        # 6. Full SearchService call
        t4_start = time.perf_counter()
        res = await SearchService.search_media(db, query_text, limit=10, offset=0)
        t4_end = time.perf_counter()
        print(f"\n6. Full SearchService response count: {len(res['items'])} in {t4_end - t4_start:.4f}s")
        print(f"   Message: {res.get('message')}")

if __name__ == "__main__":
    asyncio.run(main())

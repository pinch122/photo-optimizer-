import asyncio
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.modules.media.models import MediaAsset, ImageAIAnalysis

async def main():
    async with async_session() as db:
        # 1. Count rows in image_ai_analysis
        count_stmt = select(func.count(ImageAIAnalysis.id))
        count_res = await db.execute(count_stmt)
        total_ai_rows = count_res.scalar()

        asset_count_stmt = select(func.count(MediaAsset.id))
        asset_count_res = await db.execute(asset_count_stmt)
        total_assets = asset_count_res.scalar()

        print(f"1. TOTAL ROWS IN image_ai_analysis: {total_ai_rows} (out of {total_assets} total media_assets)")

        # 2. Pick one image from Similar Photos candidates
        sample_stmt = (
            select(MediaAsset)
            .options(selectinload(MediaAsset.ai_analysis))
            .where(MediaAsset.filename.in_(["4.jpg", "64.jpg", "195.jpg", "235.jpg", "237.jpg"]))
            .limit(1)
        )
        sample_res = await db.execute(sample_stmt)
        sample_asset = sample_res.scalar_one_or_none()

        if sample_asset and sample_asset.ai_analysis:
            ai = sample_asset.ai_analysis
            print(f"\n2. SAMPLE IMAGE INSPECTION -> Filename: [{sample_asset.filename}] (ID: {sample_asset.id})")
            print("   CURRENT REBUILT METADATA:")
            print(f"     • caption: '{ai.caption}'")
            print(f"     • objects: {ai.objects}")
            print(f"     • scene: '{ai.scene}'")
            print(f"     • keywords: {list((ai.keywords or {}).keys())}")
            print(f"     • document_type: {ai.document_type}")

            print("\n   COMPARISON TO BEFORE THE REBUILD:")
            print(f"     • Before caption: 'A photo of filename {sample_asset.filename} with aspect ratio 1024x768'")
            print("     • Before objects: None")
            print("     • Before scene: None")
            print("     • Before keywords: ['p_hash', 'blur_score', 'brightness', 'darkness', 'sharpness']")
            print("     • Before document_type: None")

        # 3. Check null rates across all 1034 AI Memory Records
        stmt_all = select(ImageAIAnalysis)
        all_res = await db.execute(stmt_all)
        all_records = all_res.scalars().all()

        empty_caption = sum(1 for r in all_records if not r.caption)
        empty_objects = sum(1 for r in all_records if not r.objects or len(r.objects) == 0)
        empty_scene = sum(1 for r in all_records if not r.scene)
        empty_keywords = sum(1 for r in all_records if not r.keywords or len(r.keywords) == 0)

        print("\n3. RECOMMENDATION QUERIES & FILTERING FIELD AUDIT:")
        print(f"   • Records with empty caption: {empty_caption} / {total_ai_rows}")
        print(f"   • Records with empty objects: {empty_objects} / {total_ai_rows}")
        print(f"   • Records with empty scene: {empty_scene} / {total_ai_rows}")
        print(f"   • Records with empty keywords: {empty_keywords} / {total_ai_rows}")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.modules.media.models import MediaAsset, ImageAIAnalysis

async def main():
    async with async_session() as db:
        print("=== Verifying Refreshed AI Memory Records in Database ===")
        stmt = (
            select(MediaAsset)
            .options(selectinload(MediaAsset.ai_analysis))
            .where(MediaAsset.status == "READY")
        )
        res = await db.execute(stmt)
        assets = res.scalars().all()

        print(f"Loaded {len(assets)} READY assets from database.")
        for a in assets[:10]:
            ai = a.ai_analysis
            if ai:
                print(f"\n[Asset {a.filename}]")
                print(f"  Caption: '{ai.caption}'")
                print(f"  Objects: {ai.objects}")
                print(f"  Scene: '{ai.scene}'")
                print(f"  Dominant Colors: {ai.dominant_colors}")
                print(f"  Keywords: {list((ai.keywords or {}).keys())}")

if __name__ == "__main__":
    asyncio.run(main())

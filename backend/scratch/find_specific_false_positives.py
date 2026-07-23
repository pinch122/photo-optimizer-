import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.modules.media.models import MediaAsset

def get_hamming_distance(hash1: str, hash2: str) -> int:
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        return bin(val1 ^ val2).count('1')
    except ValueError:
        return 999

async def main():
    async with async_session() as db:
        query = (
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.photo_metadata),
                selectinload(MediaAsset.ai_analysis)
            )
        )
        res = await db.execute(query)
        assets = res.scalars().all()

        print("=== Inspecting all 354 candidate near-duplicate pairs (dist 1..4) ===")
        for i in range(len(assets)):
            itemA = assets[i]
            if not itemA.p_hash:
                continue
            for j in range(i + 1, len(assets)):
                itemB = assets[j]
                if not itemB.p_hash:
                    continue
                dist = get_hamming_distance(itemA.p_hash, itemB.p_hash)
                if 1 <= dist <= 4:
                    # Print any pair where itemA and itemB are DIFFERENT base files (not edits of same file)
                    baseA = itemA.filename.replace("resized_", "").replace("dark_", "").replace("bright_", "").replace("blurred_", "").replace("rotated_", "")
                    baseB = itemB.filename.replace("resized_", "").replace("dark_", "").replace("bright_", "").replace("blurred_", "").replace("rotated_", "")

                    if baseA != baseB:
                        aiA = itemA.ai_analysis
                        aiB = itemB.ai_analysis
                        metaA = itemA.photo_metadata
                        metaB = itemB.photo_metadata

                        wA = metaA.width if metaA else None
                        hA = metaA.height if metaA else None
                        wB = metaB.width if metaB else None
                        hB = metaB.height if metaB else None

                        print(f"\nCROSS-IMAGE FALSE POSITIVE CANDIDATE PAIR (pHash Dist = {dist}):")
                        print(f"  Item A: [{itemA.filename}] (Base: {baseA}) | Dim: {wA}x{hA} | pHash: {itemA.p_hash}")
                        print(f"    Caption: '{aiA.caption if aiA else None}'")
                        print(f"    Scene: '{aiA.scene if aiA else None}' | Objs: {aiA.objects if aiA else None} | Colors: {aiA.dominant_colors if aiA else None}")
                        print(f"  Item B: [{itemB.filename}] (Base: {baseB}) | Dim: {wB}x{hB} | pHash: {itemB.p_hash}")
                        print(f"    Caption: '{aiB.caption if aiB else None}'")
                        print(f"    Scene: '{aiB.scene if aiB else None}' | Objs: {aiB.objects if aiB else None} | Colors: {aiB.dominant_colors if aiB else None}")

if __name__ == "__main__":
    asyncio.run(main())

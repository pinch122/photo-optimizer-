import asyncio
import random
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.modules.media.models import MediaAsset, ImageAIAnalysis

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
        print("=== AUDITING pHASH INTEGRITY & STORAGE FORMAT ===")
        stmt = (
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.ai_analysis),
                selectinload(MediaAsset.photo_metadata)
            )
            .where(MediaAsset.status == "READY")
        )
        res = await db.execute(stmt)
        assets = res.scalars().all()
        print(f"Loaded {len(assets)} READY assets.\n")

        # 1. Inspect p_hash storage across 20 sample images
        print("--- 1. SAMPLE 20 pHASH VALUES FROM DATABASE ---")
        phashes = []
        valid_hex_count = 0
        for i, a in enumerate(assets[:20]):
            ph = a.p_hash
            is_valid_hex = False
            if ph and len(ph) == 16:
                try:
                    int(ph, 16)
                    is_valid_hex = True
                    valid_hex_count += 1
                except ValueError:
                    pass

            print(f"Asset #{i+1} [{a.filename}]: p_hash = '{ph}' (Valid 16-char hex: {is_valid_hex})")
            if ph:
                phashes.append(ph)

        print(f"\nValid 16-character hex count: {valid_hex_count} / {len(assets[:20])}")

        # 2. Check pHash population rate across all assets
        all_phashes = [a.p_hash for a in assets if a.p_hash]
        print(f"\n--- 2. pHASH POPULATION OVERALL ---")
        print(f"Total assets with non-null p_hash: {len(all_phashes)} / {len(assets)}")

        # 3. Calculate Hamming Distance Distribution across 1,000 random image pairs
        print(f"\n--- 3. HAMMING DISTANCE DISTRIBUTION (1,000 RANDOM PAIRS) ---")
        valid_assets = [a for a in assets if a.p_hash and len(a.p_hash) == 16]
        if len(valid_assets) >= 2:
            dist_counts = {i: 0 for i in range(65)}
            dist_counts[999] = 0

            random.seed(42)
            pair_count = 0
            for _ in range(1000):
                a1, a2 = random.sample(valid_assets, 2)
                dist = get_hamming_distance(a1.p_hash, a2.p_hash)
                dist_counts[dist] = dist_counts.get(dist, 0) + 1
                pair_count += 1

            print(f"Evaluated {pair_count} random pairs:")
            print(f"  • Distance = 0 (Exact match): {dist_counts.get(0, 0)}")
            print(f"  • Distance 1..4 (Near duplicate window): {sum(dist_counts.get(d, 0) for d in range(1, 5))}")
            print(f"    - dist 1: {dist_counts.get(1, 0)}")
            print(f"    - dist 2: {dist_counts.get(2, 0)}")
            print(f"    - dist 3: {dist_counts.get(3, 0)}")
            print(f"    - dist 4: {dist_counts.get(4, 0)}")
            print(f"  • Distance 5..10: {sum(dist_counts.get(d, 0) for d in range(5, 11))}")
            print(f"  • Distance 11..20: {sum(dist_counts.get(d, 0) for d in range(11, 21))}")
            print(f"  • Distance 21..32: {sum(dist_counts.get(d, 0) for d in range(21, 33))}")
            print(f"  • Distance > 32: {sum(dist_counts.get(d, 0) for d in range(33, 65))}")

        # 4. Check edits of same original file (e.g. bright_, dark_, rotated_, resized_)
        print(f"\n--- 4. HAMMING DISTANCE FOR DERIVED EDIT PAIRS (SAME ORIGINAL BASE IMAGE) ---")
        base_groups = {}
        for a in valid_assets:
            base = a.filename.replace("resized_", "").replace("dark_", "").replace("bright_", "").replace("blurred_", "").replace("rotated_", "")
            base_groups.setdefault(base, []).append(a)

        edit_pairs_evaluated = 0
        edit_dist_counts = {i: 0 for i in range(65)}
        for base, group in base_groups.items():
            if len(group) > 1:
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        a1 = group[i]
                        a2 = group[j]
                        dist = get_hamming_distance(a1.p_hash, a2.p_hash)
                        edit_dist_counts[dist] = edit_dist_counts.get(dist, 0) + 1
                        edit_pairs_evaluated += 1
                        if edit_pairs_evaluated <= 10:
                            print(f"  [{a1.filename}] vs [{a2.filename}] -> pHash1={a1.p_hash}, pHash2={a2.p_hash} | Dist = {dist}")

        print(f"\nEvaluated {edit_pairs_evaluated} derived edit pairs:")
        print(f"  • Distance = 0: {edit_dist_counts.get(0, 0)}")
        print(f"  • Distance 1..4 (Near duplicate window): {sum(edit_dist_counts.get(d, 0) for d in range(1, 5))}")
        print(f"  • Distance 5..15: {sum(edit_dist_counts.get(d, 0) for d in range(5, 16))}")
        print(f"  • Distance > 15: {sum(edit_dist_counts.get(d, 0) for d in range(16, 65))}")

if __name__ == "__main__":
    asyncio.run(main())

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

GENERIC_WORDS = set([
    "photo", "photos", "image", "images", "picture", "pictures",
    "outdoor", "outdoors", "indoor", "indoors", "nature", "landscape",
    "sky", "tree", "trees", "grass", "field", "fields", "cloud", "clouds",
    "scene", "scenes", "view", "views", "background", "color", "colors",
    "light", "lighting", "shot", "front", "close-up", "day", "daytime",
    "night", "overall", "small", "large", "high", "low", "wood", "wooden",
    "floor", "table", "wall", "room"
])

def is_meaningful_word(w: str) -> bool:
    clean = w.lower().strip()
    return len(clean) >= 3 and clean not in GENERIC_WORDS

def get_meaningful_words(text: str) -> list[str]:
    if not text:
        return []
    import re
    return [w for w in re.split(r'[\s,._\-:;!?"\'()]+', text.lower()) if is_meaningful_word(w)]

def is_scene_compatible(scene_a: str, scene_b: str) -> bool:
    if not scene_a or not scene_b:
        return True
    sa = scene_a.lower().strip()
    sb = scene_b.lower().strip()
    if sa == sb:
        return True
    is_beach_a = "beach" in sa or "coast" in sa or "ocean" in sa or "sea" in sa or "sunset" in sa
    is_beach_b = "beach" in sb or "coast" in sb or "ocean" in sb or "sea" in sb or "dusk" in sb
    if is_beach_a and is_beach_b:
        return True
    is_mtn_a = "mountain" in sa or "valley" in sa or "hill" in sa or "peak" in sa
    is_mtn_b = "mountain" in sb or "valley" in sb or "hill" in sb or "landscape" in sb
    if is_mtn_a and is_mtn_b:
        return True
    if is_beach_a and ("floor" in sb or "room" in sb or "kitchen" in sb or "office" in sb):
        return False
    if ("floor" in sa or "room" in sa) and is_beach_b:
        return False
    return True

def is_rotated_or_matching_ratio(wA, hA, wB, hB):
    if not wA or not hA or not wB or not hB:
        return True, "SKIPPED (missing dimensions)"
    arA = wA / hA
    arB = wB / hB
    arB_rot = hB / wB
    diff_direct = abs(arA - arB)
    diff_rot = abs(arA - arB_rot)
    if diff_direct <= 0.40 or diff_rot <= 0.40:
        return True, f"PASSED (arA={arA:.2f}, arB={arB:.2f}, diffDirect={diff_direct:.2f}, diffRot={diff_rot:.2f})"
    return False, f"REJECTED (arA={arA:.2f}, arB={arB:.2f}, diffDirect={diff_direct:.2f}, diffRot={diff_rot:.2f})"

def debug_validate_near_duplicate_pair(itemA: MediaAsset, itemB: MediaAsset):
    aiA = itemA.ai_analysis
    aiB = itemB.ai_analysis
    metaA = itemA.photo_metadata
    metaB = itemB.photo_metadata

    print(f"\n========================================================")
    print(f"PAIR EVALUATION: [{itemA.filename}] vs [{itemB.filename}]")
    print(f"========================================================")
    p1 = itemA.p_hash
    p2 = itemB.p_hash
    dist = get_hamming_distance(p1, p2)
    print(f"pHash A: {p1} | pHash B: {p2} | Hamming Distance: {dist}")

    wA = metaA.width if metaA else None
    hA = metaA.height if metaA else None
    wB = metaB.width if metaB else None
    hB = metaB.height if metaB else None
    arA = (wA / hA) if (wA and hA) else None
    arB = (wB / hB) if (wB and hB) else None

    print(f"\n--- Item A [{itemA.filename}] ---")
    print(f"  Dimensions: {wA}x{hA} (AR: {round(arA, 2) if arA else 'None'})")
    print(f"  Caption: '{aiA.caption if aiA else None}'")
    print(f"  Scene: '{aiA.scene if aiA else None}'")
    print(f"  Objects: {aiA.objects if aiA else None}")
    print(f"  Dominant Colors: {aiA.dominant_colors if aiA else None}")

    print(f"\n--- Item B [{itemB.filename}] ---")
    print(f"  Dimensions: {wB}x{hB} (AR: {round(arB, 2) if arB else 'None'})")
    print(f"  Caption: '{aiB.caption if aiB else None}'")
    print(f"  Scene: '{aiB.scene if aiB else None}'")
    print(f"  Objects: {aiB.objects if aiB else None}")
    print(f"  Dominant Colors: {aiB.dominant_colors if aiB else None}")

    print(f"\n--- Validation Rule Decisions ---")

    # 1. Aspect Ratio Rule
    ar_pass, ar_reason = is_rotated_or_matching_ratio(wA, hA, wB, hB)
    print(f"1. Aspect Ratio Rule: {ar_reason}")

    # 2. Scene Rule
    sceneA = (aiA.scene if aiA and aiA.scene else "").lower().strip()
    sceneB = (aiB.scene if aiB and aiB.scene else "").lower().strip()
    if not sceneA or not sceneB:
        scene_decision = "SKIPPED (missing scene metadata)"
        scene_pass = True
    elif sceneA == sceneB:
        scene_decision = f"PASSED (matching scene '{sceneA}')"
        scene_pass = True
    elif is_scene_compatible(sceneA, sceneB):
        scene_decision = f"PASSED (compatible scenes '{sceneA}' vs '{sceneB}')"
        scene_pass = True
    else:
        scene_decision = f"REJECTED (incompatible scenes '{sceneA}' vs '{sceneB}')"
        scene_pass = False
    print(f"2. Scene Rule: {scene_decision}")

    # 3. Dominant Objects Rule
    objsA = [o.lower().strip() for o in (aiA.objects if aiA and aiA.objects else []) if is_meaningful_word(o)]
    objsB = [o.lower().strip() for o in (aiB.objects if aiB and aiB.objects else []) if is_meaningful_word(o)]
    if len(objsA) == 0 or len(objsB) == 0:
        obj_decision = f"SKIPPED (missing/generic objects: objsA={objsA}, objsB={objsB})"
        obj_pass = True
    else:
        common = [o for o in objsA if o in objsB]
        if len(common) > 0:
            obj_decision = f"PASSED (shared objects: {common})"
            obj_pass = True
        else:
            obj_decision = f"REJECTED (no common objects: {objsA} vs {objsB})"
            obj_pass = False
    print(f"3. Objects Rule: {obj_decision}")

    # 4. Caption Rule
    wordsA = get_meaningful_words(aiA.caption if aiA else "")
    wordsB = get_meaningful_words(aiB.caption if aiB else "")
    if len(wordsA) < 3 or len(wordsB) < 3:
        cap_decision = f"SKIPPED (insufficient meaningful words: wordsA={wordsA}, wordsB={wordsB})"
        cap_pass = True
    else:
        common_words = [w for w in wordsA if w in wordsB]
        union_size = len(set(wordsA + wordsB))
        jaccard = len(common_words) / union_size if union_size > 0 else 0
        if jaccard < 0.10 and len(common_words) == 0:
            cap_decision = f"REJECTED (jaccard={jaccard:.2f}, common={common_words})"
            cap_pass = False
        else:
            cap_decision = f"PASSED (jaccard={jaccard:.2f}, common={common_words})"
            cap_pass = True
    print(f"4. Caption Rule: {cap_decision}")

    # 5. Dominant Colors Rule
    colorsA = [c.lower().strip() for c in (aiA.dominant_colors if aiA and aiA.dominant_colors else [])]
    colorsB = [c.lower().strip() for c in (aiB.dominant_colors if aiB and aiB.dominant_colors else [])]
    if len(colorsA) < 2 or len(colorsB) < 2:
        col_decision = f"SKIPPED (insufficient color metadata: colorsA={colorsA}, colorsB={colorsB})"
        col_pass = True
    else:
        common_colors = [c for c in colorsA if c in colorsB]
        if len(common_colors) > 0:
            col_decision = f"PASSED (shared colors: {common_colors})"
            col_pass = True
        else:
            is_mono_a = all("black" in c or "white" in c or "gray" in c for c in colorsA)
            is_mono_b = all("black" in c or "white" in c or "gray" in c for c in colorsB)
            if is_mono_a or is_mono_b:
                col_decision = "PASSED (monochrome edit allowed)"
                col_pass = True
            else:
                col_decision = f"REJECTED (no color overlap: {colorsA} vs {colorsB})"
                col_pass = False
    print(f"5. Dominant Colors Rule: {col_decision}")

    final_valid = ar_pass and scene_pass and obj_pass and cap_pass and col_pass
    print(f"\nFINAL VALIDATION DECISION -> {'ACCEPTED' if final_valid else 'REJECTED'}")
    return final_valid

async def main():
    async with async_session() as db:
        print("Fetching all MediaAssets from database...")
        query = (
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.photo_metadata),
                selectinload(MediaAsset.ai_analysis)
            )
        )
        res = await db.execute(query)
        assets = res.scalars().all()
        print(f"Loaded {len(assets)} assets.")

        # Find near duplicate candidate pairs (dist 1 to 4)
        print("\nScanning for pHash near-duplicate candidate pairs (dist 1..4)...")
        candidate_pairs = []
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
                    candidate_pairs.append((itemA, itemB, dist))

        print(f"Found {len(candidate_pairs)} candidate near-duplicate pairs (dist 1..4).")

        print(f"\nPrinting detailed rule-by-rule debug breakdown for ALL {len(candidate_pairs)} candidate pairs:")
        passing_pairs = []
        for itemA, itemB, dist in candidate_pairs:
            valid = debug_validate_near_duplicate_pair(itemA, itemB)
            if valid:
                passing_pairs.append((itemA, itemB, dist))

        print(f"\n========================================================")
        print(f"TOTAL PAIRS PASSING VALIDATION: {len(passing_pairs)} out of {len(candidate_pairs)}")
        print(f"========================================================")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from sqlalchemy import select, func
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
        return True
    arA = wA / hA
    arB = wB / hB
    arB_rot = hB / wB
    diff_direct = abs(arA - arB)
    diff_rot = abs(arA - arB_rot)
    return diff_direct <= 0.40 or diff_rot <= 0.40

def validate_near_duplicate_pair(itemA: MediaAsset, itemB: MediaAsset) -> bool:
    aiA = itemA.ai_analysis
    aiB = itemB.ai_analysis
    metaA = itemA.photo_metadata
    metaB = itemB.photo_metadata

    wA = metaA.width if metaA else None
    hA = metaA.height if metaA else None
    wB = metaB.width if metaB else None
    hB = metaB.height if metaB else None

    if wA and hA and wB and hB:
        if not is_rotated_or_matching_ratio(wA, hA, wB, hB):
            return False

    sceneA = (aiA.scene if aiA and aiA.scene else "").lower().strip()
    sceneB = (aiB.scene if aiB and aiB.scene else "").lower().strip()
    if sceneA and sceneB and sceneA != sceneB:
        if not is_scene_compatible(sceneA, sceneB):
            return False

    objsA = [o.lower().strip() for o in (aiA.objects if aiA and aiA.objects else []) if is_meaningful_word(o)]
    objsB = [o.lower().strip() for o in (aiB.objects if aiB and aiB.objects else []) if is_meaningful_word(o)]
    if len(objsA) > 0 and len(objsB) > 0:
        common = [o for o in objsA if o in objsB]
        if len(common) == 0:
            return False

    wordsA = get_meaningful_words(aiA.caption if aiA else "")
    wordsB = get_meaningful_words(aiB.caption if aiB else "")
    if len(wordsA) >= 3 and len(wordsB) >= 3:
        common_words = [w for w in wordsA if w in wordsB]
        union_size = len(set(wordsA + wordsB))
        jaccard = len(common_words) / union_size if union_size > 0 else 0
        if jaccard < 0.10 and len(common_words) == 0:
            return False

    colorsA = [c.lower().strip() for c in (aiA.dominant_colors if aiA and aiA.dominant_colors else [])]
    colorsB = [c.lower().strip() for c in (aiB.dominant_colors if aiB and aiB.dominant_colors else [])]
    if len(colorsA) >= 2 and len(colorsB) >= 2:
        common_colors = [c for c in colorsA if c in colorsB]
        if len(common_colors) == 0:
            is_mono_a = all("black" in c or "white" in c or "gray" in c for c in colorsA)
            is_mono_b = all("black" in c or "white" in c or "gray" in c for c in colorsB)
            if not is_mono_a and not is_mono_b:
                return False

    return True

def validate_candidate_pair_similar(itemA: MediaAsset, itemB: MediaAsset):
    aiA = itemA.ai_analysis
    aiB = itemB.ai_analysis

    object_score = 0.5
    objsA = [o.lower().strip() for o in (aiA.objects if aiA and aiA.objects else []) if is_meaningful_word(o)]
    objsB = [o.lower().strip() for o in (aiB.objects if aiB and aiB.objects else []) if is_meaningful_word(o)]
    if len(objsA) > 0 and len(objsB) > 0:
        common = [o for o in objsA if o in objsB]
        object_score = 1.0 if len(common) > 0 else 0.1

    scene_score = 0.5
    sceneA = (aiA.scene if aiA and aiA.scene else "").lower().strip()
    sceneB = (aiB.scene if aiB and aiB.scene else "").lower().strip()
    if sceneA and sceneB:
        if sceneA == sceneB or is_scene_compatible(sceneA, sceneB):
            scene_score = 1.0
        else:
            scene_score = 0.2

    keyword_score = 0.5
    wordsA = get_meaningful_words(aiA.caption if aiA else "") + list((aiA.keywords or {}).keys() if aiA else [])
    wordsB = get_meaningful_words(aiB.caption if aiB else "") + list((aiB.keywords or {}).keys() if aiB else [])
    if len(wordsA) > 0 and len(wordsB) > 0:
        common_w = [w for w in wordsA if w in wordsB]
        union_sz = len(set(wordsA + wordsB))
        jaccard = len(common_w) / union_sz if union_sz > 0 else 0
        keyword_score = 1.0 if jaccard >= 0.2 else 0.2

    ocr_score = 0.5
    people_score = 0.5
    event_score = 0.5

    metadata_consistency = int(round((object_score * 0.35 + scene_score * 0.25 + keyword_score * 0.20 + ocr_score * 0.10 + people_score * 0.05 + event_score * 0.05) * 100))

    is_valid = metadata_consistency >= 40
    return is_valid

async def main():
    async with async_session() as db:
        print("Fetching all READY media assets from PostgreSQL...")
        stmt = (
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.photo_metadata),
                selectinload(MediaAsset.ai_analysis)
            )
            .where(MediaAsset.status == "READY")
        )
        res = await db.execute(stmt)
        active_items = res.scalars().all()
        print(f"Total active items: {len(active_items)}\n")

        # ── 1. EXACT DUPLICATES ───────────────────────────────────────────────
        print("=========================================")
        print("1. EXACT DUPLICATES")
        print("=========================================")
        initial_exact_candidates = 0
        phash_exact_matches = 0
        visited_exact = set()
        exact_duplicate_groups = []
        exact_dup_ids = set()

        for i in range(len(active_items)):
            itemA = active_items[i]
            if itemA.id in visited_exact:
                continue

            current_group = [itemA]
            for j in range(i + 1, len(active_items)):
                itemB = active_items[j]
                if itemB.id in visited_exact:
                    continue

                initial_exact_candidates += 1
                is_dup = False
                if itemA.p_hash and itemB.p_hash:
                    dist = get_hamming_distance(itemA.p_hash, itemB.p_hash)
                    if dist == 0:
                        is_dup = True
                        phash_exact_matches += 1
                else:
                    cleanA = itemA.filename.split('.')[0].lower()
                    cleanB = itemB.filename.split('.')[0].lower()
                    if itemA.file_size == itemB.file_size and cleanA == cleanB:
                        is_dup = True
                        phash_exact_matches += 1

                if is_dup:
                    current_group.append(itemB)
                    visited_exact.add(itemB.id)

            if len(current_group) > 1:
                exact_duplicate_groups.append(current_group)
                visited_exact.add(itemA.id)
                for item in current_group:
                    exact_dup_ids.add(item.id)

        print(f"Initial candidate pairs evaluated: {initial_exact_candidates}")
        print(f"After pHash / metadata match (dist = 0): {phash_exact_matches}")
        print(f"Final groups formed: {len(exact_duplicate_groups)}")
        print(f"Returned groups: {len(exact_duplicate_groups)}")

        # ── 2. NEAR DUPLICATES ─────────────────────────────────────────────────
        print("\n=========================================")
        print("2. NEAR DUPLICATES")
        print("=========================================")
        initial_near_candidates = 0
        phash_near_matches = 0
        ai_validated_near = 0
        visited_near = set()
        near_duplicate_groups = []
        near_dup_ids = set()

        for i in range(len(active_items)):
            itemA = active_items[i]
            if itemA.id in visited_near or itemA.id in exact_dup_ids:
                continue

            current_group = [itemA]
            for j in range(i + 1, len(active_items)):
                itemB = active_items[j]
                if itemB.id in visited_near or itemB.id in exact_dup_ids:
                    continue

                initial_near_candidates += 1
                is_near = False
                if itemA.p_hash and itemB.p_hash:
                    dist = get_hamming_distance(itemA.p_hash, itemB.p_hash)
                    if 1 <= dist <= 4:
                        phash_near_matches += 1
                        if validate_near_duplicate_pair(itemA, itemB):
                            ai_validated_near += 1
                            is_near = True

                if is_near:
                    current_group.append(itemB)
                    visited_near.add(itemB.id)

            if len(current_group) > 1:
                near_duplicate_groups.append(current_group)
                visited_near.add(itemA.id)
                for item in current_group:
                    near_dup_ids.add(item.id)

        print(f"Initial candidate pairs evaluated: {initial_near_candidates}")
        print(f"After pHash filter (1 <= dist <= 4): {phash_near_matches}")
        print(f"After AI validation: {ai_validated_near}")
        print(f"After grouping: {len(near_duplicate_groups)}")
        print(f"Returned groups: {len(near_duplicate_groups)}")

        # ── 3. SIMILAR PHOTOS ─────────────────────────────────────────────────
        print("\n=========================================")
        print("3. SIMILAR PHOTOS")
        print("=========================================")
        filter_items = [i for i in active_items if i.id not in exact_dup_ids and i.id not in near_dup_ids]
        initial_sim_candidates = 0
        ai_validated_sim = 0
        visited_sim = set()
        similar_groups = []

        for i in range(len(filter_items)):
            itemA = filter_items[i]
            if itemA.id in visited_sim:
                continue

            current_group = [itemA]
            for j in range(i + 1, len(filter_items)):
                itemB = filter_items[j]
                if itemB.id in visited_sim:
                    continue

                initial_sim_candidates += 1
                if validate_candidate_pair_similar(itemA, itemB):
                    ai_validated_sim += 1
                    current_group.append(itemB)
                    visited_sim.add(itemB.id)

            if len(current_group) > 1:
                similar_groups.append(current_group)
                visited_sim.add(itemA.id)

        print(f"Total candidate pairs evaluated: {initial_sim_candidates}")
        print(f"After AI signal validation: {ai_validated_sim}")
        print(f"After grouping: {len(similar_groups)}")
        print(f"Returned groups: {len(similar_groups)}")

        # ── 4. DOCUMENTS ───────────────────────────────────────────────────────
        print("\n=========================================")
        print("4. DOCUMENTS")
        print("=========================================")
        total_items_eval = len(active_items)
        passed_doc_type = 0
        passed_ocr_len = 0
        final_docs = []

        for item in active_items:
            doc_type = (item.ai_analysis.document_type if item.ai_analysis and item.ai_analysis.document_type else "").lower()
            ocr_text = item.ai_analysis.detected_text if item.ai_analysis and item.ai_analysis.detected_text else ""

            is_doc_type = bool(doc_type) and doc_type not in {"screenshot", "receipt", "other", "unknown", "none"}
            if is_doc_type:
                passed_doc_type += 1
            is_ocr = len(ocr_text) > 120
            if is_ocr:
                passed_ocr_len += 1

            if is_doc_type or is_ocr:
                final_docs.append(item)

        print(f"Total active items evaluated: {total_items_eval}")
        print(f"Matching document_type filter: {passed_doc_type}")
        print(f"Matching OCR length filter (>120 chars): {passed_ocr_len}")
        print(f"Final items returned: {len(final_docs)}")

        # ── 5. RECEIPTS ────────────────────────────────────────────────────────
        print("\n=========================================")
        print("5. RECEIPTS")
        print("=========================================")
        passed_receipt_doc_type = 0
        passed_receipt_ocr_text = 0
        final_receipts = []

        for item in active_items:
            doc_type = (item.ai_analysis.document_type if item.ai_analysis and item.ai_analysis.document_type else "").lower()
            ocr_text = (item.ai_analysis.detected_text if item.ai_analysis and item.ai_analysis.detected_text else "").lower()

            is_rec_type = doc_type == "receipt"
            if is_rec_type:
                passed_receipt_doc_type += 1

            is_rec_ocr = any(w in ocr_text for w in ["receipt", "invoice", "total", "payment"])
            if is_rec_ocr:
                passed_receipt_ocr_text += 1

            if is_rec_type or is_rec_ocr:
                final_receipts.append(item)

        print(f"Total active items evaluated: {total_items_eval}")
        print(f"Matching document_type == 'receipt': {passed_receipt_doc_type}")
        print(f"Matching receipt OCR keywords (receipt, invoice, total, payment): {passed_receipt_ocr_text}")
        print(f"Final items returned: {len(final_receipts)}")

        # ── 6. IDs ─────────────────────────────────────────────────────────────
        print("\n=========================================")
        print("6. IDs (Passport, Driving License, PAN, Aadhaar)")
        print("=========================================")
        passed_id_keywords = 0
        final_ids = []

        id_kws = ["passport", "driving license", "pan card", "aadhaar", "identity card", "id card"]
        for item in active_items:
            text = (item.ai_analysis.detected_text if item.ai_analysis and item.ai_analysis.detected_text else "").lower()
            caption = (item.ai_analysis.caption if item.ai_analysis and item.ai_analysis.caption else "").lower()

            if any(kw in text or kw in caption for kw in id_kws):
                passed_id_keywords += 1
                final_ids.append(item)

        print(f"Total active items evaluated: {total_items_eval}")
        print(f"Matching ID keywords (passport, driving license, identity card, etc.): {passed_id_keywords}")
        print(f"Final items returned: {len(final_ids)}")

        # ── 7. SCREENSHOTS ─────────────────────────────────────────────────────
        print("\n=========================================")
        print("7. SCREENSHOTS")
        print("=========================================")
        passed_screenshot_filename = 0
        passed_screenshot_caption = 0
        passed_screenshot_doctype = 0
        final_screenshots = []

        for item in active_items:
            fn = item.filename.lower()
            caption = (item.ai_analysis.caption if item.ai_analysis and item.ai_analysis.caption else "").lower()
            doc_type = (item.ai_analysis.document_type if item.ai_analysis and item.ai_analysis.document_type else "").lower()

            is_fn = "screenshot" in fn
            if is_fn:
                passed_screenshot_filename += 1

            is_cap = "screenshot" in caption
            if is_cap:
                passed_screenshot_caption += 1

            is_doc = doc_type == "screenshot"
            if is_doc:
                passed_screenshot_doctype += 1

            if is_fn or is_cap or is_doc:
                final_screenshots.append(item)

        print(f"Total active items evaluated: {total_items_eval}")
        print(f"Matching filename contains 'screenshot': {passed_screenshot_filename}")
        print(f"Matching caption contains 'screenshot': {passed_screenshot_caption}")
        print(f"Matching document_type == 'screenshot': {passed_screenshot_doctype}")
        print(f"Final items returned: {len(final_screenshots)}")

if __name__ == "__main__":
    asyncio.run(main())

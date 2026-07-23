import asyncio
import os
import json
import torch
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.modules.media.models import MediaAsset
from app.modules.media.services.embedding_service import EmbeddingService

labels_obj = [
    "analog clock", "flower garden", "car vehicle", "dog pet", "cat pet",
    "mountain", "tree", "building", "boat vessel", "receipt document", "passport document", "laptop computer", "phone",
    "person people", "food meal", "sandy beach", "bird animal", "bicycle bike", "furniture room"
]

async def main():
    model = EmbeddingService.get_model()

    async with async_session() as db:
        stmt = (
            select(MediaAsset)
            .options(selectinload(MediaAsset.ai_analysis))
            .where(MediaAsset.is_deleted == False)
        )
        res = await db.execute(stmt)
        assets = res.scalars().all()

        total_assets = len(assets)

        dog_objects_count = 0
        cat_objects_count = 0
        dog_caption_count = 0
        cat_caption_count = 0
        dog_keyword_count = 0
        cat_keyword_count = 0

        tagged_dog_files = []
        tagged_cat_files = []
        high_prob_untagged_dog_files = []
        high_prob_untagged_cat_files = []

        for asset in assets:
            ai = asset.ai_analysis
            cap = (ai.caption or "").lower() if ai else ""
            objs = [o.lower() for o in (ai.objects or [])] if ai and ai.objects else []
            kws = [k.lower() for k in (ai.keywords.keys() if isinstance(ai.keywords, dict) else [])] if ai else []

            has_dog_obj = any("dog" in o for o in objs)
            has_cat_obj = any("cat" in o for o in objs)
            has_dog_cap = "dog" in cap
            has_cat_cap = "cat" in cap
            has_dog_kw = any("dog" in k for k in kws)
            has_cat_kw = any("cat" in k for k in kws)

            if has_dog_obj: dog_objects_count += 1
            if has_cat_obj: cat_objects_count += 1
            if has_dog_cap: dog_caption_count += 1
            if has_cat_cap: cat_caption_count += 1
            if has_dog_kw: dog_keyword_count += 1
            if has_cat_kw: cat_keyword_count += 1

            if has_dog_obj or has_dog_cap or has_dog_kw:
                tagged_dog_files.append((asset.filename, cap, objs, kws))
            if has_cat_obj or has_cat_cap or has_cat_kw:
                tagged_cat_files.append((asset.filename, cap, objs, kws))

            # Also check if filename has dog/cat
            fn_lower = asset.filename.lower()
            is_dog_fn = "dog" in fn_lower or "puppy" in fn_lower
            is_cat_fn = "cat" in fn_lower or "kitten" in fn_lower

            if (is_dog_fn and not (has_dog_obj or has_dog_cap or has_dog_kw)) or (is_cat_fn and not (has_cat_obj or has_cat_cap or has_cat_kw)):
                # Evaluate CLIP
                storage_path = asset.original_path
                if not os.path.exists(storage_path):
                    alt_path = os.path.join("/storage", storage_path.lstrip("/"))
                    if os.path.exists(alt_path):
                        storage_path = alt_path

                if os.path.exists(storage_path):
                    try:
                        img = Image.open(storage_path).convert("RGB")
                        img_emb = model.encode(img, convert_to_tensor=True)
                        obj_embs = model.encode(labels_obj, convert_to_tensor=True)
                        probs_obj = (img_emb @ obj_embs.T).softmax(dim=-1).tolist()
                        prob_dict = {labels_obj[i]: round(probs_obj[i], 4) for i in range(len(labels_obj))}
                        top_idx = probs_obj.index(max(probs_obj))
                        top_label = labels_obj[top_idx]

                        if is_dog_fn:
                            high_prob_untagged_dog_files.append({
                                "filename": asset.filename,
                                "raw_clip_probs": prob_dict,
                                "selected_object": top_label,
                                "stored_caption": cap,
                                "stored_objects": objs
                            })
                        if is_cat_fn:
                            high_prob_untagged_cat_files.append({
                                "filename": asset.filename,
                                "raw_clip_probs": prob_dict,
                                "selected_object": top_label,
                                "stored_caption": cap,
                                "stored_objects": objs
                            })
                    except Exception:
                        pass

        # Also sample top CLIP dog/cat candidate probabilities across all images if any
        report = {
            "total_assets": total_assets,
            "counts": {
                "dog_objects_count": dog_objects_count,
                "cat_objects_count": cat_objects_count,
                "dog_caption_count": dog_caption_count,
                "cat_caption_count": cat_caption_count,
                "dog_keyword_count": dog_keyword_count,
                "cat_keyword_count": cat_keyword_count
            },
            "tagged_dog_files": tagged_dog_files,
            "tagged_cat_files": tagged_cat_files,
            "untagged_dog_files": high_prob_untagged_dog_files,
            "untagged_cat_files": high_prob_untagged_cat_files
        }

        with open("/storage/dog_cat_investigation.json", "w") as f:
            json.dump(report, f, indent=2)

        print("Investigation complete! Written to /storage/dog_cat_investigation.json")

if __name__ == "__main__":
    asyncio.run(main())

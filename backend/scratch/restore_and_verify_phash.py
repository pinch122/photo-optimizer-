import asyncio
import os
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.modules.media.models import MediaAsset, ImageAIAnalysis

def compute_phash(img: Image.Image) -> str:
    """
    Compute a 16-character hexadecimal perceptual hash (pHash)
    using pure Pillow image operations. Zero external dependencies.
    """
    gray = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    avg = sum(pixels) / 64.0
    bits = "".join(["1" if p >= avg else "0" for p in pixels])
    return f"{int(bits, 2):016x}"

async def main():
    async with async_session() as db:
        print("=== RESTORING AND PERSISTING pHASH ACROSS ALL ASSETS ===")
        stmt = (
            select(MediaAsset)
            .options(selectinload(MediaAsset.ai_analysis))
            .where(MediaAsset.status == "READY")
        )
        res = await db.execute(stmt)
        assets = res.scalars().all()

        total = len(assets)
        restored = 0
        failed = 0

        for a in assets:
            if not a.original_path or not os.path.exists(a.original_path):
                failed += 1
                continue

            try:
                img = Image.open(a.original_path)
                ph = compute_phash(img)

                if not a.ai_analysis:
                    a.ai_analysis = ImageAIAnalysis(
                        media_asset_id=a.id,
                        keywords={"p_hash": ph}
                    )
                    db.add(a.ai_analysis)
                else:
                    current_kw = dict(a.ai_analysis.keywords or {})
                    current_kw["p_hash"] = ph
                    a.ai_analysis.keywords = current_kw

                restored += 1
            except Exception as e:
                print(f"Failed pHash for asset [{a.id}]: {e}")
                failed += 1

        await db.commit()
        print(f"Restoration Complete: {restored}/{total} assets updated with valid 16-char pHash ({failed} failed/missing).\n")

        # Verify sample pHashes
        res_verify = await db.execute(stmt)
        verified_assets = res_verify.scalars().all()

        valid_count = 0
        for i, va in enumerate(verified_assets[:20]):
            ph = va.p_hash
            is_valid = bool(ph and len(ph) == 16)
            if is_valid:
                valid_count += 1
            print(f"Verified Asset #{i+1} [{va.filename}]: p_hash = '{ph}' (Valid: {is_valid})")

        print(f"\n20-Sample Validation: {valid_count}/20 valid 16-char hex pHashes.")

if __name__ == "__main__":
    asyncio.run(main())

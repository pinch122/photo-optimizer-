import asyncio
from app.database import async_session
from app.modules.media.services.rebuild_ai_metadata_service import RebuildAIMetadataService

async def main():
    async with async_session() as db:
        print("=== Triggering AI Metadata Rebuild for all assets ===")
        res = await RebuildAIMetadataService.rebuild_all_metadata(db)
        print(f"Rebuild Result: {res}")

if __name__ == "__main__":
    asyncio.run(main())

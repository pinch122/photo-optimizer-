import asyncio
from app.database import async_session
from app.modules.media.services.search_service import SearchService

async def main():
    async with async_session() as db:
        test_queries = ["receipt", "flowers", "beach", "mountains", "dog", "car"]
        print("=== Testing Search Validation Policy ===")
        for q in test_queries:
            res = await SearchService.search_media(db, q, limit=5, offset=0)
            items_count = len(res["items"])
            msg = res.get("message")
            print(f"Query: '{q}' -> Results Count: {items_count} | Message: {msg}")
            if items_count > 0:
                top = res['items'][0]
                print(f"   Top item: {top.filename} (score: {top.score:.4f})")
                print(f"   Explanations: {top.explanation}")
            print("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())

from resync.core.async_cache import AsyncTTLCache
import asyncio


async def test():
    cache = AsyncTTLCache()
    await cache.stop()
    print("Cache initialized successfully")


if __name__ == "__main__":
    asyncio.run(test())

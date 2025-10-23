import tempfile
from pathlib import Path
from resync.core.async_cache import AsyncTTLCache
import asyncio


async def test_wal_simple():
    with tempfile.TemporaryDirectory() as temp_dir:
        wal_path = Path(temp_dir) / "wal_test"

        # Create cache with WAL enabled
        cache = AsyncTTLCache(ttl_seconds=10, enable_wal=True, wal_path=wal_path)

        # Perform some operations
        await cache.set("test_key1", "test_value1", ttl_seconds=5)
        result = await cache.get("test_key1")
        print(f"Retrieved value: {result}")

        # Clean up
        await cache.stop()
        if cache.wal:
            await cache.wal.close()

        print("WAL test completed successfully")


if __name__ == "__main__":
    asyncio.run(test_wal_simple())

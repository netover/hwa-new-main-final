#!/usr/bin/env python3
"""
Simple test script to verify unified cache implementation works correctly.
"""

import asyncio
import logging

from resync.core.cache import CacheFactory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_cache_operations():
    """Test basic cache operations."""
    logger.info("Testing basic cache operations...")

    # Create a simple unified cache
    cache = CacheFactory.create_memory_cache(ttl_seconds=5)
    await cache.initialize()

    try:
        # Test set and get
        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1", f"Expected 'value1', got {value}"
        logger.info("✓ Basic set/get works")

        # Test get with default
        value = await cache.get("nonexistent", "default")
        assert value == "default", f"Expected 'default', got {value}"
        logger.info("✓ Get with default works")

        # Test delete
        deleted = await cache.delete("key1")
        assert deleted is True, "Expected delete to return True"
        value = await cache.get("key1")
        assert value is None, f"Expected None after delete, got {value}"
        logger.info("✓ Delete works")

        # Test clear
        await cache.set("key2", "value2")
        await cache.clear()
        value = await cache.get("key2")
        assert value is None, f"Expected None after clear, got {value}"
        logger.info("✓ Clear works")

    finally:
        await cache.shutdown()


async def main():
    """Run all tests."""
    logger.info("Starting unified cache tests...")

    try:
        await test_basic_cache_operations()
        logger.info("✅ All tests passed!")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())





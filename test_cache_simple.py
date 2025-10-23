"""
Teste simples para validar as melhorias no cache assíncrono.
"""
import asyncio
import os
import sys
from pathlib import Path

# Set environment variable to avoid settings validation error
os.environ["ADMIN_PASSWORD"] = "test_password_123"

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_cache_improvements():
    """Test basic cache functionality with improvements."""
    try:
        # Set environment variable to avoid settings validation error
        import os
        os.environ["ADMIN_PASSWORD"] = "test_password_123"
        from resync.core.cache.async_cache_refactored import AsyncTTLCache
        
        print("Creating cache...")
        # Set environment variable to avoid settings validation error
        import os
        os.environ["ADMIN_PASSWORD"] = "test_password_123"
        cache = AsyncTTLCache(ttl_seconds=60, num_shards=4)
        
        print("Testing set operation...")
        await cache.set("test_key", "test_value")
        
        print("Testing get operation...")
        value = await cache.get("test_key")
        assert value == "test_value", f"Expected 'test_value', got {value}"
        
        print("Testing hot shards detection...")
        hot_shards = cache.get_hot_shards()
        assert isinstance(hot_shards, list), f"Expected list, got {type(hot_shards)}"
        
        print("Testing detailed metrics...")
        metrics = cache.get_detailed_metrics()
        assert "lock_contention" in metrics, "lock_contention not in metrics"
        assert "hot_shards" in metrics, "hot_shards not in metrics"
        
        print("Testing delete operation...")
        result = await cache.delete("test_key")
        assert result == True, "Delete operation failed"
        
        print("All tests passed!")
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_cache_improvements())
    sys.exit(0 if success else 1)
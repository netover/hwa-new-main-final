#!/usr/bin/env python3
"""Simple import test for refactored cache."""

print('Testing imports for refactored cache...')
try:
    from resync.core.async_cache_refactored import AsyncTTLCache
    from resync.core.cache.strategies import CacheSetStrategy, CacheRollbackStrategy, CacheRestoreStrategy
    from resync.core.cache.memory_manager import CacheMemoryManager
    from resync.core.cache.persistence_manager import CachePersistenceManager
    from resync.core.cache.transaction_manager import CacheTransactionManager
    print('✅ All imports successful!')

    # Test basic instantiation
    cache = AsyncTTLCache()
    print(f'✅ Cache instantiated: {cache.num_shards} shards, {cache.size()} entries')

    print('🎉 Import and instantiation tests passed!')
except Exception as e:
    print(f'❌ Import test failed: {e}')
    import traceback
    traceback.print_exc()
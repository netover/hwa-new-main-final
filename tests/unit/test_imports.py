#!/usr/bin/env python3
"""Simple import test for refactored cache."""

print('Testing imports for refactored cache...')
try:
    from resync.core.async_cache_refactored import AsyncTTLCache
    print('✅ All imports successful!')

    # Test basic instantiation
    cache = AsyncTTLCache()
    print(f'✅ Cache instantiated: {cache.num_shards} shards, {cache.size()} entries')

    print('🎉 Import and instantiation tests passed!')
except Exception as e:
    print(f'❌ Import test failed: {e}')
    import traceback
    traceback.print_exc()





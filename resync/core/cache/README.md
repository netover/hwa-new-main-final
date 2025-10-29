# Unified Cache Implementation

This document describes the unified cache implementation that consolidates all cache functionality in the resync project.

## Overview

The unified cache implementation (`UnifiedAsyncCache`) consolidates all the unique features from the various cache implementations that were previously scattered across the project. This provides a single, robust cache solution with all the best features from the existing implementations.

## Features

### Core Functionality
- **Async operations**: All cache operations are fully async for non-blocking behavior
- **TTL support**: Time-to-live support for automatic expiration
- **Sharded locks**: Concurrent access protection using sharded asyncio.Lock
- **Background cleanup**: Automatic cleanup of expired entries

### Advanced Features
- **Two-tier hierarchy**: Optional L1 (in-memory) + L2 (Redis-backed) caching
- **Memory bounds checking**: Intelligent memory usage management with configurable limits
- **LRU eviction**: Least Recently Used eviction policy
- **Stampede protection**: Configurable protection against cache stampede (none, basic, aggressive)
- **Comprehensive metrics**: Detailed performance and usage metrics
- **WAL support**: Write-Ahead Logging for persistence and crash recovery
- **Transaction support**: Atomic multi-key operations with rollback capability
- **Snapshot/restore**: Cache state persistence for warm starts

## Usage

### Basic Usage

```python
from resync.core.cache import CacheFactory, UnifiedAsyncCache

# Create a simple cache
cache = CacheFactory.create_memory_cache(ttl_seconds=300)
await cache.initialize()

# Use the cache
await cache.set("key", "value")
value = await cache.get("key")
await cache.delete("key")
await cache.clear()
await cache.shutdown()
```

### Hierarchy Cache

```python
# Create a two-tier cache
cache = CacheFactory.create_hierarchy_cache(
    l1_max_size=5000,
    l2_ttl_seconds=600
)
await cache.initialize()

# Use the hierarchy cache
await cache.set("key", "value")
value = await cache.get("key")  # Checks L1 first, then L2
```

### High-Performance Cache

```python
# Create a high-performance cache
cache = CacheFactory.create_high_performance_cache(
    num_shards=32,
    eviction_batch_size=200
)
await cache.initialize()
```

### Persistent Cache

```python
# Create a persistent cache
cache = CacheFactory.create_persistent_cache(
    enable_wal=True,
    snapshot_dir="./cache_snapshots"
)
await cache.initialize()

# Create snapshots
await cache.snapshot()

# Restore from snapshot
await cache.restore()
```

### Cache with Stampede Protection

```python
# Create a cache with stampede protection
cache = CacheFactory.create_unified_cache(
    stampede_protection="aggressive"
)
await cache.initialize()

# Use with loader function
async def load_data():
    # Expensive operation
    return "loaded_data"

value = await cache.get_with_loader("key", load_data)
# Only one call to load_data() will be made even with concurrent requests
```

### Configuration

The cache can be configured with various options:

```python
from resync.core.cache import UnifiedCacheConfig

config = UnifiedCacheConfig(
    ttl_seconds=300,           # 5 minutes
    cleanup_interval=60,        # 1 minute
    max_entries=100000,        # 100K entries
    max_memory_mb=100,          # 100MB
    enable_hierarchy=False,       # Disable two-tier hierarchy
    enable_wal=False,           # Disable WAL
    stampede_protection="basic", # Basic stampede protection
    enable_metrics=True,          # Enable Prometheus metrics
)

cache = UnifiedAsyncCache(config)
```

## Migration from Legacy Implementations

To migrate from legacy cache implementations:

1. Replace imports:
   ```python
   # Old
   from resync.core.async_cache import AsyncTTLCache
   
   # New
   from resync.core.cache import UnifiedAsyncCache, CacheFactory
   ```

2. Update instantiation:
   ```python
   # Old
   cache = AsyncTTLCache()
   
   # New
   cache = CacheFactory.create_memory_cache()
   ```

3. Update method calls:
   ```python
   # Old
   await cache.set(key, value)
   
   # New
   await cache.set(key, value)
   ```

## Benefits

1. **Reduced Complexity**: Single implementation instead of multiple scattered ones
2. **Improved Maintainability**: Easier to understand and modify
3. **Better Performance**: Optimized implementation with all best features
4. **Consistent Behavior**: Unified interface across all cache usage
5. **Easier Testing**: Single implementation to test instead of multiple
6. **Future-Proof**: Extensible design for new features

## Deprecation

Legacy cache implementations have been moved to `resync/core/cache/legacy/` and will show deprecation warnings when imported:

```
resync.core.cache.legacy.async_cache is deprecated. 
Please use resync.core.cache.unified_cache.UnifiedAsyncCache instead.
```

## Testing

Run the test script to verify functionality:

```bash
python test_unified_cache.py
```

This will test basic cache operations and confirm the implementation works correctly.




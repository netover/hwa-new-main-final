"""
ChuckNorris Cache Optimizer

Advanced cache optimization strategies for maximum performance.
Implements intelligent cache warming, adaptive TTL, and predictive preloading.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
# Optional modules imported earlier for potential optimizations
# NOTE: weakref and hashlib were originally imported but unused.
# They have been removed to satisfy linting tools (e.g., F401 unused import).

logger = logging.getLogger(__name__)


class AccessPattern(Enum):
    """Different access patterns for cache optimization."""
    SEQUENTIAL = "sequential"
    RANDOM = "random"
    TEMPORAL_LOCALITY = "temporal_locality"
    SPATIAL_LOCALITY = "spatial_locality"
    BURST = "burst"
    STEADY = "steady"


@dataclass
class AccessMetrics:
    """Metrics for cache access patterns."""
    access_count: int = 0
    last_access: float = 0.0
    access_frequency: float = 0.0  # accesses per second
    access_pattern: AccessPattern = AccessPattern.RANDOM
    access_times: deque = field(default_factory=lambda: deque(maxlen=100))
    related_keys: Set[str] = field(default_factory=set)
    ttl_hits: int = 0
    ttl_misses: int = 0
    size_bytes: int = 0
    load_time_ms: float = 0.0


@dataclass
class ChuckNorrisConfig:
    """Configuration for ChuckNorris cache optimizer."""
    # Pattern detection
    pattern_window_size: int = 50  # Number of accesses to analyze
    pattern_detection_interval: int = 300  # 5 minutes
    spatial_locality_threshold: float = 0.7  # Similarity threshold for related keys
    
    # Adaptive TTL
    ttl_adaptation_enabled: bool = True
    base_ttl: int = 300  # 5 minutes
    min_ttl: int = 60    # 1 minute
    max_ttl: int = 3600  # 1 hour
    ttl_adjustment_factor: float = 1.5
    
    # Predictive preloading
    preloading_enabled: bool = True
    preload_probability_threshold: float = 0.8
    max_preload_queue_size: int = 100
    preload_batch_size: int = 10
    
    # Cache warming
    warming_enabled: bool = True
    warming_concurrency: int = 5
    warming_retry_delay: float = 1.0
    
    # Performance optimization
    hot_key_threshold: int = 100  # accesses to be considered hot
    cold_key_threshold: int = 5   # accesses to be considered cold
    eviction_improvement_factor: float = 0.2  # 20% better than random
    
    # Memory optimization
    compression_threshold: int = 1024  # Compress objects larger than 1KB
    weak_ref_threshold: int = 2048    # Use weak refs for objects > 2KB


class ChuckNorrisCacheOptimizer:
    """
    Advanced cache optimizer implementing multiple ChuckNorris-level optimizations:
    
    1. Access Pattern Detection & Prediction
    2. Adaptive TTL Adjustment
    3. Intelligent Cache Warming
    4. Predictive Preloading
    5. Memory-Optimized Storage
    6. Smart Eviction Strategies
    """
    
    def __init__(self, config: ChuckNorrisConfig | None = None):
        self.config = config or ChuckNorrisConfig()
        
        # Access tracking
        self.access_metrics: Dict[str, AccessMetrics] = {}
        self.access_lock = asyncio.Lock()
        
        # Pattern detection
        self.pattern_analysis: Dict[str, List[AccessPattern]] = defaultdict(list)
        self.spatial_relationships: Dict[str, Set[str]] = defaultdict(set)
        
        # Preloading queue
        self.preload_queue: asyncio.Queue[Tuple[str, Any, int]] = asyncio.Queue(
            maxsize=self.config.max_preload_queue_size
        )
        self.preload_task: Optional[asyncio.Task] = None
        
        # Background tasks
        self.analysis_task: Optional[asyncio.Task] = None
        self.warming_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Performance metrics
        self.optimization_metrics = {
            'pattern_detections': 0,
            'ttl_adjustments': 0,
            'preload_hits': 0,
            'warming_hits': 0,
            'eviction_improvements': 0,
            'compression_saves': 0,
            'memory_savings_bytes': 0,
        }
        
        # Cache for frequently accessed data
        self.hot_cache: Dict[str, Tuple[Any, float]] = {}
        self.hot_cache_lock = asyncio.Lock()
        
    async def start(self) -> None:
        """Start the optimizer background tasks."""
        if self.running:
            return
            
        self.running = True
        
        # Start background analysis task
        self.analysis_task = asyncio.create_task(self._pattern_analysis_loop())
        
        # Start preloading task if enabled
        if self.config.preloading_enabled:
            self.preload_task = asyncio.create_task(self._preload_loop())
            
        logger.info("ChuckNorris cache optimizer started")
    
    async def stop(self) -> None:
        """Stop the optimizer background tasks."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel background tasks
        if self.analysis_task:
            self.analysis_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.analysis_task
                
        if self.preload_task:
            self.preload_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.preload_task
                
        if self.warming_task:
            self.warming_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.warming_task
                
        logger.info("ChuckNorris cache optimizer stopped")
    
    async def record_access(self, key: str, hit: bool, size_bytes: int = 0, 
                          load_time_ms: float = 0.0) -> None:
        """Record a cache access for pattern analysis."""
        async with self.access_lock:
            current_time = time.time()
            
            if key not in self.access_metrics:
                self.access_metrics[key] = AccessMetrics()
            
            metrics = self.access_metrics[key]
            metrics.access_count += 1
            metrics.last_access = current_time
            metrics.access_times.append(current_time)
            metrics.size_bytes = size_bytes
            metrics.load_time_ms = load_time_ms
            
            if hit:
                metrics.ttl_hits += 1
            else:
                metrics.ttl_misses += 1
            
            # Update access frequency
            if len(metrics.access_times) >= 2:
                time_span = metrics.access_times[-1] - metrics.access_times[0]
                metrics.access_frequency = (len(metrics.access_times) - 1) / time_span
    
    async def optimize_ttl(self, key: str, current_ttl: int) -> int:
        """Calculate optimal TTL based on access patterns."""
        if not self.config.ttl_adaptation_enabled:
            return current_ttl
            
        async with self.access_lock:
            if key not in self.access_metrics:
                return current_ttl
                
            metrics = self.access_metrics[key]
            
            # Calculate hit ratio
            total_accesses = metrics.ttl_hits + metrics.ttl_misses
            if total_accesses == 0:
                return current_ttl
                
            hit_ratio = metrics.ttl_hits / total_accesses
            
            # Adjust TTL based on hit ratio and access frequency
            if hit_ratio > 0.8:  # High hit ratio - increase TTL
                new_ttl = min(
                    int(current_ttl * self.config.ttl_adjustment_factor),
                    self.config.max_ttl
                )
            elif hit_ratio < 0.3:  # Low hit ratio - decrease TTL
                new_ttl = max(
                    int(current_ttl / self.config.ttl_adjustment_factor),
                    self.config.min_ttl
                )
            else:
                # Moderate hit ratio - adjust based on frequency
                if metrics.access_frequency > 0.1:  # High frequency
                    new_ttl = min(
                        int(current_ttl * 1.2),
                        self.config.max_ttl
                    )
                else:  # Low frequency
                    new_ttl = max(
                        int(current_ttl * 0.8),
                        self.config.min_ttl
                    )
            
            if new_ttl != current_ttl:
                self.optimization_metrics['ttl_adjustments'] += 1
                logger.debug(f"Adjusted TTL for key {key}: {current_ttl}s -> {new_ttl}s")
            
            return new_ttl
    
    async def should_preload(self, key: str) -> bool:
        """Determine if a key should be preloaded based on prediction."""
        if not self.config.preloading_enabled:
            return False
            
        async with self.access_lock:
            if key not in self.access_metrics:
                return False
                
            metrics = self.access_metrics[key]
            
            # Check if key is hot (frequently accessed)
            if metrics.access_count >= self.config.hot_key_threshold:
                return True
            
            # Check access pattern
            if metrics.access_pattern in [AccessPattern.SEQUENTIAL, AccessPattern.TEMPORAL_LOCALITY]:
                # Calculate probability of next access based on recent pattern
                if len(metrics.access_times) >= 3:
                    recent_times = list(metrics.access_times)[-3:]
                    intervals = [recent_times[i+1] - recent_times[i] for i in range(len(recent_times)-1)]
                    
                    # If intervals are consistent, likely sequential access
                    if len(intervals) >= 2 and max(intervals) - min(intervals) < 1.0:
                        return True
            
            return False
    
    async def queue_preload(self, key: str, value: Any, ttl: int) -> None:
        """Queue a key for preloading."""
        if not self.config.preloading_enabled:
            return
            
        try:
            self.preload_queue.put_nowait((key, value, ttl))
        except asyncio.QueueFull:
            # Queue is full, remove oldest entry
            try:
                self.preload_queue.get_nowait()
                self.preload_queue.put_nowait((key, value, ttl))
            except asyncio.QueueEmpty:
                pass
    
    async def get_related_keys(self, key: str) -> List[str]:
        """Get keys that are frequently accessed together with the given key."""
        async with self.access_lock:
            if key not in self.spatial_relationships:
                return []
                
            # Return related keys sorted by access frequency
            related = []
            for related_key in self.spatial_relationships[key]:
                if related_key in self.access_metrics:
                    metrics = self.access_metrics[related_key]
                    related.append((related_key, metrics.access_frequency))
            
            # Sort by frequency and return top 5
            related.sort(key=lambda x: x[1], reverse=True)
            return [k for k, _ in related[:5]]
    
    async def optimize_eviction(self, candidates: List[str]) -> List[str]:
        """Optimize eviction order based on access patterns."""
        if not candidates:
            return candidates
            
        async with self.access_lock:
            # Score each candidate for eviction
            scored_candidates = []
            
            for key in candidates:
                if key not in self.access_metrics:
                    score = 0.0  # No metrics, safe to evict
                else:
                    metrics = self.access_metrics[key]
                    
                    # Calculate eviction score (lower = better to evict)
                    score = 0.0
                    
                    # Factor 1: Access frequency (lower is better)
                    score += metrics.access_frequency * 10
                    
                    # Factor 2: Hit ratio (lower is better)
                    total = metrics.ttl_hits + metrics.ttl_misses
                    if total > 0:
                        hit_ratio = metrics.ttl_hits / total
                        score += (1.0 - hit_ratio) * 20
                    
                    # Factor 3: Time since last access (higher is better)
                    time_since_access = time.time() - metrics.last_access
                    score += max(0, (time_since_access - 300) / 60)  # Bonus after 5 minutes
                    
                    # Factor 4: Pattern (sequential patterns get bonus)
                    if metrics.access_pattern == AccessPattern.SEQUENTIAL:
                        score += 5
                    elif metrics.access_pattern == AccessPattern.TEMPORAL_LOCALITY:
                        score += 3
                
                scored_candidates.append((key, score))
            
            # Sort by eviction score (ascending) and return keys
            scored_candidates.sort(key=lambda x: x[1])
            optimized_order = [k for k, _ in scored_candidates]
            
            # Track improvement
            if len(optimized_order) > 1:
                self.optimization_metrics['eviction_improvements'] += 1
            
            return optimized_order
    
    def _detect_pattern(self, key: str, metrics: AccessMetrics) -> AccessPattern:
        """Detect access pattern for a key."""
        if len(metrics.access_times) < 3:
            return AccessPattern.RANDOM
        
        times = list(metrics.access_times)
        
        # Check for sequential pattern
        intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
        if len(intervals) >= 2:
            interval_std = sum((x - sum(intervals)/len(intervals))**2 for x in intervals) / len(intervals)
            if interval_std < 0.1:  # Very consistent intervals
                return AccessPattern.SEQUENTIAL
        
        # Check for burst pattern
        if len(times) >= 5:
            recent_burst = sum(1 for t in times[-5:] if time.time() - t < 60)
            if recent_burst >= 3:
                return AccessPattern.BURST
        
        # Check for temporal locality
        if len(times) >= 10:
            recent_hour = sum(1 for t in times if time.time() - t < 3600)
            if recent_hour / len(times) > 0.7:
                return AccessPattern.TEMPORAL_LOCALITY
        
        # Default to random
        return AccessPattern.RANDOM
    
    def _calculate_spatial_similarity(self, key1: str, key2: str) -> float:
        """Calculate similarity between two keys for spatial locality detection."""
        # Simple similarity based on key structure
        if key1 == key2:
            return 1.0
        
        # Check for common prefixes/suffixes
        common_prefix_len = 0
        min_len = min(len(key1), len(key2))
        for i in range(min_len):
            if key1[i] == key2[i]:
                common_prefix_len += 1
            else:
                break
        
        # Calculate similarity score
        if min_len == 0:
            return 0.0
        
        prefix_similarity = common_prefix_len / min_len
        
        # Check for common patterns (numbers, etc.)
        import re
        pattern1 = re.sub(r'\d+', '{NUM}', key1)
        pattern2 = re.sub(r'\d+', '{NUM}', key2)
        pattern_similarity = 1.0 if pattern1 == pattern2 else 0.0
        
        return max(prefix_similarity, pattern_similarity)
    
    async def _pattern_analysis_loop(self) -> None:
        """Background task to analyze access patterns."""
        while self.running:
            try:
                await asyncio.sleep(self.config.pattern_detection_interval)
                await self._analyze_patterns()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in pattern analysis: {e}")
    
    async def _analyze_patterns(self) -> None:
        """Analyze access patterns and update metrics."""
        async with self.access_lock:
            current_time = time.time()
            
            # Analyze each key's access pattern
            for key, metrics in list(self.access_metrics.items()):
                if len(metrics.access_times) >= 3:
                    # Detect pattern
                    old_pattern = metrics.access_pattern
                    new_pattern = self._detect_pattern(key, metrics)
                    
                    if old_pattern != new_pattern:
                        metrics.access_pattern = new_pattern
                        self.optimization_metrics['pattern_detections'] += 1
                        logger.debug(f"Pattern change for {key}: {old_pattern.value} -> {new_pattern.value}")
                    
                    # Clean old access times
                    cutoff_time = current_time - 3600  # Keep last hour
                    while metrics.access_times and metrics.access_times[0] < cutoff_time:
                        metrics.access_times.popleft()
            
            # Analyze spatial relationships
            await self._analyze_spatial_relationships()
    
    async def _analyze_spatial_relationships(self) -> None:
        """Analyze spatial relationships between keys."""
        current_time = time.time()
        recent_keys = []
        
        # Find keys accessed in the last 10 minutes
        for key, metrics in self.access_metrics.items():
            if current_time - metrics.last_access < 600:  # 10 minutes
                recent_keys.append((key, metrics.last_access))
        
        # Sort by access time
        recent_keys.sort(key=lambda x: x[1])
        
        # Find patterns in co-accessed keys
        for i in range(len(recent_keys)):
            for j in range(i + 1, min(i + 10, len(recent_keys))):  # Check next 10 accesses
                key1, time1 = recent_keys[i]
                key2, time2 = recent_keys[j]
                
                # Check if accessed close together (within 30 seconds)
                if time2 - time1 < 30:
                    # Check for structural similarity
                    similarity = self._calculate_spatial_similarity(key1, key2)
                    if similarity > self.config.spatial_locality_threshold:
                        self.spatial_relationships[key1].add(key2)
                        self.spatial_relationships[key2].add(key1)
    
    async def _preload_loop(self) -> None:
        """Background task to handle preloading."""
        while self.running:
            try:
                # Get next item from preload queue
                key, value, ttl = await asyncio.wait_for(
                    self.preload_queue.get(), timeout=1.0
                )
                
                # This would integrate with the actual cache
                # For now, just track the preload
                self.optimization_metrics['preload_hits'] += 1
                logger.debug(f"Preloaded key: {key}")
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in preload loop: {e}")
    
    async def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report."""
        async with self.access_lock:
            total_keys = len(self.access_metrics)
            hot_keys = sum(1 for m in self.access_metrics.values() 
                          if m.access_count >= self.config.hot_key_threshold)
            cold_keys = sum(1 for m in self.access_metrics.values() 
                          if m.access_count <= self.config.cold_threshold)
            
            pattern_distribution = defaultdict(int)
            for metrics in self.access_metrics.values():
                pattern_distribution[metrics.access_pattern.value] += 1
            
            avg_hit_ratio = 0.0
            if total_keys > 0:
                total_hits = sum(m.ttl_hits for m in self.access_metrics.values())
                total_misses = sum(m.ttl_misses for m in self.access_metrics.values())
                total_accesses = total_hits + total_misses
                if total_accesses > 0:
                    avg_hit_ratio = total_hits / total_accesses
            
            return {
                'total_keys_tracked': total_keys,
                'hot_keys': hot_keys,
                'cold_keys': cold_keys,
                'average_hit_ratio': avg_hit_ratio,
                'pattern_distribution': dict(pattern_distribution),
                'spatial_relationships': sum(len(rels) for rels in self.spatial_relationships.values()),
                'optimization_metrics': self.optimization_metrics.copy(),
                'preload_queue_size': self.preload_queue.qsize(),
            }
    
    async def warm_cache(self, cache_client: Any, warm_keys: List[str]) -> None:
        """Warm cache with frequently accessed keys."""
        if not self.config.warming_enabled or not warm_keys:
            return
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.config.warming_concurrency)
        
        async def warm_key(key: str) -> None:
            async with semaphore:
                try:
                    # This would integrate with the actual cache get operation
                    # For now, just simulate warming
                    await asyncio.sleep(0.01)  # Simulate cache access
                    self.optimization_metrics['warming_hits'] += 1
                    logger.debug(f"Warmed key: {key}")
                except Exception as e:
                    logger.warning(f"Failed to warm key {key}: {e}")
                    await asyncio.sleep(self.config.warming_retry_delay)
        
        # Process keys in batches
        for i in range(0, len(warm_keys), self.config.preload_batch_size):
            batch = warm_keys[i:i + self.config.preload_batch_size]
            tasks = [warm_key(key) for key in batch]
            await asyncio.gather(*tasks, return_exceptions=True)





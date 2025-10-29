"""
ChuckNorris Batch Processor

Advanced async batch processing with intelligent queuing,
adaptive batching, and optimized resource utilization.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import weakref
import statistics

logger = logging.getLogger(__name__)


class BatchStrategy(Enum):
    """Different batching strategies."""
    TIME_BASED = "time_based"           # Batch by time window
    SIZE_BASED = "size_based"          # Batch by item count
    ADAPTIVE = "adaptive"                # Adaptive batching
    PRIORITY_BASED = "priority_based"     # Batch by priority
    LOAD_AWARE = "load_aware"           # Based on system load


class BatchPriority(Enum):
    """Batch processing priorities."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    REALTIME = 5


@dataclass
class BatchMetrics:
    """Metrics for batch processing performance."""
    total_batches: int = 0
    total_items: int = 0
    successful_batches: int = 0
    failed_batches: int = 0
    
    # Performance metrics
    avg_batch_size: float = 0.0
    avg_processing_time: float = 0.0
    avg_wait_time: float = 0.0
    throughput: float = 0.0  # items per second
    
    # Queue metrics
    queue_size: int = 0
    max_queue_size: int = 0
    avg_queue_depth: float = 0.0
    
    # Resource metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    concurrency: int = 0


@dataclass
class BatchItem:
    """Represents an item in the batch queue."""
    data: Any
    priority: BatchPriority = BatchPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    timeout: float = 0.0
    retry_count: int = 0
    correlation_id: Optional[str] = None
    callback: Optional[Callable] = None


@dataclass
class BatchResult:
    """Result of batch processing."""
    batch_id: str
    items_processed: int
    successful_items: int
    failed_items: int
    processing_time: float
    errors: List[Exception] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChuckNorrisBatchConfig:
    """Configuration for ChuckNorris batch processor."""
    
    # Basic configuration
    max_batch_size: int = 100
    min_batch_size: int = 1
    max_wait_time: float = 1.0  # seconds
    min_wait_time: float = 0.01  # seconds
    
    # Strategy configuration
    strategy: BatchStrategy = BatchStrategy.ADAPTIVE
    priority_enabled: bool = True
    
    # Adaptive configuration
    adaptive_window: int = 100  # Number of batches to analyze
    performance_target: float = 100.0  # Target throughput (items/sec)
    load_threshold: float = 0.8  # System load threshold
    
    # Concurrency configuration
    max_concurrent_batches: int = 5
    worker_pool_size: int = 10
    
    # Resource management
    memory_limit_mb: float = 100.0
    cpu_threshold: float = 0.8
    backpressure_enabled: bool = True
    
    # Error handling
    retry_enabled: bool = True
    max_retries: int = 3
    retry_backoff: float = 1.0
    dead_letter_queue: bool = True
    
    # Monitoring
    metrics_enabled: bool = True
    metrics_interval: int = 60  # seconds


class ChuckNorrisBatchProcessor:
    """
    Advanced batch processor with ChuckNorris-level optimization:
    
    1. Adaptive Batching Strategies
    2. Priority-based Processing
    3. Load-aware Resource Management
    4. Intelligent Queue Management
    5. Performance Monitoring and Optimization
    6. Backpressure Handling
    7. Dead Letter Queue Support
    """
    
    def __init__(self, name: str, processor_func: Callable, config: ChuckNorrisBatchConfig | None = None):
        self.name = name
        self.processor_func = processor_func
        self.config = config or ChuckNorrisBatchConfig()
        
        # Queue management
        self.queue: asyncio.Queue[BatchItem] = asyncio.Queue()
        self.priority_queues: Dict[BatchPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in BatchPriority
        }
        self.dead_letter_queue: asyncio.Queue[BatchItem] = asyncio.Queue()
        
        # State management
        self.running = False
        self.active_batches: Dict[str, asyncio.Task] = {}
        self.batch_counter = 0
        
        # Performance tracking
        self.metrics = BatchMetrics()
        self.performance_history: deque = deque(maxlen=self.config.adaptive_window)
        self.last_adaptation = time.time()
        
        # Adaptive parameters
        self.current_batch_size = self.config.max_batch_size
        self.current_wait_time = self.config.max_wait_time
        self.adaptive_adjustments = {
            'batch_size_history': deque(maxlen=50),
            'processing_time_history': deque(maxlen=50),
            'throughput_history': deque(maxlen=50),
        }
        
        # Worker pool
        self.worker_semaphore = asyncio.Semaphore(self.config.worker_pool_size)
        self.batch_semaphore = asyncio.Semaphore(self.config.max_concurrent_batches)
        
        # Background tasks
        self.processor_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
        self.adaptation_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self.batch_start_callbacks: List[Callable[[str, List[BatchItem]], None]] = []
        self.batch_complete_callbacks: List[Callable[[BatchResult], None]] = []
        self.error_callbacks: List[Callable[[Exception, List[BatchItem]], None]] = []
        
        logger.info(f"ChuckNorris batch processor initialized for {name}")
    
    async def start(self) -> None:
        """Start the batch processor."""
        if self.running:
            return
            
        self.running = True
        
        # Start background tasks
        self.processor_task = asyncio.create_task(self._processing_loop())
        
        if self.config.metrics_enabled:
            self.metrics_task = asyncio.create_task(self._metrics_loop())
        
        if self.config.strategy == BatchStrategy.ADAPTIVE:
            self.adaptation_task = asyncio.create_task(self._adaptation_loop())
        
        logger.info(f"ChuckNorris batch processor started for {self.name}")
    
    async def stop(self) -> None:
        """Stop the batch processor."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel background tasks
        if self.processor_task:
            self.processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.processor_task
        
        if self.metrics_task:
            self.metrics_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.metrics_task
        
        if self.adaptation_task:
            self.adaptation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.adaptation_task
        
        # Wait for active batches to complete
        await asyncio.gather(*self.active_batches.values(), return_exceptions=True)
        
        logger.info(f"ChuckNorris batch processor stopped for {self.name}")
    
    async def submit(self, item: Any, priority: BatchPriority = BatchPriority.NORMAL,
                   timeout: float = 0.0, correlation_id: Optional[str] = None,
                   callback: Optional[Callable] = None) -> str:
        """Submit an item for batch processing."""
        batch_item = BatchItem(
            data=item,
            priority=priority,
            timeout=timeout,
            correlation_id=correlation_id,
            callback=callback
        )
        
        if self.config.priority_enabled:
            await self.priority_queues[priority].put(batch_item)
        else:
            await self.queue.put(batch_item)
        
        # Update queue metrics
        total_queue_size = sum(queue.qsize() for queue in self.priority_queues.values()) + self.queue.qsize()
        self.metrics.queue_size = total_queue_size
        self.metrics.max_queue_size = max(self.metrics.max_queue_size, total_queue_size)
        
        return correlation_id or f"item_{int(time.time() * 1000)}"
    
    async def submit_batch(self, items: List[Any], priority: BatchPriority = BatchPriority.NORMAL) -> None:
        """Submit multiple items for batch processing."""
        for item in items:
            await self.submit(item, priority)
    
    def add_batch_start_callback(self, callback: Callable[[str, List[BatchItem]], None]) -> None:
        """Add callback for batch start events."""
        self.batch_start_callbacks.append(callback)
    
    def add_batch_complete_callback(self, callback: Callable[[BatchResult], None]) -> None:
        """Add callback for batch completion events."""
        self.batch_complete_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[Exception, List[BatchItem]], None]) -> None:
        """Add callback for error events."""
        self.error_callbacks.append(callback)
    
    async def get_metrics(self) -> BatchMetrics:
        """Get current batch processing metrics."""
        # Calculate averages
        if self.metrics.total_batches > 0:
            self.metrics.avg_batch_size = self.metrics.total_items / self.metrics.total_batches
            self.metrics.avg_processing_time = (
                sum(h.processing_time for h in self.performance_history) / max(1, len(self.performance_history))
            )
        
        # Calculate throughput
        if self.metrics.avg_processing_time > 0:
            self.metrics.throughput = self.metrics.avg_batch_size / self.metrics.avg_processing_time
        
        # Calculate average queue depth
        if self.metrics.queue_size > 0:
            self.metrics.avg_queue_depth = self.metrics.max_queue_size / 2.0
        
        return self.metrics
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get detailed queue status."""
        priority_sizes = {
            priority.name.lower(): queue.qsize()
            for priority, queue in self.priority_queues.items()
        }
        
        return {
            'name': self.name,
            'total_queue_size': self.metrics.queue_size,
            'priority_queue_sizes': priority_sizes,
            'dead_letter_queue_size': self.dead_letter_queue.qsize(),
            'active_batches': len(self.active_batches),
            'max_concurrent_batches': self.config.max_concurrent_batches,
            'current_batch_size': self.current_batch_size,
            'current_wait_time': self.current_wait_time,
            'strategy': self.config.strategy.value,
        }
    
    async def _processing_loop(self) -> None:
        """Main processing loop for batch creation and execution."""
        while self.running:
            try:
                # Collect batch based on strategy
                batch_items = await self._collect_batch()
                
                if batch_items:
                    # Process batch
                    await self._process_batch(batch_items)
                else:
                    # No items, wait briefly
                    await asyncio.sleep(self.config.min_wait_time)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(0.1)  # Brief pause before retry
    
    async def _collect_batch(self) -> List[BatchItem]:
        """Collect items for a batch based on strategy."""
        if self.config.strategy == BatchStrategy.PRIORITY_BASED:
            return await self._collect_priority_batch()
        elif self.config.strategy == BatchStrategy.ADAPTIVE:
            return await self._collect_adaptive_batch()
        elif self.config.strategy == BatchStrategy.SIZE_BASED:
            return await self._collect_size_batch()
        elif self.config.strategy == BatchStrategy.TIME_BASED:
            return await self._collect_time_batch()
        elif self.config.strategy == BatchStrategy.LOAD_AWARE:
            return await self._collect_load_aware_batch()
        else:
            return await self._collect_default_batch()
    
    async def _collect_priority_batch(self) -> List[BatchItem]:
        """Collect batch based on priority."""
        batch_items = []
        
        # Process from highest to lowest priority
        for priority in sorted(BatchPriority, key=lambda p: p.value, reverse=True):
            queue = self.priority_queues[priority]
            
            while len(batch_items) < self.current_batch_size and not queue.empty():
                try:
                    item = queue.get_nowait()
                    batch_items.append(item)
                except asyncio.QueueEmpty:
                    break
        
        return batch_items
    
    async def _collect_adaptive_batch(self) -> List[BatchItem]:
        """Collect batch with adaptive sizing."""
        start_time = time.time()
        batch_items = []
        
        # Collect items with time and size limits
        while (len(batch_items) < self.current_batch_size and 
               time.time() - start_time < self.current_wait_time):
            
            # Get next item (priority-aware)
            item = await self._get_next_item()
            if item is None:
                break
                
            batch_items.append(item)
        
        # Adjust adaptive parameters if needed
        if len(batch_items) == 0:
            # No items, increase wait time slightly
            self.current_wait_time = min(
                self.current_wait_time * 1.1,
                self.config.max_wait_time
            )
        
        return batch_items
    
    async def _collect_size_batch(self) -> List[BatchItem]:
        """Collect batch based on size."""
        batch_items = []
        
        while len(batch_items) < self.current_batch_size:
            item = await self._get_next_item()
            if item is None:
                break
            batch_items.append(item)
        
        return batch_items
    
    async def _collect_time_batch(self) -> List[BatchItem]:
        """Collect batch based on time window."""
        start_time = time.time()
        batch_items = []
        
        while time.time() - start_time < self.current_wait_time:
            item = await self._get_next_item()
            if item is None:
                break
            batch_items.append(item)
        
        return batch_items
    
    async def _collect_load_aware_batch(self) -> List[BatchItem]:
        """Collect batch based on system load."""
        # Get current system load (simplified)
        current_load = await self._get_system_load()
        
        # Adjust batch size based on load
        if current_load > self.config.load_threshold:
            # High load, use smaller batches
            max_size = max(1, int(self.current_batch_size * 0.5))
        else:
            # Low load, can use larger batches
            max_size = self.current_batch_size
        
        batch_items = []
        while len(batch_items) < max_size:
            item = await self._get_next_item()
            if item is None:
                break
            batch_items.append(item)
        
        return batch_items
    
    async def _collect_default_batch(self) -> List[BatchItem]:
        """Default batch collection strategy."""
        batch_items = []
        
        # Try to collect up to current batch size
        for _ in range(self.current_batch_size):
            item = await self._get_next_item()
            if item is None:
                break
            batch_items.append(item)
        
        return batch_items
    
    async def _get_next_item(self) -> Optional[BatchItem]:
        """Get next item from appropriate queue."""
        if self.config.priority_enabled:
            # Check priority queues in order
            for priority in sorted(BatchPriority, key=lambda p: p.value, reverse=True):
                queue = self.priority_queues[priority]
                if not queue.empty():
                    try:
                        return queue.get_nowait()
                    except asyncio.QueueEmpty:
                        continue
        
        # Fallback to regular queue
        if not self.queue.empty():
            try:
                return self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        
        return None
    
    async def _process_batch(self, batch_items: List[BatchItem]) -> None:
        """Process a batch of items."""
        if not batch_items:
            return
        
        batch_id = f"batch_{self.name}_{self.batch_counter}"
        self.batch_counter += 1
        
        # Check concurrency limits
        if len(self.active_batches) >= self.config.max_concurrent_batches:
            if self.config.backpressure_enabled:
                logger.warning(f"Backpressure: too many active batches for {self.name}")
                # Put items back in queue
                for item in batch_items:
                    if self.config.priority_enabled:
                        await self.priority_queues[item.priority].put(item)
                    else:
                        await self.queue.put(item)
                return
        
        # Create batch processing task
        async with self.batch_semaphore:
            task = asyncio.create_task(
                self._execute_batch(batch_id, batch_items),
                name=f"batch_{batch_id}"
            )
            self.active_batches[batch_id] = task
        
        # Update metrics
        self.metrics.total_batches += 1
        self.metrics.total_items += len(batch_items)
        self.metrics.concurrency = len(self.active_batches)
    
    async def _execute_batch(self, batch_id: str, batch_items: List[BatchItem]) -> None:
        """Execute a single batch."""
        start_time = time.time()
        
        try:
            # Call batch start callbacks
            for callback in self.batch_start_callbacks:
                try:
                    callback(batch_id, batch_items)
                except Exception as e:
                    logger.error(f"Error in batch start callback: {e}")
            
            # Process the batch
            async with self.worker_semaphore:
                if asyncio.iscoroutinefunction(self.processor_func):
                    result = await self.processor_func([item.data for item in batch_items])
                else:
                    result = self.processor_func([item.data for item in batch_items])
            
            # Create batch result
            processing_time = time.time() - start_time
            batch_result = BatchResult(
                batch_id=batch_id,
                items_processed=len(batch_items),
                successful_items=len(batch_items),
                failed_items=0,
                processing_time=processing_time,
                metadata={'result': result} if result is not None else {}
            )
            
            # Update metrics
            self.metrics.successful_batches += 1
            self.performance_history.append(processing_time)
            
            # Call completion callbacks
            for callback in self.batch_complete_callbacks:
                try:
                    callback(batch_result)
                except Exception as e:
                    logger.error(f"Error in batch complete callback: {e}")
            
            # Call item callbacks
            for item in batch_items:
                if item.callback:
                    try:
                        if asyncio.iscoroutinefunction(item.callback):
                            await item.callback(result)
                        else:
                            item.callback(result)
                    except Exception as e:
                        logger.error(f"Error in item callback: {e}")
        
        except Exception as e:
            # Handle batch failure
            processing_time = time.time() - start_time
            
            # Update metrics
            self.metrics.failed_batches += 1
            
            # Call error callbacks
            for callback in self.error_callbacks:
                try:
                    callback(e, batch_items)
                except Exception as cb_error:
                    logger.error(f"Error in error callback: {cb_error}")
            
            # Handle retries
            if self.config.retry_enabled:
                await self._handle_batch_retry(batch_items, e)
            else:
                # Send to dead letter queue
                if self.config.dead_letter_queue:
                    for item in batch_items:
                        item.retry_count += 1
                        await self.dead_letter_queue.put(item)
        
        finally:
            # Clean up
            if batch_id in self.active_batches:
                del self.active_batches[batch_id]
    
    async def _handle_batch_retry(self, batch_items: List[BatchItem], original_error: Exception) -> None:
        """Handle retry logic for failed batches."""
        for item in batch_items:
            if item.retry_count < self.config.max_retries:
                item.retry_count += 1
                
                # Apply backoff
                await asyncio.sleep(self.config.retry_backoff * (2 ** item.retry_count))
                
                # Resubmit item
                if self.config.priority_enabled:
                    await self.priority_queues[item.priority].put(item)
                else:
                    await self.queue.put(item)
            else:
                # Max retries exceeded, send to dead letter queue
                if self.config.dead_letter_queue:
                    await self.dead_letter_queue.put(item)
    
    async def _get_system_load(self) -> float:
        """Get current system load (simplified implementation)."""
        # This is a simplified implementation
        # In practice, you'd use system metrics like CPU, memory, etc.
        return 0.5  # Placeholder
    
    async def _metrics_loop(self) -> None:
        """Background task to update metrics."""
        while self.running:
            try:
                await asyncio.sleep(self.config.metrics_interval)
                await self.get_metrics()  # Update metrics
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
    
    async def _adaptation_loop(self) -> None:
        """Background task for adaptive optimization."""
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._adapt_parameters()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in adaptation loop: {e}")
    
    async def _adapt_parameters(self) -> None:
        """Adapt batch parameters based on performance."""
        if len(self.performance_history) < 10:
            return  # Not enough data
        
        current_time = time.time()
        if current_time - self.last_adaptation < 60:  # At least 1 minute between adaptations
            return
        
        # Calculate recent performance metrics
        recent_times = list(self.performance_history)[-20:]  # Last 20 batches
        avg_time = statistics.mean(recent_times)
        
        # Calculate current throughput
        current_throughput = self.current_batch_size / max(0.001, avg_time)
        
        # Adapt batch size based on performance target
        if current_throughput < self.config.performance_target * 0.8:
            # Underperforming, try smaller batches
            new_batch_size = max(
                self.config.min_batch_size,
                int(self.current_batch_size * 0.9)
            )
        elif current_throughput > self.config.performance_target * 1.2:
            # Overperforming, try larger batches
            new_batch_size = min(
                self.config.max_batch_size,
                int(self.current_batch_size * 1.1)
            )
        else:
            new_batch_size = self.current_batch_size
        
        # Apply changes if significant
        if abs(new_batch_size - self.current_batch_size) >= 1:
            old_size = self.current_batch_size
            self.current_batch_size = new_batch_size
            self.last_adaptation = current_time
            
            logger.info(
                f"Adapted batch size for {self.name}: "
                f"{old_size} -> {new_batch_size} "
                f"(throughput: {current_throughput:.2f} items/sec, target: {self.config.performance_target:.2f})"
            )

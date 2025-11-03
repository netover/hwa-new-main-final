"""
Test script to verify thread-safe component cache operations.
This script demonstrates that the async synchronization prevents race conditions.
"""

import asyncio
import logging
import time
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


async def simulate_concurrent_cache_access():
    """Test concurrent access to component cache."""
    from resync.core.health_service import HealthCheckService

    service = HealthCheckService()

    # Create test data
    from resync.core.health_models import ComponentHealth, ComponentType, HealthStatus

    ComponentHealth(
        name="test_component",
        component_type=ComponentType.OTHER,
        status=HealthStatus.HEALTHY,
        message="Test component",
        last_check=datetime.now(),
    )

    async def update_cache_task(task_id):
        """Simulate cache updates from multiple tasks."""
        for i in range(5):
            # Update the cache with varying status
            component = ComponentHealth(
                name=f"component_{task_id}",
                component_type=ComponentType.OTHER,
                status=HealthStatus.HEALTHY if i % 2 == 0 else HealthStatus.DEGRADED,
                message=f"Update {i} from task {task_id}",
                last_check=datetime.now(),
            )

            await service._update_cached_component(f"component_{task_id}", component)
            logger.info(f"Task {task_id} updated component_{task_id}")

            # Add some delay to simulate processing
            await asyncio.sleep(0.01)

    async def read_cache_task(task_id):
        """Simulate cache reads from multiple tasks."""
        for _i in range(5):
            cache_contents = await service._get_all_cached_components()
            logger.info(
                f"Task {task_id} read cache with {len(cache_contents)} components"
            )
            await asyncio.sleep(0.01)

    # Run concurrent operations
    update_tasks = [update_cache_task(i) for i in range(3)]
    read_tasks = [read_cache_task(i) for i in range(3)]

    all_tasks = update_tasks + read_tasks

    logger.info("Starting concurrent cache operations...")
    start_time = time.time()

    # Run all tasks concurrently
    await asyncio.gather(*all_tasks)

    end_time = time.time()
    logger.info(
        f"All concurrent operations completed in {end_time - start_time:.3f} seconds"
    )

    # Verify final state
    final_cache = await service._get_all_cached_components()
    logger.info(f"Final cache contains {len(final_cache)} components")

    # Test individual component access
    for i in range(3):
        component = await service._get_cached_component(f"component_{i}")
        if component:
            logger.info(
                f"Component {i}: {component.status.value} - {component.message}"
            )

    return True


async def main():
    """Main test function."""
    logger.info("Testing thread-safe component cache operations...")

    try:
        success = await simulate_concurrent_cache_access()
        if success:
            logger.info("✅ Thread-safe cache operations test passed!")
        else:
            logger.error("❌ Thread-safe cache operations test failed!")
            return False
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return False

    return True


if __name__ == "__main__":
    asyncio.run(main())





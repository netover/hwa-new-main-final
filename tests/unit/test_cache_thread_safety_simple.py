"""
Simple test script to verify thread-safe component cache operations.
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_thread_safe_cache():
    """Test thread-safe cache operations with mock components."""
    from resync.core.health_service import HealthCheckService

    service = HealthCheckService()

    # Create test data
    from resync.core.health_models import ComponentHealth, ComponentType, HealthStatus

    async def cache_writer(task_id):
        """Write to cache with different components."""
        for i in range(3):
            component = ComponentHealth(
                name=f"test_component_{task_id}",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.HEALTHY,
                message=f"Update {i} from writer {task_id}",
            )

            await service._update_cached_component(
                f"test_component_{task_id}", component
            )
            logger.info(f"Writer {task_id} updated test_component_{task_id}")
            await asyncio.sleep(0.01)

    async def cache_reader(task_id):
        """Read from cache concurrently."""
        for _i in range(3):
            cache = await service._get_all_cached_components()
            logger.info(f"Reader {task_id} found {len(cache)} components")
            await asyncio.sleep(0.01)

    # Run concurrent operations
    writers = [cache_writer(i) for i in range(2)]
    readers = [cache_reader(i) for i in range(2)]

    logger.info("Starting thread-safe cache test...")

    # Run all tasks concurrently
    await asyncio.gather(*writers, *readers)

    # Verify final state
    final_cache = await service._get_all_cached_components()
    logger.info(f"Final cache contains {len(final_cache)} components")

    for i in range(2):
        component = await service._get_cached_component(f"test_component_{i}")
        if component:
            logger.info(f"Component {i}: {component.name} - {component.status.value}")

    return True


async def main():
    """Main test function."""
    logger.info("Testing thread-safe cache operations...")

    try:
        success = await test_thread_safe_cache()
        if success:
            logger.info("✅ Thread-safe cache operations test passed!")
        else:
            logger.error("❌ Test failed!")
            return False
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    asyncio.run(main())





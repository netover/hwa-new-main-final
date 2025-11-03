from __future__ import annotations

import asyncio

from resync.core.pools.pool_manager import (
    get_connection_pool_manager,
    reset_connection_pool_manager,
)


async def test_manager() -> None:
    try:
        manager = await get_connection_pool_manager()  # type: ignore[no-untyped-call]
        print(f"Manager initialized: {manager._initialized}")  # type: ignore[attr-defined]
        print(f"Pools: {list(manager.pools.keys())}")  # type: ignore[attr-defined]

        # Reset for next test
        await reset_connection_pool_manager()  # type: ignore[no-untyped-call]
        print("Manager reset successfully")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_manager())





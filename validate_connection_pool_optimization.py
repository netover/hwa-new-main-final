#!/usr/bin/env python3
"""
Validacao das Otimizacoes de Connection Pool para Ambiente de 20 Usuarios

Script to validate that the optimized connection pool configurations behave
as expected for the target environment.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any, Dict, Literal, NotRequired, Optional, TypedDict

from resync.config.settings import settings
from resync.core.connection_pool_manager import ConnectionPoolConfig, DatabaseConnectionPool

logger = logging.getLogger(__name__)

StatusLiteral = Literal['PASS', 'FAIL', 'ERROR', 'SKIP', 'PARTIAL']


class PoolResult(TypedDict):
    status: StatusLiteral
    config: NotRequired[Dict[str, Any]]
    performance: NotRequired[Dict[str, Any]]
    pool_stats: NotRequired[Dict[str, Any]]
    memory_efficient: NotRequired[bool]
    error: NotRequired[str]
    note: NotRequired[str]


class ConnectionPoolValidator:
    """Validate the optimized connection pool configuration."""

    def __init__(self) -> None:
        self.results: Dict[str, PoolResult] = {}

    async def validate_database_pool(self) -> None:
        """Validate the database connection pool."""
        logger.info("Validating database connection pool...")

        pool: Optional[DatabaseConnectionPool] = None
        recommended_max = getattr(settings, 'db_pool_recommended_max_size', 8)
        start_time = time.perf_counter()

        try:
            config = ConnectionPoolConfig(
                pool_name="validation_db",
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                connection_timeout=settings.db_pool_connect_timeout,
                max_lifetime=settings.db_pool_max_lifetime,
                idle_timeout=settings.db_pool_idle_timeout,
                health_check_interval=settings.db_pool_health_check_interval,
            )

            database_url = getattr(settings, 'db_validation_url', "sqlite+aiosqlite:///:memory:")
            pool = DatabaseConnectionPool(config, database_url)
            await pool.initialize()

            async def simulate_user_workload() -> bool:
                async with pool.get_connection():
                    await asyncio.sleep(0.03)
                    return True

            tasks = [simulate_user_workload() for _ in range(15)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            errors = [result for result in results if isinstance(result, Exception)]
            for err in errors:
                logger.error("Database workload task failed: %s", err, exc_info=err)

            total_requests = len(results)
            success_count = total_requests - len(errors)
            error_count = len(errors)
            success_rate = (success_count / total_requests * 100.0) if total_requests else 0.0
            duration_seconds = time.perf_counter() - start_time

            stats = pool.get_stats_copy()
            status: StatusLiteral = 'PASS' if error_count == 0 else 'FAIL'

            self.results['database'] = {
                'status': status,
                'config': {
                    'min_size': config.min_size,
                    'max_size': config.max_size,
                    'expected_users': getattr(settings, 'db_expected_users', 20),
                    'concurrent_peak': 15,
                    'database_url': database_url,
                },
                'performance': {
                    'success_rate': success_rate,
                    'total_requests': total_requests,
                    'successful_requests': success_count,
                    'errors': error_count,
                    'duration_seconds': duration_seconds,
                },
                'pool_stats': stats,
                'memory_efficient': config.max_size <= recommended_max,
            }
        except Exception as exc:
            logger.exception("Database pool validation failed")
            self.results['database'] = {
                'status': 'ERROR',
                'error': str(exc),
            }
        finally:
            if pool is not None:
                with contextlib.suppress(Exception):
                    await pool.close()

    async def validate_redis_pool(self) -> None:
        """Validate the Redis connection pool."""
        logger.info("Validating Redis connection pool...")

        try:
            import redis.asyncio as redis
        except ImportError as exc:
            logger.warning("Redis validation skipped; redis.asyncio not available: %s", exc)
            self.results['redis'] = {
                'status': 'SKIP',
                'note': 'redis.asyncio client is not installed',
            }
            return

        host = getattr(settings, 'redis_host', 'localhost')
        port = getattr(settings, 'redis_port', 6379)
        password = getattr(settings, 'redis_password', None)
        max_connections = getattr(settings, 'redis_pool_max_size', 0)
        recommended_max = getattr(settings, 'redis_pool_recommended_max_size', 6)
        socket_timeout = getattr(settings, 'redis_socket_timeout', 5)
        connect_timeout = getattr(settings, 'redis_socket_connect_timeout', 5)

        client = redis.Redis(
            host=host,
            port=port,
            password=password,
            db=getattr(settings, 'redis_db', 0),
            decode_responses=True,
            socket_timeout=socket_timeout,
            socket_connect_timeout=connect_timeout,
        )

        try:
            ping_result = await client.ping()
            status: StatusLiteral = 'PASS' if ping_result else 'FAIL'

            self.results['redis'] = {
                'status': status,
                'config': {
                    'host': host,
                    'port': port,
                    'max_connections': max_connections,
                },
                'performance': {
                    'connectivity_test': 'successful' if ping_result else 'failed',
                    'ping_response': ping_result,
                },
                'memory_efficient': recommended_max <= 0 or max_connections <= recommended_max,
            }
        except Exception as exc:
            logger.exception("Redis pool validation failed")
            self.results['redis'] = {
                'status': 'ERROR',
                'error': str(exc),
                'config': {
                    'host': host,
                    'port': port,
                    'max_connections': max_connections,
                },
            }
        finally:
            with contextlib.suppress(Exception):
                await client.aclose()

    async def validate_http_pool(self) -> None:
        """Validate the HTTP connection pool configuration."""
        logger.info("Validating HTTP connection pool configuration...")

        max_size = getattr(settings, 'http_pool_max_size', None)
        idle_timeout = getattr(settings, 'http_pool_idle_timeout', None)
        recommended_max = getattr(settings, 'http_pool_recommended_max_size', 12)

        if max_size is None or idle_timeout is None:
            message = 'HTTP pool configuration missing required attributes'
            logger.warning(message)
            self.results['http'] = {
                'status': 'PARTIAL',
                'config': {
                    'max_size': max_size,
                    'idle_timeout': idle_timeout,
                },
                'performance': {
                    'configuration_check': 'incomplete',
                },
                'note': message,
            }
            return

        max_size_ok = max_size <= recommended_max
        self.results['http'] = {
            'status': 'PASS' if max_size_ok else 'FAIL',
            'config': {
                'max_size': max_size,
                'idle_timeout': idle_timeout,
                'recommended_max_size': recommended_max,
            },
            'performance': {
                'configuration_check': 'completed',
                'pool_limits_verified': max_size_ok,
            },
            'memory_efficient': max_size_ok,
        }

        endpoint = getattr(settings, 'http_pool_validation_endpoint', None)
        if not endpoint:
            return

        try:
            import httpx
        except ImportError:
            logger.info("httpx not installed; skipping HTTP request validation step")
            self.results['http']['note'] = 'httpx not installed; configuration validation only'
            return

        request_count = getattr(settings, 'http_validation_request_count', 3)

        async def perform_request(client: httpx.AsyncClient) -> float:
            start = time.perf_counter()
            response = await client.get(endpoint)
            response.raise_for_status()
            return time.perf_counter() - start

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                durations = await asyncio.gather(
                    *(perform_request(client) for _ in range(request_count)),
                    return_exceptions=True,
                )

            errors = [d for d in durations if isinstance(d, Exception)]
            for err in errors:
                logger.error("HTTP validation request failed: %s", err, exc_info=err)

            successful = [d for d in durations if not isinstance(d, Exception)]
            performance = self.results['http']['performance']
            performance.update(
                {
                    'requests_sent': request_count,
                    'successful_requests': len(successful),
                    'failed_requests': len(errors),
                }
            )
            if successful:
                performance['avg_latency_seconds'] = sum(successful) / len(successful)

            if errors:
                self.results['http']['status'] = 'PARTIAL'
                self.results['http']['note'] = 'Some HTTP validation requests failed'
        except Exception as exc:
            logger.exception("HTTP pool validation requests failed")
            self.results['http']['status'] = 'PARTIAL'
            self.results['http']['note'] = str(exc)

    async def run_validation(self) -> None:
        """Run every validation and print the final report."""
        logger.info("Starting connection pool optimization validation...")

        await asyncio.gather(
            self.validate_database_pool(),
            self.validate_redis_pool(),
            self.validate_http_pool(),
        )

        self.print_report()

    def print_report(self) -> None:
        """Print a human-readable validation report."""
        print("\n" + "=" * 80)
        print("Connection Pool Optimization Validation Report")
        print("=" * 80)
        print("Environment: 20 users, Xeon 4 cores, 16GB RAM")
        print()

        for pool_name, data in self.results.items():
            print(f"{pool_name.upper()} POOL:")
            print(f"   Status: {data['status']}")
            if 'error' in data:
                print(f"   Error: {data['error']}")
            if 'note' in data:
                print(f"   Note: {data['note']}")
            if 'config' in data:
                config_details = ', '.join(f"{key}={value}" for key, value in data['config'].items())
                print(f"   Config: {config_details}")
            if 'performance' in data:
                perf_details = ', '.join(f"{key}={value}" for key, value in data['performance'].items())
                print(f"   Performance: {perf_details}")
            if 'memory_efficient' in data:
                memory_state = 'Optimized' if data['memory_efficient'] else 'Not optimized'
                print(f"   Memory: {memory_state}")
            if 'pool_stats' in data:
                print(f"   Pool stats: {data['pool_stats']}")
            print()

        all_passed = all(result['status'] == 'PASS' for result in self.results.values())
        if all_passed:
            print("OVERALL RESULT: PASS - All pool optimizations validated")
        else:
            print("OVERALL RESULT: CHECK RESULTS - Issues detected; see details above")

        print("=" * 80)


async def main() -> None:
    """Execute the validation workflow."""
    validator = ConnectionPoolValidator()
    await validator.run_validation()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    asyncio.run(main())



"""TWS (Tivoli Workload Scheduler) service integration.

This module provides comprehensive integration with IBM Tivoli Workload Scheduler,
including job monitoring, workstation status, critical path analysis, and
real-time data retrieval through optimized HTTP client connections.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from dateutil import parser
from resync.core.cache_hierarchy import get_cache_hierarchy
# Import circuit breaker and retry utilities from their actual locations.
from resync.utils.exceptions import CircuitBreakerError
from resync.core.health.circuit_breaker_manager import CircuitBreakerManager
from resync.utils.retry_utils import retry_with_backoff_async
from resync.settings.settings import settings  # New import
from resync.core.connection_pool_manager import get_connection_pool_manager
from resync.utils.exceptions import TWSConnectionError

from resync.models.tws import (
    CriticalJob,
    DependencyTree,
    Event,
    JobDetails,
    JobExecution,
    JobStatus,
    PerformanceData,
    PlanDetails,
    ResourceStatus,
    SystemStatus,
    WorkstationStatus,
)
from resync.services.http_client_factory import (
    create_async_http_client,
    create_tws_http_client,
)

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# HTTPX AsyncClient singleton
_httpx_client: httpx.AsyncClient | None = None

def get_httpx_client() -> httpx.AsyncClient:
    """Get HTTPX AsyncClient singleton with lazy initialization."""
    global _httpx_client
    if _httpx_client is None:
        # Use sensible defaults for limits and enable HTTP/2 for better performance
        _httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            http2=True,
        )
    return _httpx_client

# Se seu serviço precisar fechar o client no shutdown:
async def shutdown_httpx():
    """Shutdown HTTPX AsyncClient singleton."""
    global _httpx_client
    if _httpx_client is not None:
        await _httpx_client.aclose()
        _httpx_client = None

# Regex para validar job_ids, permitindo alfanuméricos, underscores e hifens.

# NOTE: Circuit Breaker Evolution
# This service now supports both traditional circuit breakers (via decorators)
# and adaptive circuit breakers with latency monitoring (via adaptive_tws_api_breaker).
# For new implementations, consider using adaptive_tws_api_breaker.call_with_latency()
# for better observability and automatic threshold adaptation.
SAFE_JOB_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# --- Constants ---
# Default timeout for HTTP requests to prevent indefinite hangs
DEFAULT_TIMEOUT = 30.0


# --- Caching Mechanism ---
# CacheEntry and SimpleTTLCache moved to resync.core.async_cache
# Now using AsyncTTLCache for truly async operations


# --- TWS Client ---
class OptimizedTWSClient:
    """
    An optimized client for interacting with the HCL Workload Automation (TWS) API.
    Features include asynchronous requests, connection pooling, and caching.
    """

    def __init__(
        self,
        hostname: str,
        port: int,
        username: str,
        password: str,
        engine_name: str = "tws-engine",
        engine_owner: str = "tws-owner",
        use_connection_pool: bool = True,
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.engine_name = engine_name
        self.engine_owner = engine_owner
        self.timeout = DEFAULT_TIMEOUT
        self.base_url = f"http://{hostname}:{port}/twsd"
        self.auth = (username, password)
        self.use_connection_pool = use_connection_pool
        self._pool_manager: Any = None

        if use_connection_pool:
            # Use connection pool manager for enhanced connection management
            logger.info("Using connection pool manager for TWS HTTP client")
        else:
            # Legacy direct httpx client for backward compatibility
            self.client = create_tws_http_client(
                base_url=self.base_url,
                auth=self.auth,
                # verify herdado da factory (False por padrão via settings)
            )

        # Caching layer to reduce redundant API calls - using a direct Redis cache
        self.cache = get_cache_hierarchy()
        logger.info(
            "OptimizedTWSClient initialized for base URL: %s", self.base_url
        )

        # Initialize centralized resilience manager
        self.cbm = CircuitBreakerManager()
        # Register circuit breakers for all TWS endpoints
        self.cbm.register("tws_http_client", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_ping", fail_max=5, reset_timeout=60)
        self.cbm.register("tws_workstations", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_jobs_status", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_system_status", fail_max=2, reset_timeout=60)
        self.cbm.register("tws_job_details", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_job_history", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_job_log", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_plan_details", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_job_dependencies", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_resource_usage", fail_max=3, reset_timeout=30)
        self.cbm.register("tws_event_log", fail_max=3, reset_timeout=30)
        self.cbm.register(
            "tws_performance_metrics", fail_max=2, reset_timeout=60
        )

    async def _get_http_client(self) -> Any:
        """Get HTTP client from connection pool or use direct client."""
        if self.use_connection_pool:
            if self._pool_manager is None:
                self._pool_manager = await get_connection_pool_manager()
            pool = self._pool_manager.get_pool("tws_http")
            if pool:
                return await pool.get_connection()
            logger.warning(
                "TWS HTTP connection pool not available, falling back to direct client"
            )
            # Fallback to direct client if pool not available
            if not hasattr(self, "client"):
                self.client = create_async_http_client(
                    base_url=self.base_url,
                    auth=self.auth,
                    verify=True,
                )
            return self.client
        return self.client if hasattr(self, "client") else None

    async def _make_request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Makes an HTTP request with retry logic using connection pool."""

        # Enforce read-only mode: if the settings indicate mock mode or
        # read-only behaviour, disallow any HTTP methods other than GET
        # and HEAD.  This protects against accidental writes (POST/PUT/
        # DELETE) to the TWS API in environments where modifications
        # should not occur.  Use an environment variable or the
        # ``tws_mock_mode`` flag in settings to control this behaviour.
        try:
            from resync.settings.settings import settings as _settings  # type: ignore
            read_only = getattr(_settings, "tws_mock_mode", False)
        except Exception:
            read_only = False
        import os as _os
        if _os.getenv("READ_ONLY_MODE", "false").lower() in {"1", "true", "yes"}:
            read_only = True
        if read_only and method.upper() not in {"GET", "HEAD"}:
            raise TWSConnectionError(
                f"HTTP method {method.upper()} not allowed in read-only mode"
            )

        logger.debug("Making request: %s %s", method.upper(), url)

        # Get client from connection pool or use direct client
        client = await self._get_http_client()
        if client is None:
            # Use singleton client as fallback
            client = get_httpx_client()

        async def _once():
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        async def _call():
            return await self.cbm.call("tws_http_client", _once)

        return await retry_with_backoff_async(
            _call,
            retries=3,
            base_delay=1.0,
            cap=10.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )

    @asynccontextmanager
    async def _api_request(
        self, method: str, url: str, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any] | list[Any], None]:
        """A context manager for making robust API requests."""
        try:
            response = await self._make_request(method, url, **kwargs)
            data = response.json()
            if isinstance(data, (dict, list)):
                yield data
            else:
                yield {}
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error occurred: %s - %s",
                e.response.status_code,
                e.response.text,
            )
            raise TWSConnectionError(
                f"HTTP error: {e.response.status_code}", original_exception=e
            )
        except httpx.RequestError as e:
            logger.error("Network error during API request: %s", str(e))
            raise TWSConnectionError(
                f"Network error during API request: {e.request.url}",
                original_exception=e,
            )
        except Exception as e:
            logger.error(
                "An unexpected error occurred during API request: %s", e
            )
            # Wrap unexpected errors for consistent error handling
            raise TWSConnectionError(
                "An unexpected error occurred", original_exception=e
            )

    async def ping(self) -> None:
        """
        Performs a lightweight connectivity test to the TWS server.

        This method attempts to establish a connection and receive a response
        without processing the full API response, making it suitable for health checks.

        Raises:
            TWSConnectionError: If the server is unreachable, unresponsive, or times out.
        """
        try:
            # Get client from connection pool or use direct client
            client = await self._get_http_client()
            if client is None:
                # Use singleton client as fallback
                client = get_httpx_client()

            # Use a simple HEAD request to the base URL to test connectivity
            async def _once():
                response = await client.head("", timeout=5.0)
                response.raise_for_status()
                return response

            async def _call():
                return await self.cbm.call("tws_ping", _once)

            await retry_with_backoff_async(
                _call,
                retries=2,
                base_delay=0.5,
                cap=3.0,
                jitter=True,
                retry_on=(
                    httpx.RequestError,
                    httpx.TimeoutException,
                    CircuitBreakerError,
                ),
            )
        except httpx.TimeoutException as e:
            logger.warning("TWS server ping timed out")
            raise TWSConnectionError(
                "TWS server ping timed out", original_exception=e
            )
        except httpx.RequestError as e:
            logger.error(f"TWS server ping failed: {e}")
            raise TWSConnectionError(
                "TWS server unreachable", original_exception=e
            )
        except Exception as e:
            logger.error(f"Unexpected error during TWS ping: {e}")
            raise TWSConnectionError(
                "TWS ping failed unexpectedly", original_exception=e
            )

    async def check_connection(self) -> bool:
        """Verifies the connection to the TWS server is active."""
        try:

            async def _once():
                async with self._api_request("GET", "/plan/current") as data:
                    return "planId" in data

            async def _call():
                return await self.cbm.call("tws_check_connection", _once)

            return await retry_with_backoff_async(
                _call,
                retries=2,
                base_delay=1.0,
                cap=5.0,
                jitter=True,
                retry_on=(
                    httpx.RequestError,
                    httpx.TimeoutException,
                    CircuitBreakerError,
                ),
            )
        except TWSConnectionError:
            return False

    async def get_workstations_status(self) -> list[WorkstationStatus]:
        """Retrieves the status of all workstations, utilizing the cache."""
        cache_key = "workstations_status"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return cached_data if isinstance(cached_data, list) else []

        url = f"/model/workstation?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                return (
                    [WorkstationStatus(**ws) for ws in data]
                    if isinstance(data, list)
                    else []
                )

        async def _call():
            return await self.cbm.call("tws_workstations", _once)

        workstations = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(
            cache_key, workstations
        )  # ttl not supported in current cache implementation
        return workstations

    async def get_jobs_status(self) -> list[JobStatus]:
        """Retrieves the status of all jobs, utilizing the cache."""
        cache_key = "jobs_status"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return cached_data if isinstance(cached_data, list) else []

        url = f"/model/jobdefinition?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                return (
                    [JobStatus(**job) for job in data]
                    if isinstance(data, list)
                    else []
                )

        async def _call():
            return await self.cbm.call("tws_jobs_status", _once)

        jobs = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(
            cache_key, jobs
        )  # ttl not supported in current cache implementation
        return jobs

    async def get_critical_path_status(self) -> list[CriticalJob]:
        """Retrieves the status of jobs in the critical path, utilizing the cache."""
        cache_key = "critical_path_status"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return cached_data if isinstance(cached_data, list) else []

        url = "/plan/current/criticalpath"

        async def _once():
            async with self._api_request("GET", url) as data:
                jobs_data = (
                    data.get("jobs", []) if isinstance(data, dict) else []
                )
                return (
                    [CriticalJob(**job) for job in jobs_data]
                    if isinstance(jobs_data, list)
                    else []
                )

        async def _call():
            return await self.cbm.call("tws_critical_path", _once)

        critical_jobs = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(
            cache_key, critical_jobs
        )  # ttl not supported in current cache implementation
        return critical_jobs

    async def get_system_status(self) -> SystemStatus:
        """Retrieves a comprehensive system status with parallel execution."""
        # Execute all three calls concurrently
        workstations_task = asyncio.create_task(self.get_workstations_status())
        jobs_task = asyncio.create_task(self.get_jobs_status())
        critical_jobs_task = asyncio.create_task(
            self.get_critical_path_status()
        )

        workstations: list[WorkstationStatus] | Exception
        jobs: list[JobStatus] | Exception
        critical_jobs: list[CriticalJob] | Exception
        workstations, jobs, critical_jobs = await asyncio.gather(
            workstations_task,
            jobs_task,
            critical_jobs_task,
            return_exceptions=True,
        )

        # Handle potential exceptions
        if isinstance(workstations, Exception):
            logger.error(f"Failed to get workstations status: {workstations}")
            workstations = []

        if isinstance(jobs, Exception):
            logger.error(f"Failed to get jobs status: {jobs}")
            jobs = []

        if isinstance(critical_jobs, Exception):
            logger.error(
                f"Failed to get critical path status: {critical_jobs}"
            )
            critical_jobs = []

        return SystemStatus(
            workstations=workstations, jobs=jobs, critical_jobs=critical_jobs
        )

    async def get_job_details(self, job_id: str) -> JobDetails:
        """Retrieves detailed information about a specific job."""
        cache_key = f"job_details:{job_id}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return (
                cached_data
                if isinstance(cached_data, dict)
                else JobDetails(**cached_data)
            )

        # Validate job_id format
        if not SAFE_JOB_ID_PATTERN.match(job_id):
            logger.warning(f"Invalid job_id format: {job_id}")
            raise ValueError(f"Invalid job_id format: {job_id}")

        url = f"/model/jobdefinition/{job_id}?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                if isinstance(data, dict):
                    # Get job history for execution details
                    try:
                        history = await self.get_job_history(job_id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to get job history for {job_id}: {e}"
                        )
                        history = []

                    # Get dependencies
                    try:
                        dependencies = await self.get_job_dependencies(job_id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to get dependencies for {job_id}: {e}"
                        )
                        dependencies = []

                    return JobDetails(
                        job_id=job_id,
                        name=data.get("name", job_id),
                        workstation=data.get("workstation", ""),
                        status=data.get("status", "UNKNOWN"),
                        job_stream=data.get("job_stream", ""),
                        full_definition=data,
                        dependencies=dependencies.dependencies,
                        resource_requirements=data.get(
                            "resource_requirements", {}
                        ),
                        execution_history=history[
                            :10
                        ],  # Limit to last 10 executions
                    )
                raise ValueError(f"Unexpected data format for job {job_id}")

        async def _call():
            return await self.cbm.call("tws_job_details", _once)

        job_details = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(cache_key, job_details.dict())
        return job_details

    async def get_job_history(self, job_name: str) -> list[JobExecution]:
        """Retrieves the execution history for a specific job."""
        cache_key = f"job_history:{job_name}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return (
                [JobExecution(**execution) for execution in cached_data]
                if isinstance(cached_data, list)
                else []
            )

        # Validate job_name format
        if not SAFE_JOB_ID_PATTERN.match(job_name):
            logger.warning(f"Invalid job_name format: {job_name}")
            raise ValueError(f"Invalid job_name format: {job_name}")

        url = f"/model/jobdefinition/{job_name}/history?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                executions = []
                if isinstance(data, list):
                    for execution_data in data:
                        if isinstance(execution_data, dict):
                            try:
                                # Convert timestamps to datetime objects
                                start_time = execution_data.get("start_time")
                                end_time = execution_data.get("end_time")

                                if start_time and isinstance(start_time, str):
                                    # Try to parse ISO format
                                    try:
                                        start_time = parser.parse(start_time)
                                    except Exception:
                                        start_time = None

                                if end_time and isinstance(end_time, str):
                                    try:
                                        end_time = parser.parse(end_time)
                                    except Exception:
                                        end_time = None

                                execution = JobExecution(
                                    job_id=execution_data.get(
                                        "job_id", job_name
                                    ),
                                    status=execution_data.get(
                                        "status", "UNKNOWN"
                                    ),
                                    start_time=start_time or None,
                                    end_time=end_time,
                                    duration=execution_data.get("duration"),
                                    error_message=execution_data.get(
                                        "error_message"
                                    ),
                                )
                                executions.append(execution)
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse execution data: {e}"
                                )

                return executions

        async def _call():
            return await self.cbm.call("tws_job_history", _once)

        executions = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(cache_key, [e.dict() for e in executions])
        return executions

    async def get_job_log(self, job_id: str) -> str:
        """Retrieves the log content for a specific job execution."""
        cache_key = f"job_log:{job_id}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return str(cached_data)

        # Validate job_id format
        if not SAFE_JOB_ID_PATTERN.match(job_id):
            logger.warning(f"Invalid job_id format: {job_id}")
            raise ValueError(f"Invalid job_id format: {job_id}")

        url = f"/model/jobdefinition/{job_id}/log?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                log_content = ""
                if isinstance(data, dict):
                    log_content = data.get("log_content", "")
                elif isinstance(data, str):
                    log_content = data
                return log_content

        async def _call():
            return await self.cbm.call("tws_job_log", _once)

        log_content = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(cache_key, log_content)
        return log_content

    async def get_plan_details(self) -> PlanDetails:
        """Retrieves details about the current TWS plan."""
        cache_key = "plan_details"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return (
                PlanDetails(**cached_data)
                if isinstance(cached_data, dict)
                else PlanDetails(**cached_data)
            )

        url = "/plan/current"

        async def _once():
            async with self._api_request("GET", url) as data:
                if isinstance(data, dict):
                    # Parse timestamps
                    creation_date = data.get("creation_date")
                    estimated_completion = data.get("estimated_completion")

                    if creation_date and isinstance(creation_date, str):
                        try:
                            creation_date = parser.parse(creation_date)
                        except Exception:
                            creation_date = None

                    if estimated_completion and isinstance(
                        estimated_completion, str
                    ):
                        try:
                            estimated_completion = parser.parse(
                                estimated_completion
                            )
                        except Exception:
                            estimated_completion = None

                    return PlanDetails(
                        plan_id=data.get("plan_id", "current"),
                        creation_date=creation_date or None,
                        jobs_count=data.get("jobs_count", 0),
                        estimated_completion=estimated_completion,
                        status=data.get("status", "UNKNOWN"),
                    )
                raise ValueError("Unexpected data format for plan details")

        async def _call():
            return await self.cbm.call("tws_plan_details", _once)

        plan_details = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(cache_key, plan_details.dict())
        return plan_details

    async def get_job_dependencies(self, job_id: str) -> DependencyTree:
        """Retrieves the dependency tree for a specific job."""
        cache_key = f"job_dependencies:{job_id}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return (
                DependencyTree(**cached_data)
                if isinstance(cached_data, dict)
                else DependencyTree(**cached_data)
            )

        # Validate job_id format
        if not SAFE_JOB_ID_PATTERN.match(job_id):
            logger.warning(f"Invalid job_id format: {job_id}")
            raise ValueError(f"Invalid job_id format: {job_id}")

        url = f"/model/jobdefinition/{job_id}/dependencies?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                if isinstance(data, dict):
                    return DependencyTree(
                        job_id=job_id,
                        dependencies=data.get("dependencies", []),
                        dependents=data.get("dependents", []),
                        dependency_graph=data.get("dependency_graph", {}),
                    )
                raise ValueError(
                    f"Unexpected data format for job dependencies {job_id}"
                )

        async def _call():
            return await self.cbm.call("tws_job_dependencies", _once)

        dependency_tree = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(cache_key, dependency_tree.dict())
        return dependency_tree

    async def get_resource_usage(self) -> list[ResourceStatus]:
        """Retrieves resource usage information."""
        cache_key = "resource_usage"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return (
                [ResourceStatus(**resource) for resource in cached_data]
                if isinstance(cached_data, list)
                else []
            )

        url = f"/model/resource?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                resources = []
                if isinstance(data, list):
                    for resource_data in data:
                        if isinstance(resource_data, dict):
                            try:
                                resource = ResourceStatus(
                                    resource_name=resource_data.get(
                                        "resource_name", ""
                                    ),
                                    resource_type=resource_data.get(
                                        "resource_type", ""
                                    ),
                                    total_capacity=resource_data.get(
                                        "total_capacity"
                                    ),
                                    used_capacity=resource_data.get(
                                        "used_capacity"
                                    ),
                                    available_capacity=resource_data.get(
                                        "available_capacity"
                                    ),
                                    utilization_percentage=resource_data.get(
                                        "utilization_percentage"
                                    ),
                                )
                                resources.append(resource)
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse resource data: {e}"
                                )

                return resources

        async def _call():
            return await self.cbm.call("tws_resource_usage", _once)

        resources = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(cache_key, [r.dict() for r in resources])
        return resources

    async def get_event_log(self, last_hours: int = 24) -> list[Event]:
        """Retrieves TWS event log entries."""
        cache_key = f"event_log:{last_hours}h"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return (
                [Event(**event) for event in cached_data]
                if isinstance(cached_data, list)
                else []
            )

        url = f"/events?since={last_hours}h&engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                events = []
                if isinstance(data, list):
                    for event_data in data:
                        if isinstance(event_data, dict):
                            try:
                                # Parse timestamp
                                timestamp = event_data.get("timestamp")
                                if timestamp and isinstance(timestamp, str):
                                    try:
                                        timestamp = parser.parse(timestamp)
                                    except Exception:
                                        timestamp = None

                                event = Event(
                                    event_id=event_data.get("event_id", ""),
                                    timestamp=timestamp or None,
                                    event_type=event_data.get(
                                        "event_type", ""
                                    ),
                                    severity=event_data.get(
                                        "severity", "INFO"
                                    ),
                                    source=event_data.get("source", ""),
                                    message=event_data.get("message", ""),
                                    job_id=event_data.get("job_id"),
                                    workstation=event_data.get("workstation"),
                                )
                                events.append(event)
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse event data: {e}"
                                )

                return events

        async def _call():
            return await self.cbm.call("tws_event_log", _once)

        events = await retry_with_backoff_async(
            _call,
            retries=2,
            base_delay=1.0,
            cap=5.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(cache_key, [e.dict() for e in events])
        return events

    async def get_performance_metrics(self) -> PerformanceData:
        """Retrieves TWS performance metrics."""
        cache_key = "performance_metrics"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return (
                PerformanceData(**cached_data)
                if isinstance(cached_data, dict)
                else PerformanceData(**cached_data)
            )

        url = f"/metrics?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        async def _once():
            async with self._api_request("GET", url) as data:
                if isinstance(data, dict):
                    # Parse timestamp
                    timestamp = data.get("timestamp")
                    if timestamp and isinstance(timestamp, str):
                        try:
                            timestamp = parser.parse(timestamp)
                        except Exception:
                            timestamp = None

                    return PerformanceData(
                        timestamp=timestamp or None,
                        api_response_times=data.get("api_response_times", {}),
                        cache_hit_rate=data.get("cache_hit_rate", 0.0),
                        memory_usage_mb=data.get("memory_usage_mb", 0.0),
                        cpu_usage_percentage=data.get(
                            "cpu_usage_percentage", 0.0
                        ),
                        active_connections=data.get("active_connections", 0),
                        jobs_per_minute=data.get("jobs_per_minute", 0.0),
                    )
                raise ValueError(
                    "Unexpected data format for performance metrics"
                )

        async def _call():
            return await self.cbm.call("tws_performance_metrics", _once)

        performance_data = await retry_with_backoff_async(
            _call,
            retries=3,
            base_delay=1.0,
            cap=8.0,
            jitter=True,
            retry_on=(
                httpx.RequestError,
                httpx.TimeoutException,
                CircuitBreakerError,
            ),
        )
        await self.cache.set(cache_key, performance_data.dict())
        return performance_data

    async def get_job_status_batch(
        self, job_ids: list[str]
    ) -> dict[str, JobStatus]:
        """
        Batch multiple job status queries using parallel execution.

        Args:
            job_ids: List of job IDs to query

        Returns:
            Dictionary mapping job_id to JobStatus
        """
        results: dict[str, JobStatus] = {}

        # Separate cached and uncached jobs
        uncached_jobs = []
        for job_id in job_ids:
            # Validação de segurança para prevenir Path Traversal ou injeção de URL
            if not SAFE_JOB_ID_PATTERN.match(job_id):
                logger.warning(f"Skipping invalid job_id format: {job_id}")
                continue

            cache_key = f"job_status:{job_id}"
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                results[job_id] = cached_data
            else:
                uncached_jobs.append(job_id)

        # Process uncached jobs in parallel with concurrency control
        if uncached_jobs:
            # Limit concurrent requests to prevent overwhelming server
            semaphore = asyncio.Semaphore(
                getattr(settings, "TWS_MAX_CONCURRENT_REQUESTS", 10)
            )

            async def fetch_single_job(
                job_id: str,
            ) -> tuple[str, JobStatus | None]:
                async with semaphore:
                    try:
                        url = f"/model/jobdefinition/{job_id}?engineName={self.engine_name}&engineOwner={self.engine_owner}"
                        async with self._api_request("GET", url) as data:
                            if isinstance(data, dict):
                                job_status = JobStatus(**data)
                                # Cache result
                                await self.cache.set(
                                    f"job_status:{job_id}", job_status
                                )  # ttl not supported in current cache implementation
                                return job_id, job_status
                            logger.warning(
                                f"Unexpected data format for job {job_id}: expected dict, got {type(data)}"
                            )
                            return job_id, None
                    except Exception as e:
                        logger.warning(
                            f"Failed to get status for job {job_id}: {e}"
                        )
                        return job_id, None

            # Execute all requests concurrently
            tasks = [fetch_single_job(job_id) for job_id in uncached_jobs]
            parallel_results = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            # Process results
            for result in parallel_results:
                if isinstance(result, Exception):
                    logger.error(
                        f"Error in parallel job status fetch: {result}"
                    )
                elif isinstance(result, tuple) and len(result) == 2:
                    job_id, job_status = result
                    if job_status is not None:
                        results[job_id] = job_status

        return results

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """
        Retrieves status of a specific job.

        Args:
            job_id: The ID of job to check

        Returns:
            Dictionary containing job status information
        """
        # Validate job_id format
        if not SAFE_JOB_ID_PATTERN.match(job_id):
            logger.warning(f"Invalid job_id format: {job_id}")
            raise ValueError(f"Invalid job_id format: {job_id}")

        cache_key = f"job_status:{job_id}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return cached_data if isinstance(cached_data, dict) else {}

        url = f"/model/jobdefinition/{job_id}?engineName={self.engine_name}&engineOwner={self.engine_owner}"

        try:
            async with asyncio.timeout(5.0):  # 5s timeout

                async def _once():
                    async with self._api_request("GET", url) as data:
                        return data if isinstance(data, dict) else {}

                async def _call():
                    return await self.cbm.call("tws_job_status", _once)

                job_status = await retry_with_backoff_async(
                    _call,
                    retries=2,
                    base_delay=1.0,
                    cap=5.0,
                    jitter=True,
                    retry_on=(
                        httpx.RequestError,
                        httpx.TimeoutException,
                        CircuitBreakerError,
                    ),
                )
                await self.cache.set(cache_key, job_status)
                return job_status

        except asyncio.TimeoutError:
            logger.error(f"Timeout getting job status for {job_id}")
            raise TWSConnectionError(
                f"Timeout getting job status for {job_id}"
            )
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            raise TWSConnectionError(
                f"Error getting job status for {job_id}: {e}"
            )

    async def validate_connection(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        """
        Validates TWS connection parameters without changing current connection.

        Args:
            host: TWS server hostname (optional, uses current if not provided)
            port: TWS server port (optional, uses current if not provided)
            user: TWS username (optional, uses current if not provided)
            password: TWS password (optional, uses current if not provided)

        Returns:
            Dictionary with validation result
        """
        # Use current values if not provided
        test_host = host or self.hostname
        test_port = port or self.port
        test_user = user or self.username
        test_password = password or self.password

        try:
            # Create a temporary client with test parameters
            test_base_url = f"http://{test_host}:{test_port}/twsd"
            test_client = httpx.AsyncClient(
                base_url=test_base_url,
                auth=(test_user, test_password),
                verify=settings.TWS_VERIFY,
                timeout=httpx.Timeout(
                    connect=getattr(settings, "TWS_CONNECT_TIMEOUT", 10),
                    read=getattr(settings, "TWS_READ_TIMEOUT", 30),
                    write=getattr(settings, "TWS_WRITE_TIMEOUT", 30),
                    pool=getattr(settings, "TWS_POOL_TIMEOUT", 30),
                ),
            )

            # Try to establish a connection
            response = await test_client.head("", timeout=5.0)
            response.raise_for_status()

            await test_client.aclose()

            logger.info(
                f"TWS connection validation successful for {test_host}:{test_port}"
            )
            return {
                "valid": True,
                "message": f"Successfully validated connection to {test_host}:{test_port}",
                "host": test_host,
                "port": test_port,
            }

        except httpx.TimeoutException as e:
            logger.warning(
                f"TWS connection validation timed out for {test_host}:{test_port}"
            )
            return {
                "valid": False,
                "message": f"TWS connection validation timed out: {e}",
                "host": test_host,
                "port": test_port,
            }
        except httpx.RequestError as e:
            logger.error(
                f"TWS connection validation failed for {test_host}:{test_port} - {e}"
            )
            await test_client.aclose()  # Make sure client is closed in case of error
            return {
                "valid": False,
                "message": f"TWS connection validation failed: {e}",
                "host": test_host,
                "port": test_port,
            }
        except Exception as e:
            logger.error(
                f"Unexpected error during TWS connection validation: {e}"
            )
            if "test_client" in locals():
                try:
                    await test_client.aclose()
                except Exception as e:
                    # Log cleanup errors but don't fail validation
                    logger.debug(f"TWS test client cleanup error: {e}")
            return {
                "valid": False,
                "message": f"Unexpected error during TWS connection validation: {e}",
                "host": test_host,
                "port": test_port,
            }

    async def invalidate_system_cache(self) -> None:
        """Invalidates system-level cache."""
        logger.info("Invalidating system-level TWS cache")
        # Clear all cached system status data
        await self.cache.delete_pattern("tws:system:*")

    async def invalidate_all_jobs(self) -> None:
        """Invalidates all job-related cache."""
        logger.info("Invalidating all job-related TWS cache")
        # Clear all cached job data
        await self.cache.delete_pattern("tws:jobs:*")

    async def invalidate_all_workstations(self) -> None:
        """Invalidates all workstation-related cache."""
        logger.info("Invalidating all workstation-related TWS cache")
        # Clear all cached workstation data
        await self.cache.delete_pattern("tws:workstations:*")

    @property
    def is_connected(self) -> bool:
        """Checks if TWS client is currently connected."""
        if self.use_connection_pool:
            # When using pooled connections, check pool health via the
            # connection pool manager.  Since this property may be accessed in
            # synchronous contexts, we synchronously create or retrieve the
            # manager and invoke its ``is_pool_healthy`` method.  Any
            # exceptions are handled gracefully by returning ``False``.
            try:
                pool_manager = asyncio.run(get_connection_pool_manager())
                return bool(
                    pool_manager.is_pool_healthy("tws_http")
                )
            except Exception:
                return False

        # Otherwise, check the direct HTTPX client if available
        return hasattr(self, "client") and not getattr(self.client, "is_closed", True)

    async def close(self) -> None:
        """Closes underlying HTTPX client and its connections."""
        if self.use_connection_pool:
            # Connection pool manager handles cleanup
            logger.info(
                "TWS client using connection pool - cleanup handled by pool manager"
            )
        else:
            # Close direct client if it exists
            if hasattr(self, "client") and not self.client.is_closed:
                await self.client.aclose()
                logger.info("HTTPX client has been closed.")










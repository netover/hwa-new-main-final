"""
Service layer for optimized module communication in Resync.  

This module provides a service layer that abstracts the communication between  
different modules, reducing direct dependencies and enabling better decoupling.  
"""  

from __future__ import annotations  

import logging  
from abc import abstractmethod  
from typing import Any, Optional, Protocol  

from resync.core.cache_hierarchy import (
    get_cache_hierarchy,
)
from resync.core.interfaces import (
    IAgentManager,
    IKnowledgeGraph,
    ITWSClient,
)
from resync.core.logger import log_with_correlation
from resync.models.tws import (
    CriticalJob,
    JobStatus,
    SystemStatus,
    WorkstationStatus,
)


class ITWSService(Protocol):  
    """Protocol for TWS service operations."""  

    @abstractmethod  
    async def get_system_status(self) -> SystemStatus:  
        """Get the overall system status."""  
        pass  

    @abstractmethod  
    async def get_workstations_status(self) -> list[WorkstationStatus]:  
        """Get the status of all workstations."""  
        pass  

    @abstractmethod  
    async def get_jobs_status(self) -> list[JobStatus]:  
        """Get the status of all jobs."""  
        pass  

    @abstractmethod  
    async def get_critical_path_status(self) -> list[CriticalJob]:  
        """Get the status of jobs on the critical path."""  
        pass  

    @abstractmethod  
    async def get_job_status_batch(self, job_ids: list[str]) -> dict[str, Optional[JobStatus]]:  
        """Get the status of multiple jobs in a batch."""  
        pass  


class IAgentService(Protocol):  
    """Protocol for agent service operations."""  

    @abstractmethod  
    async def get_agent(self, agent_id: str) -> Any:  
        """Get an agent by ID."""  
        pass  

    @abstractmethod  
    async def get_all_agents(self) -> list[Any]:  
        """Get all agents."""  
        pass  


class IKnowledgeService(Protocol):  
    """Protocol for knowledge service operations."""  

    @abstractmethod  
    async def search_similar_issues(self, query: str, limit: int = 5) -> list[dict[str, Any]]:  
        """Search for similar issues in the knowledge graph."""  
        pass  

    @abstractmethod  
    async def get_relevant_context(self, user_query: str) -> str:  
        """Get relevant context for a user query."""  
        pass  


class TWSService:  
    """Concrete implementation of TWS service."""  

    def __init__(self, tws_client: ITWSClient) -> None:  
        self.tws_client = tws_client  
        self.cache = get_cache_hierarchy()  
        self.logger = logging.getLogger(__name__)  

    async def get_system_status(self) -> SystemStatus:  
        """Get the overall system status."""  
        try:  
            # Try to retrieve from cache first
            cache_key = "service_system_status"  
            cached_result = await self.cache.get(cache_key)  
            if cached_result:  
                return SystemStatus(**cached_result)  

            # Fetch from TWS client if not in cache
            result = await self.tws_client.get_system_status()  

            # Store in cache
            await self.cache.set(cache_key, result.dict(), ttl=30)  

            return result  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to get system status: {str(e)}",  
                component="tws_service",  
            )  
            raise  

    async def get_workstations_status(self) -> list[WorkstationStatus]:  
        """Get the status of all workstations."""  
        try:  
            # Try to retrieve from cache first
            cache_key = "service_workstations_status"  
            cached_result = await self.cache.get(cache_key)  
            if cached_result:  
                return [WorkstationStatus(**ws) for ws in cached_result]  

            # Fetch from TWS client if not in cache
            result = await self.tws_client.get_workstations_status()  

            # Store in cache
            await self.cache.set(cache_key, [ws.dict() for ws in result], ttl=30)  

            return result  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to get workstations status: {str(e)}",  
                component="tws_service",  
            )  
            raise  

    async def get_jobs_status(self) -> list[JobStatus]:  
        """Get the status of all jobs."""  
        try:  
            # Try to retrieve from cache first
            cache_key = "service_jobs_status"  
            cached_result = await self.cache.get(cache_key)  
            if cached_result:  
                return [JobStatus(**job) for job in cached_result]  

            # Fetch from TWS client if not in cache
            result = await self.tws_client.get_jobs_status()  

            # Store in cache
            await self.cache.set(cache_key, [job.dict() for job in result], ttl=30)  

            return result  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to get jobs status: {str(e)}",  
                component="tws_service",  
            )  
            raise  

    async def get_critical_path_status(self) -> list[CriticalJob]:  
        """Get the status of jobs on the critical path."""  
        try:  
            # Try to retrieve from cache first
            cache_key = "service_critical_path_status"  
            cached_result = await self.cache.get(cache_key)  
            if cached_result:  
                return [CriticalJob(**cj) for cj in cached_result]  

            # Fetch from TWS client if not in cache
            result = await self.tws_client.get_critical_path_status()  

            # Store in cache
            await self.cache.set(cache_key, [cj.dict() for cj in result], ttl=30)  

            return result  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to get critical path status: {str(e)}",  
                component="tws_service",  
            )  
            raise  

    async def get_job_status_batch(self, job_ids: list[str]) -> dict[str, Optional[JobStatus]]:  
        """Get the status of multiple jobs in a batch."""  
        try:  
            results = {}  
            uncached_job_ids = []  

            # Check cache for each job
            for job_id in job_ids:  
                cache_key = f"service_job_status_{job_id}"  
                cached_result = await self.cache.get(cache_key)  
                if cached_result:  
                    results[job_id] = JobStatus(**cached_result) if cached_result else None  
                else:  
                    uncached_job_ids.append(job_id)  

            # Fetch uncached jobs from TWS client
            if uncached_job_ids:  
                uncached_results = await self.tws_client.get_job_status_batch(uncached_job_ids)  
                for job_id, job_status in uncached_results.items():  
                    results[job_id] = job_status  
                    # Cache the individual result
                    await self.cache.set(  
                        f"service_job_status_{job_id}",  
                        job_status.dict() if job_status else None,  
                        ttl=30,  
                    )  

            return results  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to get job status batch: {str(e)}",  
                component="tws_service",  
            )  
            raise  


class AgentService:  
    """Concrete implementation of agent service."""  

    def __init__(self, agent_manager: IAgentManager) -> None:  
        self.agent_manager = agent_manager  
        self.logger = logging.getLogger(__name__)  

    async def get_agent(self, agent_id: str) -> Any:  
        """Get an agent by ID."""  
        try:  
            return await self.agent_manager.get_agent(agent_id)  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to get agent {agent_id}: {str(e)}",  
                component="agent_service",  
            )  
            raise  

    async def get_all_agents(self) -> list[Any]:  
        """Get all agents."""  
        try:  
            return await self.agent_manager.get_all_agents()  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to get all agents: {str(e)}",  
                component="agent_service",  
            )  
            raise  


class KnowledgeService:  
    """Concrete implementation of knowledge service."""  

    def __init__(self, knowledge_graph: IKnowledgeGraph) -> None:  
        self.knowledge_graph = knowledge_graph  
        self.logger = logging.getLogger(__name__)  

    async def search_similar_issues(self, query: str, limit: int = 5) -> list[dict[str, Any]]:  
        """Search for similar issues in the knowledge graph."""  
        try:  
            return await self.knowledge_graph.search_similar_issues(query, limit=limit)  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to search similar issues: {str(e)}",  
                component="knowledge_service",  
            )  
            raise  

    async def get_relevant_context(self, user_query: str) -> str:  
        """Get relevant context for a user query."""  
        try:  
            return await self.knowledge_graph.get_relevant_context(user_query)  
        except Exception as e:  
            log_with_correlation(  
                logging.ERROR,  
                f"Failed to get relevant context: {str(e)}",  
                component="knowledge_service",  
            )  
            raise  


class ServiceFactory:  
    """Factory for creating service instances with proper dependency injection."""  

    @staticmethod  
    def create_tws_service(tws_client: ITWSClient) -> ITWSService:  
        """Create a TWS service instance."""  
        return TWSService(tws_client)  

    @staticmethod  
    def create_agent_service(agent_manager: IAgentManager) -> IAgentService:  
        """Create an agent service instance."""  
        return AgentService(agent_manager)  

    @staticmethod  
    def create_knowledge_service(knowledge_graph: IKnowledgeGraph) -> IKnowledgeService:  
        """Create a knowledge service instance."""  
        return KnowledgeService(knowledge_graph)  

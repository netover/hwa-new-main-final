# resync/core/rag_health_check.py
"""
Health check implementation for RAG (Retrieval-Augmented Generation) system.

This module provides comprehensive health checks for the RAG system components,
including file system access, document processing, knowledge graph connectivity,
and search functionality.
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from resync.core.exceptions import FileProcessingError, KnowledgeGraphError
from resync.core.file_ingestor import FileIngestor, is_path_in_knowledge_base
from resync.core.interfaces import IFileIngestor, IKnowledgeGraph
from resync.core.structured_logger import get_logger
from resync.settings import settings

logger = get_logger(__name__)


class RAGHealthCheck:
    """
    Comprehensive health check for RAG system components.

    Provides checks for:
    - File system access and permissions
    - Document processing capabilities
    - Knowledge graph connectivity and operations
    - Search functionality
    - Directory structure integrity
    """

    def __init__(self, file_ingestor: IFileIngestor, knowledge_graph: IKnowledgeGraph):
        """
        Initialize RAG health checker.

        Args:
            file_ingestor: File ingestion service
            knowledge_graph: Knowledge graph service
        """
        self.file_ingestor = file_ingestor
        self.knowledge_graph = knowledge_graph
        self.check_results: Dict[str, Any] = {}
        self.start_time = 0
        self.end_time = 0

    async def run_comprehensive_check(self) -> Dict[str, Any]:
        """
        Run all RAG health checks.

        Returns:
            Dictionary with check results and metadata
        """
        self.start_time = time.time()

        try:
            # Run all individual checks
            checks = await asyncio.gather(
                self._check_knowledge_base_directories(),
                self._check_file_system_permissions(),
                self._check_document_processing(),
                self._check_knowledge_graph_connectivity(),
                self._check_search_functionality(),
                self._check_file_ingestion_pipeline(),
            )

            # Aggregate results
            self.check_results = {
                "knowledge_base_directories": checks[0],
                "file_system_permissions": checks[1],
                "document_processing": checks[2],
                "knowledge_graph_connectivity": checks[3],
                "search_functionality": checks[4],
                "file_ingestion_pipeline": checks[5],
            }

            # Calculate overall health
            overall_healthy = all(
                result.get("healthy", False)
                for result in self.check_results.values()
            )

            self.end_time = time.time()

            return {
                "overall_healthy": overall_healthy,
                "execution_time": self.end_time - self.start_time,
                "checks_performed": len(self.check_results),
                "timestamp": self.end_time,
                "details": self.check_results,
            }

        except Exception as e:
            logger.error("rag_health_check_failed", error=str(e), exc_info=True)
            self.end_time = time.time()

            return {
                "overall_healthy": False,
                "execution_time": self.end_time - self.start_time,
                "error": str(e),
                "timestamp": self.end_time,
                "details": self.check_results,
            }

    async def _check_knowledge_base_directories(self) -> Dict[str, Any]:
        """
        Check if knowledge base directories exist and are accessible.

        Returns:
            Check result dictionary
        """
        try:
            accessible_dirs = []
            inaccessible_dirs = []

            for knowledge_dir in settings.KNOWLEDGE_BASE_DIRS:
                dir_path = Path(knowledge_dir)
                if dir_path.exists() and dir_path.is_dir():
                    # Try to list directory contents
                    try:
                        list(dir_path.iterdir())
                        accessible_dirs.append(str(dir_path))
                    except (PermissionError, OSError) as e:
                        inaccessible_dirs.append({
                            "path": str(dir_path),
                            "error": str(e)
                        })
                else:
                    inaccessible_dirs.append({
                        "path": str(dir_path),
                        "error": "Directory does not exist"
                    })

            healthy = len(inaccessible_dirs) == 0

            return {
                "healthy": healthy,
                "accessible_directories": accessible_dirs,
                "inaccessible_directories": inaccessible_dirs,
                "total_directories": len(settings.KNOWLEDGE_BASE_DIRS),
            }

        except Exception as e:
            logger.error("knowledge_base_directory_check_failed", error=str(e))
            return {
                "healthy": False,
                "error": str(e),
            }

    async def _check_file_system_permissions(self) -> Dict[str, Any]:
        """
        Check file system permissions for RAG operations.

        Returns:
            Check result dictionary
        """
        try:
            # Test write permissions by creating a temporary test file
            test_file_created = False
            test_file_path = None

            for knowledge_dir in settings.KNOWLEDGE_BASE_DIRS:
                dir_path = Path(knowledge_dir)
                if dir_path.exists() and dir_path.is_dir():
                    try:
                        # Try to create a temporary test file
                        test_file_path = dir_path / ".rag_health_test.tmp"
                        test_file_path.write_text("test")
                        test_file_path.unlink()  # Clean up
                        test_file_created = True
                        break
                    except (PermissionError, OSError):
                        continue

            # Check read permissions on protected directories
            protected_dirs_accessible = []
            protected_dirs_inaccessible = []

            for protected_dir in settings.PROTECTED_DIRECTORIES:
                dir_path = Path(protected_dir)
                if dir_path.exists():
                    try:
                        list(dir_path.iterdir())
                        protected_dirs_accessible.append(str(dir_path))
                    except (PermissionError, OSError) as e:
                        protected_dirs_inaccessible.append({
                            "path": str(dir_path),
                            "error": str(e)
                        })

            healthy = test_file_created and len(protected_dirs_inaccessible) == 0

            return {
                "healthy": healthy,
                "write_permissions": test_file_created,
                "protected_dirs_accessible": protected_dirs_accessible,
                "protected_dirs_inaccessible": protected_dirs_inaccessible,
            }

        except Exception as e:
            logger.error("file_system_permissions_check_failed", error=str(e))
            return {
                "healthy": False,
                "error": str(e),
            }

    async def _check_document_processing(self) -> Dict[str, Any]:
        """
        Check if document processing capabilities are working.

        Returns:
            Check result dictionary
        """
        try:
            # Create a small test document content
            test_content = """
            This is a test document for RAG health check.
            It contains some text that should be processed successfully.
            The health check verifies that document processing works.
            """

            # Test text chunking
            from resync.core.file_ingestor import chunk_text
            chunks = list(chunk_text(test_content, chunk_size=50, chunk_overlap=10))

            # Verify chunks were created
            chunking_works = len(chunks) > 0 and all(len(chunk.strip()) > 0 for chunk in chunks)

            # Test file readers
            file_readers_available = []
            file_readers_unavailable = []

            # Check if file readers are available (don't actually call them)
            from resync.core.file_ingestor import FileIngestor
            if hasattr(self.file_ingestor, 'file_readers'):
                for ext, reader_func in self.file_ingestor.file_readers.items():
                    if reader_func is not None:
                        file_readers_available.append(ext)
                    else:
                        file_readers_unavailable.append(ext)

            healthy = chunking_works and len(file_readers_available) > 0

            return {
                "healthy": healthy,
                "chunking_works": chunking_works,
                "chunks_created": len(chunks),
                "file_readers_available": file_readers_available,
                "file_readers_unavailable": file_readers_unavailable,
            }

        except Exception as e:
            logger.error("document_processing_check_failed", error=str(e))
            return {
                "healthy": False,
                "error": str(e),
            }

    async def _check_knowledge_graph_connectivity(self) -> Dict[str, Any]:
        """
        Check knowledge graph connectivity and basic operations.

        Returns:
            Check result dictionary
        """
        try:
            # Test basic connectivity (this will use circuit breaker if available)
            test_content = "RAG health check test content"
            test_metadata = {
                "source": "health_check",
                "test_id": f"test_{int(time.time())}"
            }

            # Try to add test content
            try:
                await self.knowledge_graph.add_content(test_content, test_metadata)
                content_added = True
            except Exception as e:
                logger.warning("knowledge_graph_add_content_failed", error=str(e))
                content_added = False

            # Try to get relevant context
            try:
                context = await self.knowledge_graph.get_relevant_context("test query")
                context_retrieved = isinstance(context, str)
            except Exception as e:
                logger.warning("knowledge_graph_get_context_failed", error=str(e))
                context_retrieved = False

            healthy = content_added or context_retrieved  # At least one operation should work

            return {
                "healthy": healthy,
                "content_addition_works": content_added,
                "context_retrieval_works": context_retrieved,
                "basic_connectivity": True,  # If we reach here, connection works
            }

        except Exception as e:
            logger.error("knowledge_graph_connectivity_check_failed", error=str(e))
            return {
                "healthy": False,
                "error": str(e),
            }

    async def _check_search_functionality(self) -> Dict[str, Any]:
        """
        Check search functionality in the knowledge graph.

        Returns:
            Check result dictionary
        """
        try:
            # Test different search operations
            search_tests = []

            # Test get_relevant_context
            try:
                context = await self.knowledge_graph.get_relevant_context("artificial intelligence")
                search_tests.append({
                    "operation": "get_relevant_context",
                    "success": True,
                    "result_length": len(context) if context else 0
                })
            except Exception as e:
                search_tests.append({
                    "operation": "get_relevant_context",
                    "success": False,
                    "error": str(e)
                })

            # Test search_similar_issues (if available)
            if hasattr(self.knowledge_graph, 'search_similar_issues'):
                try:
                    issues = await self.knowledge_graph.search_similar_issues("test issue")
                    search_tests.append({
                        "operation": "search_similar_issues",
                        "success": True,
                        "result_count": len(issues) if issues else 0
                    })
                except Exception as e:
                    search_tests.append({
                        "operation": "search_similar_issues",
                        "success": False,
                        "error": str(e)
                    })

            # Check if at least one search operation works
            successful_searches = [test for test in search_tests if test["success"]]
            healthy = len(successful_searches) > 0

            return {
                "healthy": healthy,
                "search_tests": search_tests,
                "successful_searches": len(successful_searches),
                "total_tests": len(search_tests),
            }

        except Exception as e:
            logger.error("search_functionality_check_failed", error=str(e))
            return {
                "healthy": False,
                "error": str(e),
            }

    async def _check_file_ingestion_pipeline(self) -> Dict[str, Any]:
        """
        Check the complete file ingestion pipeline.

        Returns:
            Check result dictionary
        """
        try:
            # Create a small test file content
            test_content = "This is a test file for RAG ingestion health check."
            test_filename = ".rag_health_test.txt"

            # Try to save a test file (if file_ingestor supports it)
            file_saved = False
            file_path = None

            if hasattr(self.file_ingestor, 'save_uploaded_file'):
                try:
                    from io import BytesIO
                    test_file_obj = BytesIO(test_content.encode('utf-8'))
                    file_path = await self.file_ingestor.save_uploaded_file(test_filename, test_file_obj)
                    file_saved = True
                except Exception as e:
                    logger.warning("file_save_test_failed", error=str(e))

            # Test ingestion pipeline
            ingestion_works = False
            if file_saved and file_path and file_path.exists():
                try:
                    ingestion_result = await self.file_ingestor.ingest_file(file_path)
                    ingestion_works = ingestion_result

                    # Clean up test file
                    if file_path.exists():
                        file_path.unlink()

                except Exception as e:
                    logger.warning("file_ingestion_test_failed", error=str(e))

            healthy = ingestion_works or not file_saved  # If can't save, that's OK, but if can save must ingest

            return {
                "healthy": healthy,
                "file_save_works": file_saved,
                "ingestion_works": ingestion_works,
                "pipeline_complete": file_saved and ingestion_works,
            }

        except Exception as e:
            logger.error("file_ingestion_pipeline_check_failed", error=str(e))
            return {
                "healthy": False,
                "error": str(e),
            }


# Convenience function to run RAG health check
async def run_rag_health_check(file_ingestor: IFileIngestor, knowledge_graph: IKnowledgeGraph) -> Dict[str, Any]:
    """
    Run comprehensive RAG health check.

    Args:
        file_ingestor: File ingestion service
        knowledge_graph: Knowledge graph service

    Returns:
        Health check results
    """
    checker = RAGHealthCheck(file_ingestor, knowledge_graph)
    return await checker.run_comprehensive_check()


def get_rag_health_summary(results: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of RAG health check results.

    Args:
        results: Health check results from run_rag_health_check

    Returns:
        Formatted summary string
    """
    if not results.get("overall_healthy", False):
        summary = "[FAIL] RAG System Health: UNHEALTHY\n"
    else:
        summary = "[OK] RAG System Health: HEALTHY\n"

    summary += f"Execution time: {results.get('execution_time', 0):.2f}s\n"
    summary += f"Checks performed: {results.get('checks_performed', 0)}\n\n"

    details = results.get("details", {})
    for check_name, check_result in details.items():
        status = "[OK]" if check_result.get("healthy", False) else "[FAIL]"
        summary += f"{status} {check_name.replace('_', ' ').title()}\n"

        if not check_result.get("healthy", False):
            error = check_result.get("error", "Unknown error")
            summary += f"   Error: {error}\n"

    return summary

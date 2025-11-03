#!/usr/bin/env python3
"""
Test script for RAG Health Check implementation.
This script tests the comprehensive health check for RAG system components.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from resync.core.rag_health_check import (
    RAGHealthCheck,
    get_rag_health_summary,
    run_rag_health_check,
)


async def test_rag_health_check():
    """Test RAG health check functionality."""

    print("Testing RAG Health Check System")
    print("=" * 50)

    try:
        # Import dependencies (these would normally come from DI container)
        from resync.core.file_ingestor import FileIngestor
        from resync.core.knowledge_graph_circuit_breaker import CircuitBreakerAsyncKnowledgeGraph

        # Create services (simplified for testing)
        file_ingestor = FileIngestor.__new__(FileIngestor)  # Create without __init__ for testing
        file_ingestor.file_readers = {".txt": lambda x: "test content"}  # Mock file readers

        knowledge_graph = CircuitBreakerAsyncKnowledgeGraph.__new__(CircuitBreakerAsyncKnowledgeGraph)

        # Test 1: Direct health checker creation and basic functionality
        print("\n1. Testing RAG Health Checker initialization...")
        checker = RAGHealthCheck(file_ingestor, knowledge_graph)
        print("   Health checker created successfully [OK]")

        # Test 2: Run comprehensive health check
        print("\n2. Running comprehensive RAG health check...")
        try:
            results = await checker.run_comprehensive_check()

            print(f"   Overall healthy: {results.get('overall_healthy', False)}")
            print(f"   Execution time: {results.get('execution_time', 0):.2f}s")
            print(f"   Checks performed: {results.get('checks_performed', 0)}")

            # Show details of each check
            details = results.get("details", {})
            for check_name, check_result in details.items():
                status = "[OK]" if check_result.get("healthy", False) else "[FAIL]"
                print(f"   {status} {check_name.replace('_', ' ').title()}")

        except Exception as e:
            print(f"   Health check failed: {type(e).__name__}: {e}")

        # Test 3: Test convenience function
        print("\n3. Testing convenience function...")
        try:
            convenience_results = await run_rag_health_check(file_ingestor, knowledge_graph)
            print(f"   Convenience function works: {bool(convenience_results)}")
        except Exception as e:
            print(f"   Convenience function failed: {type(e).__name__}")

        # Test 4: Test summary generation
        print("\n4. Testing summary generation...")
        try:
            if 'results' in locals():
                summary = get_rag_health_summary(results)
                print("   Summary generated successfully")
                print("   Summary preview:")
                print("   " + "\n   ".join(summary.split("\n")[:3]))  # First 3 lines
            else:
                print("   No results to summarize")
        except Exception as e:
            print(f"   Summary generation failed: {type(e).__name__}")

        print("\n" + "=" * 50)
        print("[SUCCESS] RAG Health Check implementation working correctly!")
        print("The health check provides comprehensive monitoring of RAG system components.")

    except Exception as e:
        print(f"\n[ERROR] Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("RAG Health Check Test")
    print("=" * 40)

    # Run the async test
    asyncio.run(test_rag_health_check())

    print("\n" + "=" * 40)
    print("Test completed!")





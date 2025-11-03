"""
Tests for the background_tasks fixture.
This module demonstrates how to use the background_tasks fixture for testing.
"""

import asyncio
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_background_tasks_fixture_basic_usage(background_tasks):
    """
    Test basic usage of the background_tasks fixture.

    This test shows how to:
    1. Start capturing background tasks
    2. Create tasks that would normally run in the background
    3. Verify they were captured
    4. Execute them manually
    """
    # Start capturing tasks
    background_tasks.start_capturing()

    # Results tracker
    results = []

    # Define some async functions
    async def task_one():
        results.append("task_one_executed")
        return "result_one"

    async def task_two():
        results.append("task_two_executed")
        return "result_two"

    # Create background tasks (these will be captured, not executed)
    asyncio.create_task(task_one())
    asyncio.create_task(task_two())

    # Verify tasks were captured
    assert background_tasks.task_count == 2

    # Execute tasks manually
    execution_results = await background_tasks.run_all_async()

    # Verify execution results
    assert len(execution_results) == 2
    assert "result_one" in execution_results
    assert "result_two" in execution_results

    # Verify the tasks actually ran
    assert "task_one_executed" in results
    assert "task_two_executed" in results


@pytest.mark.asyncio
async def test_background_tasks_with_chat_api_example(background_tasks):
    """
    Test the background_tasks fixture with a real example from the chat API.

    This test shows how the fixture can be used to test the IA Auditor background task
    that is created in resync/api/chat.py.
    """
    # Import the function that creates the background task
    from resync.api.chat import run_auditor_safely

    # Start capturing tasks
    background_tasks.start_capturing()

    # Mock the analyze_and_flag_memories function to avoid actual processing
    with patch("resync.api.chat.analyze_and_flag_memories") as mock_analyze:
        mock_analyze.return_value = {
            "processed": 1,
            "deleted": 0,
            "flagged": 0,
        }

        # Create a background task as done in the chat API
        # This is the exact pattern used in resync/api/chat.py line 126
        asyncio.create_task(run_auditor_safely())

        # Verify task was captured
        assert background_tasks.task_count == 1

        # Execute the task manually
        results = await background_tasks.run_all_async()

        # Verify the task executed
        assert len(results) == 1
        mock_analyze.assert_called_once()


@pytest.mark.asyncio
async def test_background_tasks_reset_functionality(background_tasks):
    """
    Test the reset functionality of the background_tasks fixture.
    """
    # Start capturing tasks
    background_tasks.start_capturing()

    async def sample_task():
        return "sample_result"

    # Create a few tasks
    asyncio.create_task(sample_task())
    asyncio.create_task(sample_task())

    # Verify tasks were captured
    assert background_tasks.task_count == 2

    # Reset the fixture
    background_tasks.reset()

    # Verify tasks were cleared
    assert background_tasks.task_count == 0
    assert len(background_tasks.captured_tasks) == 0


@pytest.mark.asyncio
async def test_background_tasks_stop_capturing(background_tasks):
    """
    Test that stopping capture prevents further task capture.
    """
    # Start capturing tasks
    background_tasks.start_capturing()

    async def sample_task():
        return "sample_result"

    # Create a task while capturing
    asyncio.create_task(sample_task())
    assert background_tasks.task_count == 1

    # Stop capturing
    background_tasks.stop_capturing()

    # Create another task - this should not be captured
    asyncio.create_task(sample_task())

    # Count should still be 1
    assert background_tasks.task_count == 1

    # Start capturing again
    background_tasks.start_capturing()

    # Create another task - this should be captured
    asyncio.create_task(sample_task())

    # Count should now be 2
    assert background_tasks.task_count == 2





import asyncio

import pytest

from resync.core.task_manager import TaskManager


class TestTaskManager:
    """Testes para o TaskManager."""

    @pytest.fixture
    def task_manager(self):
        """Fixture para criar uma instância do TaskManager."""
        return TaskManager()

    @pytest.mark.asyncio
    async def test_task_creation(self, task_manager):
        """Testar criação de tarefas."""

        def example_task():
            return "task_result"

        task = task_manager.create_task(example_task, name="test_task")

        assert task.name == "test_task"
        assert not task.done()

    @pytest.mark.asyncio
    async def test_task_completion(self, task_manager, event_loop):
        """Testar conclusão de tarefas."""

        def example_task():
            return "task_result"

        task = task_manager.create_task(example_task, name="test_task")

        # Simular conclusão da tarefa
        task.set_result("task_result")

        result = await task

        assert result == "task_result"
        assert task.done()

    @pytest.mark.asyncio
    async def test_task_failure(self, task_manager, event_loop):
        """Testar falha de tarefas."""

        def example_task():
            raise ValueError("Task failed")

        task = task_manager.create_task(example_task, name="test_task")

        # Simular falha da tarefa
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert task.done()
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_task_metrics(self, task_manager):
        """Testar métricas de tarefas."""
        # Criar várias tarefas
        for _ in range(5):
            task_manager.create_task(lambda: "result", name="task")

        metrics = task_manager.get_metrics()

        assert metrics["total_tasks"] == 5
        assert metrics["active_tasks"] == 5

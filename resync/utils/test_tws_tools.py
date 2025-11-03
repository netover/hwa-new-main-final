from unittest.mock import AsyncMock

import pytest

from ...tool_definitions.tws_tools import (
    tws_status_tool,
    tws_troubleshooting_tool,
)
from ..exceptions import (
    ToolConnectionError,
    ToolExecutionError,
    ToolProcessingError,
    TWSConnectionError,
)

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_tws_client():
    """Provides a mock TWS client for injection into tools."""
    client = AsyncMock()
    # Inject the mock client into the singleton tool instances for testing
    tws_status_tool.tws_client = client
    tws_troubleshooting_tool.tws_client = client
    return client


async def test_tws_status_tool_raises_tool_connection_error(mock_tws_client):
    """
    Ensures TWSStatusTool correctly wraps a TWSConnectionError
    into a ToolConnectionError.
    """
    # Arrange: Simulate a connection failure from the service
    mock_tws_client.get_system_status.side_effect = TWSConnectionError(
        "TWS is down"
    )

    # Act & Assert
    with pytest.raises(ToolConnectionError) as excinfo:
        await tws_status_tool.get_tws_status()

    assert "Falha de comunicação com o TWS" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, TWSConnectionError)


async def test_tws_status_tool_raises_tool_processing_error_on_value_error(
    mock_tws_client,
):
    """
    Ensures TWSStatusTool raises ToolProcessingError on a data processing error.
    """
    # Arrange: Simulate a data processing failure
    mock_tws_client.get_system_status.side_effect = ValueError(
        "Bad data from TWS"
    )

    # Act & Assert
    with pytest.raises(ToolProcessingError) as excinfo:
        await tws_status_tool.get_tws_status()

    assert "Erro ao processar os dados de status do TWS" in str(excinfo.value)


async def test_troubleshooting_tool_raises_tool_execution_error_on_unexpected_error(
    mock_tws_client,
):
    """
    Ensures the tool's generic exception handler wraps unexpected errors
    in a ToolExecutionError.
    """
    # Arrange: Simulate an unexpected failure
    mock_tws_client.get_system_status.side_effect = Exception(
        "Something broke"
    )

    # Act & Assert
    with pytest.raises(ToolExecutionError) as excinfo:
        await tws_troubleshooting_tool.analyze_failures()

    assert "Ocorreu um erro inesperado ao analisar as falhas do TWS" in str(
        excinfo.value
    )





# Resync Extension Guide

## Overview

Resync is designed to be extended with new agents, integrations, and AI capabilities. This guide explains how to:

1. Create new agents
2. Add integrations
3. Extend AI functionality
4. Maintain compatibility

## 1. Creating New Agents

### Agent Structure
```python
# resync/core/agents/your_agent.py
from resync.core.agent_manager import AgentBase

class YourAgent(AgentBase):
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "Your Agent"
        self.version = "1.0.0"
        self.description = "Does something useful"

    async def health_check(self) -> bool:
        # Implement health check
        return True

    async def execute(self):
        # Main execution logic
        pass
```

### Registration
```python
# resync/core/agent_manager.py
class AgentManager:
    def __init__(self):
        self.agents = [
            YourAgent(config),
            # ... other agents
        ]
```

## 2. Adding Integrations

### New Service Integration
```python
# resync/services/your_service.py
from resync.core.dependencies import ServiceBase

class YourService(ServiceBase):
    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get("base_url")

    async def make_request(self, endpoint: str):
        # Implement request logic
        return await self.client.get(endpoint)
```

### Dependency Injection
```python
# resync/core/dependencies.py
def get_your_service dependency():
    return YourService(settings.your_service_config)
```

## 3. Extending AI Functionality

### New LLM Integration
```python
# resync/core/utils/llm.py
class YourLLMClient:
    async def generate(self, prompt: str) -> str:
        # Implement generation logic
        return generated_text
```

### Configuration
Update `.env`:
```
LLM_ENDPOINT=your_end point
LLM_API_KEY=your_api_key
AGENT_MODEL_NAME=your_model
```

## 4. Maintain Compatibility

### Versioning
- Follow Semantic Versioning (SemVer)
- Update `pyproject.toml` with new version
- Document breaking changes in CHANGELOG.md

### Backward Compatibility
- Maintain deprecated functionality for 2 minor versions
- Provide migration guides for breaking changes

## 5. Testing Extensions

### Unit Tests
```python
# tests/test_your_agent.py
def test_your_agent_health_check():
    agent = YourAgent(config)
    assert agent.health_check()
```

### Integration Tests
```python
# tests/integration/test_your_service.py
async def test_your_service_integration():
    service = YourService(config)
    response = await service.make_request("/endpoint")
    assert response.status == 200
```

## 6. Documentation

For any extension:
1. Update `docs/extension-guide.md`
2. Add API documentation if applicable
3. Update README.md
4. Register new metrics if needed

## Example Extensions

### Agent Example
- Check the existing `CheckStatusAgent` implementation
- Review test cases in `tests/test_agent_manager.py`

### Integration Example
- Study the TWS service implementation
- Review service tests in `tests/test_tws_service.py`

## Best Practices

1. **Modularity**: Keep agents focused on single responsibilities
2. **Resiliency**: Implement retries and error handling
3. **Observability**: Add relevant metrics and logging
4. **Documentation**: Include usage examples in documentation
5. **Testing**: Write comprehensive unit and integration tests

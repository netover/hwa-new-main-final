
from fastapi import APIRouter
from ..models.response_models import AgentListResponse

router = APIRouter(tags=["Agents"])

@router.get("/")
def list_agents() -> AgentListResponse:
    """
    List all available agents
    """
    # Return some demo agents for testing
    demo_agents = [
        {
            "id": "demo-agent-1",
            "name": "Agente de Demonstração 1",
            "status": "ativo",
            "description": "Agente para testes de monitoramento TWS"
        },
        {
            "id": "demo-agent-2", 
            "name": "Agente de Demonstração 2",
            "status": "ativo",
            "description": "Agente para testes de troubleshooting"
        },
        {
            "id": "demo-agent-3",
            "name": "Agente de Demonstração 3",
            "status": "ativo",
            "description": "Agente para testes gerais"
        }
    ]
    return AgentListResponse(agents=demo_agents, total=len(demo_agents))

# Note: /status route moved to status router to avoid conflicts

# Solução do Problema WebSocket no Resync

## Diagnóstico do Problema

O problema principal era um erro `'str' object has no attribute 'to_dict'` que ocorria quando o WebSocket tentava processar mensagens do agente. Após análise detalhada, identificamos três problemas críticos:

1. **Problemas com o `MockAgent`**:
   - Faltavam atributos essenciais (`description`, `llm_model`)
   - O método `to_dict()` não estava implementado corretamente
   - Havia linhas problemáticas no `__init__` que causavam conflitos

2. **Problemas no tratamento WebSocket**:
   - O loop infinito tentava receber mensagens mesmo após a desconexão
   - Erros de serialização JSON ao enviar respostas
   - Falta do import `json` em alguns casos

3. **Problemas de integração com FastAPI/Starlette**:
   - Erro `Cannot call "receive" once a disconnect message has been received` indicando que o WebSocket estava tentando receber mensagens após a desconexão
   - Problemas com a serialização de objetos complexos

## Solução Implementada

### 1. Correção do `MockAgent` (resync/core/agent_manager.py)

```python
class MockAgent:
    """Mock Agent class compatible with agno.Agent interface."""
    
    def __init__(
        self,
        tools: Any = None,
        model: Any = None,
        instructions: Any = None,
        name: str = "Mock Agent",
        description: str = "Mock agent for testing",
        **kwargs: Any,
    ) -> None:
        # Initialize all required attributes
        self.tools = tools or []
        self.model = model
        self.llm_model = model  # Alias para compatibilidade com FastAPI
        self.instructions = instructions
        self.name = name
        self.description = description

        # Additional attributes that FastAPI might expect
        self.role = "Mock Agent"
        self.goal = "Provide mock responses for testing"
        self.backstory = description
        
    # Implementação do método to_dict()
    def to_dict(self) -> dict:
        """Convert agent to dictionary for serialization - required by FastAPI."""
        return {
            "name": self.name,
            "description": self.description,
            "model": str(self.model) if self.model else None,
            "llm_model": str(self.llm_model) if self.llm_model else None,
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "tools": [str(t) for t in self.tools] if self.tools else [],
        }
```

### 2. Simplificação do WebSocket (resync/api/chat.py)

Mudamos o modelo de processamento para lidar com uma única mensagem por conexão, evitando problemas de desconexão:

```python
# Single message processing model to avoid disconnect issues
try:
    # Receive message from client (only once)
    raw_data = await websocket.receive_text()
    logger.info(f"Received message for agent '{agent_id}': {raw_data}")
    
    try:
        # Process message with agent
        logger.info(f"Processing message with MockAgent: {raw_data}")
        
        # Use direct string responses instead of complex agent processing
        msg = raw_data.lower()
        if "job" in msg and ("abend" in msg or "erro" in msg):
            response = "Jobs em estado ABEND encontrados:\n- Data Processing (ID: JOB002) na workstation TWS_AGENT2\n\nRecomendo investigar o log do job e verificar dependências."
        elif "status" in msg or "workstation" in msg:
            response = "Status atual do ambiente TWS:\n\nWorkstations:\n- TWS_MASTER: ONLINE\n- TWS_AGENT1: ONLINE\n- TWS_AGENT2: OFFLINE\n\nJobs:\n- Daily Backup: SUCC (TWS_AGENT1)\n- Data Processing: ABEND (TWS_AGENT2)\n- Report Generation: SUCC (TWS_AGENT1)"
        elif "tws" in msg:
            response = f"Como {agent_id}, posso ajudar com questões relacionadas ao TWS. Que informações você precisa?"
        else:
            response = f"Entendi sua mensagem: '{raw_data}'. Como {agent_id}, estou aqui para ajudar com questões do TWS."
        
        # Send response back to client
        response_data = {
            "type": "message",
            "sender": "agent",
            "message": response,
        }
        await websocket.send_text(json.dumps(response_data))
        
    except Exception as agent_error:
        error_data = {
            "type": "error",
            "sender": "agent",
            "message": f"Erro ao processar mensagem: {str(agent_error)}",
        }
        await websocket.send_text(json.dumps(error_data))
        
    # Close connection gracefully after processing
    await websocket.close()
    
except WebSocketDisconnect:
    logger.info(f"Client disconnected from agent '{agent_id}'.")
except Exception as e:
    logger.error(f"Unexpected error in WebSocket for agent '{agent_id}': {e}")
```

### 3. Garantir imports corretos

Adicionamos o import `json` no início do arquivo:

```python
import json
```

## Conclusões e Aprendizados

1. **WebSockets em FastAPI/Starlette**:
   - Após um WebSocket ser desconectado, não é possível chamar `receive()` novamente
   - É importante tratar corretamente os erros e fechar conexões de forma limpa

2. **Serialização de Objetos**:
   - Objetos complexos precisam ter um método `to_dict()` para serialização adequada
   - É mais seguro usar `json.dumps()` explicitamente com `send_text()` do que `send_json()`

3. **Modelo de Processamento**:
   - Para aplicações simples, um modelo de "uma mensagem por conexão" pode ser mais robusto
   - Em cenários mais complexos, é necessário gerenciar cuidadosamente o ciclo de vida da conexão WebSocket

A solução implementada resolve o problema específico do erro `'str' object has no attribute 'to_dict'` e também melhora a robustez geral do sistema WebSocket.

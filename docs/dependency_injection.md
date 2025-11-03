# Injeção de Dependências no Resync

Este documento descreve o padrão de injeção de dependências implementado no projeto Resync, explicando sua arquitetura, uso e melhores práticas.

## Visão Geral

A injeção de dependências (DI) é um padrão de design que permite que classes recebam suas dependências de fontes externas em vez de criá-las internamente. Isso promove:

- **Desacoplamento**: Reduz o acoplamento entre componentes
- **Testabilidade**: Facilita a substituição de dependências reais por mocks em testes
- **Flexibilidade**: Permite trocar implementações sem modificar o código cliente
- **Reutilização**: Facilita o compartilhamento de instâncias entre diferentes partes da aplicação

## Arquitetura

O sistema de DI do Resync é composto pelos seguintes componentes:

### 1. Container de DI (`DIContainer`)

O `DIContainer` é o componente central que gerencia o ciclo de vida dos serviços. Ele permite:

- Registrar interfaces e suas implementações
- Definir o escopo dos serviços (singleton ou transient)
- Resolver dependências automaticamente
- Registrar instâncias pré-criadas ou factory functions

### 2. Interfaces

As interfaces definem os contratos que as implementações devem seguir. Usamos `Protocol` do Python para definir interfaces de forma estrutural, sem necessidade de herança explícita.

Principais interfaces:
- `IAgentManager`
- `IConnectionManager`
- `IKnowledgeGraph`
- `IAuditQueue`

### 3. Integração com FastAPI

O módulo `fastapi_di.py` integra o container de DI com o sistema de dependências do FastAPI, permitindo:

- Injetar serviços em endpoints
- Configurar o container automaticamente
- Usar middleware para disponibilizar o container em toda a aplicação

## Como Usar

### Registrando Serviços

```python
from resync.core.di_container import DIContainer, ServiceScope
from resync.core.interfaces import IAgentManager
from resync.core.agent_manager import AgentManager

# Criar ou usar o container global
container = DIContainer()

# Registrar uma interface e sua implementação
container.register(IAgentManager, AgentManager, ServiceScope.SINGLETON)

# Registrar uma instância pré-criada
instance = AgentManager()
container.register_instance(IAgentManager, instance)

# Registrar uma factory function
container.register_factory(IAgentManager, lambda: AgentManager())
```

### Resolvendo Serviços

```python
# Obter uma instância do serviço
agent_manager = container.get(IAgentManager)
```

### Usando em Endpoints FastAPI

```python
from fastapi import APIRouter, Depends
from resync.core.fastapi_di import get_agent_manager
from resync.core.interfaces import IAgentManager

router = APIRouter()

@router.get("/agents")
async def list_agents(agent_manager: IAgentManager = Depends(get_agent_manager)):
    return agent_manager.get_all_agents()
```

### Configurando o Container para uma Aplicação FastAPI

```python
from fastapi import FastAPI
from resync.core.fastapi_di import inject_container

app = FastAPI()
inject_container(app)
```

## Escopos de Serviço

O container suporta dois escopos de serviço:

1. **SINGLETON**: Uma única instância é criada e reutilizada para todas as requisições
2. **TRANSIENT**: Uma nova instância é criada cada vez que o serviço é solicitado

## Testes

### Mockando Serviços

```python
from unittest.mock import MagicMock
from resync.core.di_container import DIContainer
from resync.core.interfaces import IAgentManager

# Criar um container para testes
container = DIContainer()

# Registrar um mock
mock_agent_manager = MagicMock()
container.register_instance(IAgentManager, mock_agent_manager)

# Configurar o mock
mock_agent_manager.get_all_agents.return_value = [{"id": "test-agent"}]
```

### Testando Endpoints com DI

```python
from fastapi.testclient import TestClient
from resync.core.fastapi_di import inject_container

# Criar app com container de teste
app = FastAPI()
inject_container(app, test_container)

# Criar cliente de teste
client = TestClient(app)

# Testar endpoint
response = client.get("/agents")
assert response.status_code == 200
assert response.json() == [{"id": "test-agent"}]
```

## Migração do Padrão Singleton

O projeto está em processo de migração do padrão Singleton para injeção de dependências. Durante a transição:

1. Instâncias globais (como `agent_manager`, `connection_manager`, etc.) ainda existem para compatibilidade
2. Novos códigos devem usar o sistema de DI
3. Códigos existentes serão gradualmente refatorados para usar DI

## Melhores Práticas

1. **Sempre programe para interfaces**, não implementações concretas
2. **Mantenha interfaces focadas** em um conjunto coeso de funcionalidades
3. **Use o escopo apropriado** para cada serviço (singleton para serviços stateless, transient para stateful)
4. **Evite dependências circulares** entre serviços
5. **Documente as dependências** de cada classe para facilitar o entendimento
6. **Prefira injeção via construtor** em vez de injeção via método ou propriedade

## Conclusão

A implementação de injeção de dependências no Resync melhora significativamente a arquitetura do projeto, tornando-o mais modular, testável e manutenível. A integração com FastAPI permite usar o mesmo sistema de DI em toda a aplicação, desde endpoints até serviços de background.




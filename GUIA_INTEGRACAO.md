# Guia de Integração - Melhorias de Erro e Qualidade

## 📋 Visão Geral

Este guia explica como integrar todas as melhorias implementadas no projeto Resync.

---

## 🚀 Passo 1: Substituir o main.py

### Opção A: Substituição Completa (Recomendado)

```bash
# Backup do arquivo atual
cp resync/main.py resync/main_backup.py

# Substituir pelo arquivo melhorado
cp resync/main_improved.py resync/main.py
```

### Opção B: Integração Manual

Se preferir integrar manualmente, adicione as seguintes seções ao seu `main.py`:

#### 1. Imports

```python
# Logging estruturado
from resync.core.structured_logger import configure_structured_logging

# Middleware
from resync.api.middleware import CorrelationIdMiddleware

# Exception handlers
from resync.api.exception_handlers import register_exception_handlers
```

#### 2. Configurar Logging (antes de criar o app)

```python
# Configurar logging estruturado
configure_structured_logging(
    log_level=getattr(settings, 'LOG_LEVEL', 'INFO'),
    json_logs=settings.ENVIRONMENT == "production",
    development_mode=settings.ENVIRONMENT == "development"
)
```

#### 3. Adicionar Middleware (após criar o app)

```python
# Correlation ID Middleware (deve ser o primeiro)
app.add_middleware(CorrelationIdMiddleware)
```

#### 4. Registrar Exception Handlers

```python
# Substituir a linha existente:
# from resync.core.utils.error_utils import register_exception_handlers

# Por:
from resync.api.exception_handlers import register_exception_handlers
register_exception_handlers(app)
```

---

## 🔧 Passo 2: Atualizar Settings

Adicione as seguintes configurações ao arquivo `resync/settings.py`:

```python
# Logging
LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Environment
ENVIRONMENT: str = "development"  # development, staging, production

# Project info (se não existir)
PROJECT_NAME: str = "Resync API"
PROJECT_VERSION: str = "2.0.0"
```

---

## 📦 Passo 3: Instalar Dependências

Adicione ao `requirements.txt` ou `pyproject.toml`:

```txt
structlog>=23.1.0
pydantic>=2.0.0
```

Instalar:

```bash
pip install structlog pydantic
```

---

## 🧪 Passo 4: Testar a Integração

### 1. Executar Testes

```bash
# Testes de exceções
pytest tests/test_exceptions.py -v

# Testes de resiliência
pytest tests/test_resilience.py -v

# Todos os testes
pytest tests/ -v
```

### 2. Iniciar a Aplicação

```bash
# Modo desenvolvimento
python -m resync.main

# Ou com uvicorn
uvicorn resync.main:app --reload
```

### 3. Verificar Logs

Os logs devem aparecer em formato estruturado:

**Desenvolvimento (colorido):**
```
2024-01-15T10:30:00Z [info     ] Application startup completed successfully
```

**Produção (JSON):**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "event": "Application startup completed successfully",
  "service_name": "Resync API",
  "environment": "production",
  "version": "2.0.0"
}
```

---

## 🎯 Passo 5: Usar as Novas Funcionalidades

### 1. Usar Exceções Customizadas

```python
from resync.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    BusinessError,
)

# Em seus endpoints
@app.post("/api/users")
async def create_user(user_data: dict):
    if not user_data.get("email"):
        raise ValidationError(
            message="Email is required",
            details={"field": "email"}
        )
    
    # ... lógica de criação
```

### 2. Usar Logging Estruturado

```python
from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

# Logging com contexto
logger.info(
    "User created successfully",
    user_id=user.id,
    email=user.email
)

# Logging de erro
logger.error(
    "Failed to create user",
    error=str(e),
    exc_info=True
)
```

### 3. Usar Padrões de Resiliência

```python
from resync.core.resilience import resilient, CircuitBreaker

# Decorator resilient
@resilient(
    circuit_breaker_name="external_api",
    max_attempts=3,
    timeout_seconds=30.0
)
async def call_external_api():
    return await external_api.get_data()

# Circuit Breaker manual
cb = CircuitBreaker("payment_service")

async def process_payment(amount: float):
    return await cb.call(payment_service.charge, amount)
```

### 4. Usar Idempotency Keys

```python
from resync.core.idempotency import get_default_manager

manager = get_default_manager()

@manager.idempotent(ttl_seconds=3600)
async def create_order(order_data: dict, idempotency_key: str):
    # Esta operação só será executada uma vez por idempotency_key
    return await db.create_order(order_data)

# Chamar com idempotency key
result = await create_order(
    order_data={"item": "Product A", "quantity": 1},
    idempotency_key="order-123-abc"
)
```

### 5. Usar Respostas Padronizadas

```python
from resync.api.models import success_response, paginated_response

@app.get("/api/users")
async def list_users(page: int = 1, page_size: int = 10):
    users = await db.get_users(page, page_size)
    total = await db.count_users()
    
    return paginated_response(
        items=users,
        total=total,
        page=page,
        page_size=page_size
    )

@app.post("/api/users")
async def create_user(user_data: dict):
    user = await db.create_user(user_data)
    
    return success_response(
        data=user,
        message="User created successfully"
    )
```

---

## 🔍 Passo 6: Verificar Correlation IDs

### 1. Fazer Requisição com Correlation ID

```bash
curl -H "X-Correlation-ID: test-123" http://localhost:8000/api/health
```

### 2. Verificar Resposta

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Headers da resposta devem incluir:
```
X-Correlation-ID: test-123
```

### 3. Verificar Logs

Todos os logs relacionados devem incluir o correlation_id:

```json
{
  "correlation_id": "test-123",
  "event": "Health check requested",
  ...
}
```

---

## 📊 Passo 7: Monitorar Erros

### 1. Endpoint de Health Check

```bash
curl http://localhost:8000/api/health
```

### 2. Verificar Métricas de Circuit Breaker

```python
from resync.core.resilience import CircuitBreaker

cb = CircuitBreaker("external_api")
stats = cb.get_stats()

print(stats)
# {
#   "name": "external_api",
#   "state": "closed",
#   "total_calls": 100,
#   "total_failures": 5,
#   "total_successes": 95
# }
```

---

## 🐛 Troubleshooting

### Problema: Logs não aparecem em JSON

**Solução:** Verificar configuração do ambiente

```python
# Em settings.py
ENVIRONMENT = "production"  # Deve ser "production" para JSON
```

### Problema: Correlation ID não aparece

**Solução:** Verificar ordem dos middlewares

```python
# Correlation ID deve ser o PRIMEIRO middleware
app.add_middleware(CorrelationIdMiddleware)
# Outros middlewares depois...
```

### Problema: Exception handlers não funcionam

**Solução:** Verificar se está registrado corretamente

```python
from resync.api.exception_handlers import register_exception_handlers
register_exception_handlers(app)
```

### Problema: Import errors

**Solução:** Verificar estrutura de diretórios

```
resync/
├── api/
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── correlation_id.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── responses.py
│   ├── exception_handlers.py
│   └── ...
├── core/
│   ├── exceptions.py
│   ├── context.py
│   ├── structured_logger.py
│   ├── resilience.py
│   ├── idempotency.py
│   └── ...
└── main.py
```

---

## ✅ Checklist de Integração

- [ ] Backup do main.py original
- [ ] Logging estruturado configurado
- [ ] Middleware de Correlation ID adicionado
- [ ] Exception handlers registrados
- [ ] Settings atualizados
- [ ] Dependências instaladas
- [ ] Testes executados com sucesso
- [ ] Aplicação inicia sem erros
- [ ] Logs aparecem corretamente
- [ ] Correlation IDs funcionando
- [ ] Respostas de erro padronizadas
- [ ] Documentação da API atualizada

---

## 📚 Próximos Passos

1. **Refatorar código existente** para usar as novas exceções
2. **Adicionar type hints** nos arquivos com baixa cobertura
3. **Implementar testes de integração**
4. **Configurar monitoramento** (Prometheus, Grafana)
5. **Criar dashboards** para métricas de resiliência
6. **Documentar APIs** com exemplos de erro

---

## 🆘 Suporte

Se encontrar problemas:

1. Verificar logs estruturados para detalhes
2. Consultar `PROGRESSO_IMPLEMENTACAO.md` para status
3. Revisar `PLANO_MELHORIA_ERRO_QUALIDADE.md` para contexto
4. Verificar testes em `tests/test_exceptions.py` e `tests/test_resilience.py`

---

**Última Atualização:** 2024-01-15
**Versão:** 2.0.0

# Plano de Melhoria: Tratamento de Erros e Qualidade de Código

## 📋 Visão Geral
Este plano aborda sistematicamente a implementação de padrões robustos de tratamento de erros e melhorias de qualidade de código no projeto Resync, seguindo as melhores práticas da indústria.

---

## 🎯 FASE 1: ANÁLISE E PREPARAÇÃO (Dias 1-2)

### 1.1 Auditoria do Código Atual
**Objetivo:** Mapear o estado atual do projeto e identificar pontos críticos

**Tarefas:**
- [ ] Executar análise estática com ferramentas existentes (mypy, ruff, bandit)
- [ ] Identificar funções com alta complexidade ciclomática (> 6)
- [ ] Mapear duplicações de código
- [ ] Listar endpoints de API e seus padrões de resposta de erro
- [ ] Documentar padrões de logging atuais
- [ ] Identificar pontos sem tratamento de exceções

**Ferramentas:**
```bash
# Análise de complexidade
radon cc resync/ -a -nb

# Análise de duplicação
pylint resync/ --disable=all --enable=duplicate-code

# Análise de segurança
bandit -r resync/ -f json -o bandit-report.json

# Análise de tipos
mypy resync/ --strict
```

**Entregáveis:**
- `AUDIT_REPORT.md` - Relatório completo da auditoria
- `COMPLEXITY_HOTSPOTS.md` - Lista de funções complexas
- `DUPLICATION_REPORT.md` - Código duplicado identificado
- `ERROR_HANDLING_GAPS.md` - Lacunas no tratamento de erros

---

## 🔧 FASE 2: PADRONIZAÇÃO DE TRATAMENTO DE ERROS (Dias 3-7)

### 2.1 Criar Hierarquia de Exceções Customizadas
**Objetivo:** Estabelecer uma taxonomia clara de erros

**Tarefas:**
- [ ] Criar módulo `resync/core/exceptions.py`
- [ ] Definir exceções base para diferentes categorias:
  - `BusinessError` - Erros de lógica de negócio
  - `ValidationError` - Erros de validação de dados
  - `IntegrationError` - Erros de integração externa
  - `AuthenticationError` - Erros de autenticação
  - `AuthorizationError` - Erros de autorização
  - `ResourceNotFoundError` - Recursos não encontrados
  - `RateLimitError` - Limite de taxa excedido
  - `CircuitBreakerError` - Circuit breaker aberto

**Estrutura:**
```python
# resync/core/exceptions.py
from typing import Any, Dict, Optional
from enum import Enum

class ErrorCode(str, Enum):
    """Códigos de erro padronizados"""
    # Erros de Cliente (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # Erros de Servidor (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTEGRATION_ERROR = "INTEGRATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

class BaseAppException(Exception):
    """Exceção base para todas as exceções da aplicação"""
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.correlation_id = correlation_id
        super().__init__(self.message)
```

**Entregáveis:**
- `resync/core/exceptions.py` - Hierarquia completa de exceções
- `tests/test_exceptions.py` - Testes unitários

### 2.2 Implementar Sistema de Correlation IDs
**Objetivo:** Rastrear requisições através de múltiplos serviços

**Tarefas:**
- [ ] Criar middleware para gerar/propagar correlation IDs
- [ ] Adicionar correlation ID em todos os logs
- [ ] Incluir correlation ID nas respostas de erro
- [ ] Documentar uso de correlation IDs

**Implementação:**
```python
# resync/api/middleware/correlation_id.py
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get(
            "X-Correlation-ID", 
            str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id
        
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
```

**Entregáveis:**
- `resync/api/middleware/correlation_id.py`
- `resync/core/context.py` - Context manager para correlation ID
- Atualização em `resync/core/logger.py` para incluir correlation ID

### 2.3 Implementar Logging Estruturado
**Objetivo:** Logs em formato JSON para análise automatizada

**Tarefas:**
- [ ] Configurar structlog para logging estruturado
- [ ] Definir campos obrigatórios em todos os logs:
  - `timestamp`
  - `level`
  - `correlation_id`
  - `service_name`
  - `event`
  - `context`
- [ ] Criar helpers para logging consistente
- [ ] Implementar diferentes níveis de log por ambiente

**Estrutura:**
```python
# resync/core/structured_logger.py
import structlog
from typing import Any, Dict

def configure_structured_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

def get_logger(name: str):
    return structlog.get_logger(name)
```

**Entregáveis:**
- `resync/core/structured_logger.py`
- Atualização de todos os módulos para usar logging estruturado
- `docs/LOGGING_GUIDE.md` - Guia de uso

### 2.4 Implementar Padrões de Resiliência
**Objetivo:** Sistema resiliente a falhas

**Tarefas:**
- [ ] Implementar Circuit Breaker para chamadas externas
- [ ] Adicionar Exponential Backoff com Jitter para retries
- [ ] Implementar Timeout configurável
- [ ] Criar decoradores reutilizáveis para resiliência

**Implementação:**
```python
# resync/core/resilience.py
from typing import Callable, TypeVar, Any
from functools import wraps
import asyncio
import random
from pybreaker import CircuitBreaker

T = TypeVar('T')

class ResiliencePatterns:
    """Padrões de resiliência reutilizáveis"""
    
    @staticmethod
    def circuit_breaker(
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        """Decorator para Circuit Breaker"""
        breaker = CircuitBreaker(
            fail_max=failure_threshold,
            reset_timeout=recovery_timeout,
            expected_exception=expected_exception
        )
        
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> T:
                return await breaker.call_async(func, *args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def retry_with_backoff(
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """Decorator para Exponential Backoff com Jitter"""
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> T:
                last_exception = None
                
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        
                        if attempt == max_retries - 1:
                            raise
                        
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        
                        if jitter:
                            delay = delay * (0.5 + random.random() * 0.5)
                        
                        await asyncio.sleep(delay)
                
                raise last_exception
            return wrapper
        return decorator
```

**Entregáveis:**
- `resync/core/resilience.py`
- `tests/test_resilience.py`
- Aplicação em serviços externos (TWS, LLM, etc.)

### 2.5 Implementar Idempotency Keys
**Objetivo:** Operações seguras para retry

**Tarefas:**
- [ ] Criar sistema de idempotency keys
- [ ] Implementar storage para keys (Redis)
- [ ] Adicionar middleware para validação
- [ ] Aplicar em operações críticas (pagamentos, criação de recursos)

**Implementação:**
```python
# resync/core/idempotency.py
from typing import Optional, Any
import hashlib
import json
from datetime import timedelta
from redis.asyncio import Redis

class IdempotencyManager:
    """Gerenciador de chaves de idempotência"""
    
    def __init__(self, redis_client: Redis, ttl: timedelta = timedelta(hours=24)):
        self.redis = redis_client
        self.ttl = int(ttl.total_seconds())
    
    async def get_cached_response(self, idempotency_key: str) -> Optional[Any]:
        """Recupera resposta em cache"""
        cached = await self.redis.get(f"idempotency:{idempotency_key}")
        if cached:
            return json.loads(cached)
        return None
    
    async def cache_response(self, idempotency_key: str, response: Any):
        """Armazena resposta em cache"""
        await self.redis.setex(
            f"idempotency:{idempotency_key}",
            self.ttl,
            json.dumps(response)
        )
```

**Entregáveis:**
- `resync/core/idempotency.py`
- `resync/api/middleware/idempotency.py`
- `tests/test_idempotency.py`

---

## 🌐 FASE 3: MELHORIA DE RESPOSTAS DE ERRO DA API (Dias 8-10)

### 3.1 Padronizar Estrutura de Respostas de Erro
**Objetivo:** Respostas consistentes e informativas

**Tarefas:**
- [ ] Criar modelo Pydantic para respostas de erro
- [ ] Implementar RFC 8292 (Problem Details for HTTP APIs)
- [ ] Criar handler global de exceções
- [ ] Documentar estrutura de erros

**Estrutura:**
```python
# resync/api/models/error_response.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class ErrorDetail(BaseModel):
    """Detalhe específico de um erro"""
    field: Optional[str] = Field(None, description="Campo relacionado ao erro")
    message: str = Field(..., description="Mensagem descritiva do erro")
    code: Optional[str] = Field(None, description="Código específico do erro")

class ErrorResponse(BaseModel):
    """Resposta padronizada de erro (RFC 8292)"""
    type: str = Field(..., description="URI que identifica o tipo de problema")
    title: str = Field(..., description="Resumo curto do problema")
    status: int = Field(..., description="Código de status HTTP")
    detail: str = Field(..., description="Explicação detalhada do problema")
    instance: str = Field(..., description="URI que identifica a ocorrência específica")
    correlation_id: str = Field(..., description="ID de correlação para rastreamento")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    errors: Optional[List[ErrorDetail]] = Field(None, description="Lista de erros específicos")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "https://api.resync.com/errors/validation-error",
                "title": "Validation Error",
                "status": 400,
                "detail": "One or more fields failed validation",
                "instance": "/api/v1/orders/123",
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-15T10:30:00Z",
                "errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format",
                        "code": "INVALID_FORMAT"
                    }
                ]
            }
        }
```

**Entregáveis:**
- `resync/api/models/error_response.py`
- `resync/api/handlers/exception_handlers.py`
- `docs/API_ERROR_RESPONSES.md`

### 3.2 Implementar Mapeamento de Status HTTP Semântico
**Objetivo:** Códigos HTTP corretos para cada tipo de erro

**Tarefas:**
- [ ] Criar mapeamento de exceções para status HTTP
- [ ] Implementar handler específico para cada categoria
- [ ] Adicionar testes para cada tipo de resposta

**Mapeamento:**
```python
# resync/api/handlers/status_mapping.py
from resync.core.exceptions import *

HTTP_STATUS_MAPPING = {
    ValidationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    ResourceNotFoundError: 404,
    RateLimitError: 429,
    BusinessError: 422,
    IntegrationError: 502,
    CircuitBreakerError: 503,
    BaseAppException: 500,
}
```

**Entregáveis:**
- `resync/api/handlers/status_mapping.py`
- Atualização de exception handlers
- `tests/test_api_error_responses.py`

### 3.3 Implementar Sistema de Alertas por Severidade
**Objetivo:** Notificações apropriadas para diferentes níveis de erro

**Tarefas:**
- [ ] Definir níveis de severidade (CRITICAL, ERROR, WARNING, INFO)
- [ ] Configurar canais de notificação (Email, Slack, SMS)
- [ ] Implementar políticas de escalação
- [ ] Criar dashboard de monitoramento

**Implementação:**
```python
# resync/core/alerting.py
from enum import Enum
from typing import Dict, List, Callable
import asyncio

class Severity(str, Enum):
    CRITICAL = "critical"  # Sistema inoperante
    ERROR = "error"        # Funcionalidade comprometida
    WARNING = "warning"    # Problema potencial
    INFO = "info"          # Informação

class AlertChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    PAGERDUTY = "pagerduty"

class AlertManager:
    """Gerenciador de alertas por severidade"""
    
    def __init__(self):
        self.handlers: Dict[Severity, List[Callable]] = {
            Severity.CRITICAL: [],
            Severity.ERROR: [],
            Severity.WARNING: [],
            Severity.INFO: []
        }
    
    def register_handler(self, severity: Severity, handler: Callable):
        """Registra handler para severidade específica"""
        self.handlers[severity].append(handler)
    
    async def alert(
        self,
        severity: Severity,
        title: str,
        message: str,
        context: Dict = None
    ):
        """Envia alerta para handlers registrados"""
        for handler in self.handlers[severity]:
            try:
                await handler(severity, title, message, context)
            except Exception as e:
                # Log erro mas não falha o alerta
                print(f"Alert handler failed: {e}")
```

**Entregáveis:**
- `resync/core/alerting.py`
- `resync/integrations/slack_notifier.py`
- `resync/integrations/email_notifier.py`
- `config/alerting.yaml` - Configuração de alertas

---

## 🔍 FASE 4: REFATORAÇÃO PARA QUALIDADE DE CÓDIGO (Dias 11-16)

### 4.1 Reduzir Complexidade de Funções
**Objetivo:** Complexidade ciclomática < 6

**Tarefas:**
- [ ] Identificar funções com complexidade > 6
- [ ] Aplicar Extract Method para simplificar
- [ ] Aplicar Single Responsibility Principle
- [ ] Criar funções auxiliares privadas
- [ ] Adicionar testes para funções refatoradas

**Processo:**
1. Executar análise: `radon cc resync/ -a -nb | grep -E "^[A-Z]"`
2. Para cada função complexa:
   - Identificar responsabilidades distintas
   - Extrair em métodos menores
   - Nomear claramente cada método
   - Adicionar type hints
   - Documentar com docstrings

**Exemplo de Refatoração:**
```python
# ANTES (Complexidade: 12)
def process_order(order_data: dict):
    if not order_data.get('customer_id'):
        raise ValueError("Customer ID required")
    
    customer = db.get_customer(order_data['customer_id'])
    if not customer:
        raise ValueError("Customer not found")
    
    if customer.status != 'active':
        raise ValueError("Customer not active")
    
    total = 0
    for item in order_data['items']:
        if item['quantity'] <= 0:
            raise ValueError("Invalid quantity")
        product = db.get_product(item['product_id'])
        if not product:
            raise ValueError("Product not found")
        if product.stock < item['quantity']:
            raise ValueError("Insufficient stock")
        total += product.price * item['quantity']
    
    if total > customer.credit_limit:
        raise ValueError("Credit limit exceeded")
    
    order = db.create_order(order_data)
    send_confirmation_email(customer.email, order)
    return order

# DEPOIS (Complexidade: 2-3 por função)
def process_order(order_data: dict) -> Order:
    """Processa um pedido completo"""
    customer = self._validate_and_get_customer(order_data)
    total = self._calculate_and_validate_items(order_data['items'], customer)
    order = self._create_order(order_data)
    self._send_confirmation(customer, order)
    return order

def _validate_and_get_customer(self, order_data: dict) -> Customer:
    """Valida e retorna cliente"""
    customer_id = order_data.get('customer_id')
    if not customer_id:
        raise ValidationError("Customer ID required")
    
    customer = self.db.get_customer(customer_id)
    if not customer:
        raise ResourceNotFoundError("Customer not found")
    
    if customer.status != 'active':
        raise BusinessError("Customer not active")
    
    return customer

def _calculate_and_validate_items(
    self, 
    items: List[dict], 
    customer: Customer
) -> Decimal:
    """Calcula total e valida itens"""
    total = Decimal('0')
    
    for item in items:
        self._validate_item_quantity(item)
        product = self._get_and_validate_product(item)
        total += product.price * item['quantity']
    
    self._validate_credit_limit(total, customer)
    return total
```

**Entregáveis:**
- Funções refatoradas com complexidade < 6
- Testes unitários para cada função
- `REFACTORING_LOG.md` - Log de refatorações

### 4.2 Eliminar Duplicação de Código
**Objetivo:** Aplicar princípio DRY

**Tarefas:**
- [ ] Identificar código duplicado (> 6 linhas)
- [ ] Extrair em funções/classes reutilizáveis
- [ ] Aplicar Template Method ou Strategy Pattern quando apropriado
- [ ] Criar módulo de utilitários comuns

**Processo:**
```bash
# Identificar duplicações
pylint resync/ --disable=all --enable=duplicate-code --min-similarity-lines=6
```

**Estratégias:**
1. **Duplicação Exata:** Extrair para função comum
2. **Duplicação Similar:** Aplicar Template Method Pattern
3. **Duplicação entre Classes:** Considerar herança ou composição

**Exemplo:**
```python
# ANTES - Duplicação
class OrderService:
    async def create_order(self, data):
        logger.info(f"Creating order: {data}")
        try:
            result = await self.db.create(data)
            logger.info(f"Order created: {result.id}")
            return result
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            raise

class ProductService:
    async def create_product(self, data):
        logger.info(f"Creating product: {data}")
        try:
            result = await self.db.create(data)
            logger.info(f"Product created: {result.id}")
            return result
        except Exception as e:
            logger.error(f"Failed to create product: {e}")
            raise

# DEPOIS - DRY com Template Method
class BaseService:
    async def create(self, data: dict):
        """Template method para criação"""
        entity_name = self.get_entity_name()
        logger.info(f"Creating {entity_name}: {data}")
        
        try:
            result = await self._do_create(data)
            logger.info(f"{entity_name} created: {result.id}")
            return result
        except Exception as e:
            logger.error(f"Failed to create {entity_name}: {e}")
            raise
    
    @abstractmethod
    async def _do_create(self, data: dict):
        """Implementação específica da criação"""
        pass
    
    @abstractmethod
    def get_entity_name(self) -> str:
        """Nome da entidade"""
        pass

class OrderService(BaseService):
    async def _do_create(self, data: dict):
        return await self.db.create(data)
    
    def get_entity_name(self) -> str:
        return "order"
```

**Entregáveis:**
- `resync/core/base_service.py` - Classes base reutilizáveis
- `resync/core/utils/common.py` - Utilitários comuns
- Código refatorado sem duplicações

### 4.3 Melhorar Type Annotations
**Objetivo:** Type hints completos e precisos

**Tarefas:**
- [ ] Adicionar type hints em todas as funções
- [ ] Usar tipos genéricos apropriadamente (List, Dict, Optional, Union)
- [ ] Criar tipos customizados com TypedDict e NewType
- [ ] Configurar mypy em modo strict
- [ ] Corrigir todos os erros de tipo

**Configuração mypy:**
```ini
# mypy.ini
[mypy]
python_version = 3.12
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_any_unimported = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
check_untyped_defs = True
strict_equality = True
```

**Exemplo:**
```python
# ANTES
def process_data(data, options=None):
    if options is None:
        options = {}
    result = []
    for item in data:
        if item.get('active'):
            result.append(transform(item, options))
    return result

# DEPOIS
from typing import List, Dict, Any, Optional, TypedDict

class ProcessOptions(TypedDict, total=False):
    """Opções de processamento"""
    include_metadata: bool
    format: str
    filters: List[str]

class DataItem(TypedDict):
    """Item de dados"""
    id: str
    active: bool
    value: Any

def process_data(
    data: List[DataItem],
    options: Optional[ProcessOptions] = None
) -> List[Dict[str, Any]]:
    """
    Processa lista de dados com opções configuráveis.
    
    Args:
        data: Lista de itens para processar
        options: Opções de processamento (opcional)
    
    Returns:
        Lista de dados processados
    """
    if options is None:
        options = {}
    
    result: List[Dict[str, Any]] = []
    for item in data:
        if item.get('active', False):
            result.append(transform(item, options))
    
    return result
```

**Entregáveis:**
- Type hints em 100% das funções públicas
- Tipos customizados em `resync/core/types.py`
- Mypy passando sem erros em modo strict

### 4.4 Melhorar Nomenclatura
**Objetivo:** Nomes claros e consistentes

**Tarefas:**
- [ ] Revisar nomes de variáveis, funções e classes
- [ ] Aplicar convenções PEP 8
- [ ] Usar nomes descritivos (evitar abreviações)
- [ ] Padronizar prefixos/sufixos
- [ ] Configurar linter para enforçar convenções

**Convenções:**
```python
# Classes: PascalCase
class OrderProcessor:
    pass

# Funções/Métodos: snake_case
def calculate_total_price():
    pass

# Constantes: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3

# Variáveis privadas: _prefixo
class MyClass:
    def __init__(self):
        self._internal_state = {}

# Booleanos: is_, has_, can_, should_
is_valid = True
has_permission = False
can_process = True
should_retry = False

# Coleções: plural
orders = []
customers = {}
products = set()

# Funções que retornam bool: is_, has_, can_
def is_valid_email(email: str) -> bool:
    pass

def has_permission(user: User, resource: str) -> bool:
    pass
```

**Entregáveis:**
- Código com nomenclatura padronizada
- `NAMING_CONVENTIONS.md` - Guia de nomenclatura
- Configuração de linter atualizada

### 4.5 Melhorar Dependency Injection
**Objetivo:** Acoplamento fraco e testabilidade

**Tarefas:**
- [ ] Revisar container de DI atual
- [ ] Aplicar inversão de dependências (SOLID)
- [ ] Criar interfaces claras
- [ ] Usar injeção por construtor
- [ ] Facilitar mocking em testes

**Estrutura:**
```python
# resync/core/interfaces.py
from abc import ABC, abstractmethod
from typing import Protocol

class IOrderRepository(Protocol):
    """Interface para repositório de pedidos"""
    async def create(self, order: Order) -> Order:
        ...
    
    async def get_by_id(self, order_id: str) -> Optional[Order]:
        ...
    
    async def update(self, order: Order) -> Order:
        ...

class INotificationService(Protocol):
    """Interface para serviço de notificações"""
    async def send_email(self, to: str, subject: str, body: str) -> None:
        ...
    
    async def send_sms(self, to: str, message: str) -> None:
        ...

# resync/services/order_service.py
class OrderService:
    """Serviço de pedidos com DI"""
    
    def __init__(
        self,
        repository: IOrderRepository,
        notification_service: INotificationService,
        logger: structlog.BoundLogger
    ):
        self._repository = repository
        self._notification = notification_service
        self._logger = logger
    
    async def create_order(self, data: OrderCreate) -> Order:
        """Cria novo pedido"""
        self._logger.info("creating_order", data=data)
        
        order = await self._repository.create(Order(**data.dict()))
        
        await self._notification.send_email(
            to=order.customer_email,
            subject="Order Confirmation",
            body=f"Your order {order.id} has been created"
        )
        
        return order

# resync/core/container.py
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    """Container de DI"""
    
    config = providers.Configuration()
    
    # Repositories
    order_repository = providers.Singleton(
        OrderRepository,
        db=providers.Dependency()
    )
    
    # Services
    notification_service = providers.Singleton(
        NotificationService,
        config=config.notifications
    )
    
    order_service = providers.Factory(
        OrderService,
        repository=order_repository,
        notification_service=notification_service,
        logger=providers.Dependency()
    )
```

**Entregáveis:**
- Interfaces em `resync/core/interfaces.py`
- Container de DI atualizado
- Serviços refatorados com DI
- `docs/DEPENDENCY_INJECTION.md`

---

## 📊 FASE 5: TESTES E VALIDAÇÃO (Dias 17-19)

### 5.1 Testes de Tratamento de Erros
**Objetivo:** Garantir comportamento correto em cenários de erro

**Tarefas:**
- [ ] Testes unitários para cada tipo de exceção
- [ ] Testes de integração para fluxos de erro
- [ ] Testes de resiliência (circuit breaker, retry)
- [ ] Testes de idempotência
- [ ] Testes de correlation ID

**Estrutura:**
```python
# tests/test_error_handling.py
import pytest
from resync.core.exceptions import *
from resync.api.models.error_response import ErrorResponse

class TestExceptionHandling:
    """Testes de tratamento de exceções"""
    
    async def test_validation_error_returns_400(self, client):
        """Erro de validação retorna 400"""
        response = await client.post("/api/orders", json={"invalid": "data"})
        assert response.status_code == 400
        
        error = ErrorResponse(**response.json())
        assert error.type.endswith("validation-error")
        assert error.correlation_id is not None
    
    async def test_resource_not_found_returns_404(self, client):
        """Recurso não encontrado retorna 404"""
        response = await client.get("/api/orders/nonexistent")
        assert response.status_code == 404
        
        error = ErrorResponse(**response.json())
        assert error.type.endswith("not-found")
    
    async def test_correlation_id_propagation(self, client):
        """Correlation ID é propagado"""
        correlation_id = "test-correlation-id"
        response = await client.get(
            "/api/orders",
            headers={"X-Correlation-ID": correlation_id}
        )
        
        assert response.headers["X-Correlation-ID"] == correlation_id

class TestResiliencePatterns:
    """Testes de padrões de resiliência"""
    
    async def test_circuit_breaker_opens_after_failures(self):
        """Circuit breaker abre após falhas"""
        # Implementar teste
        pass
    
    async def test_retry_with_exponential_backoff(self):
        """Retry com backoff exponencial"""
        # Implementar teste
        pass
```

**Entregáveis:**
- Suite completa de testes de erro
- Cobertura > 90% em módulos de erro
- `tests/test_error_handling.py`
- `tests/test_resilience.py`
- `tests/test_idempotency.py`

### 5.2 Testes de Qualidade de Código
**Objetivo:** Validar melhorias de qualidade

**Tarefas:**
- [ ] Verificar complexidade ciclomática < 6
- [ ] Verificar ausência de duplicação
- [ ] Validar type hints com mypy
- [ ] Executar análise de segurança
- [ ] Gerar relatório de qualidade

**Scripts:**
```bash
# scripts/quality_check.sh
#!/bin/bash

echo "=== Verificando Complexidade ==="
radon cc resync/ -a -nb --total-average

echo "=== Verificando Duplicação ==="
pylint resync/ --disable=all --enable=duplicate-code

echo "=== Verificando Tipos ==="
mypy resync/ --strict

echo "=== Verificando Segurança ==="
bandit -r resync/ -f screen

echo "=== Verificando Estilo ==="
ruff check resync/

echo "=== Executando Testes ==="
pytest tests/ --cov=resync --cov-report=html --cov-report=term
```

**Entregáveis:**
- Script de verificação de qualidade
- Relatório de qualidade
- Métricas de melhoria (antes/depois)

### 5.3 Testes de Carga e Stress
**Objetivo:** Validar comportamento sob carga

**Tarefas:**
- [ ] Testes de carga com Locust
- [ ] Testes de stress (circuit breaker)
- [ ] Testes de rate limiting
- [ ] Monitorar uso de recursos

**Cenários:**
```python
# tests/load/test_error_handling_load.py
from locust import HttpUser, task, between

class ErrorHandlingLoadTest(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def test_successful_request(self):
        """Requisição bem-sucedida"""
        self.client.get("/api/orders")
    
    @task(1)
    def test_error_request(self):
        """Requisição com erro"""
        response = self.client.get("/api/orders/invalid")
        assert response.status_code == 404
        assert "correlation_id" in response.json()
    
    @task(1)
    def test_rate_limit(self):
        """Teste de rate limit"""
        for _ in range(100):
            response = self.client.get("/api/orders")
            if response.status_code == 429:
                break
```

**Entregáveis:**
- Testes de carga
- Relatório de performance
- Métricas de resiliência

---

## 📚 FASE 6: DOCUMENTAÇÃO (Dias 20-21)

### 6.1 Documentação Técnica
**Objetivo:** Documentar todas as implementações

**Tarefas:**
- [ ] Documentar hierarquia de exceções
- [ ] Documentar padrões de resiliência
- [ ] Documentar estrutura de erros da API
- [ ] Documentar sistema de alertas
- [ ] Criar guias de uso

**Documentos:**
1. `docs/ERROR_HANDLING_GUIDE.md` - Guia completo de tratamento de erros
2. `docs/API_ERROR_RESPONSES.md` - Referência de erros da API
3. `docs/RESILIENCE_PATTERNS.md` - Padrões de resiliência
4. `docs/LOGGING_GUIDE.md` - Guia de logging
5. `docs/CODE_QUALITY_STANDARDS.md` - Padrões de qualidade

**Estrutura:**
```markdown
# Guia de Tratamento de Erros

## Visão Geral
Este guia descreve os padrões de tratamento de erros...

## Hierarquia de Exceções
### BaseAppException
Exceção base para todas as exceções da aplicação.

**Uso:**
```python
raise BaseAppException(
    message="Erro ao processar pedido",
    error_code=ErrorCode.INTERNAL_ERROR,
    status_code=500,
    details={"order_id": "123"},
    correlation_id=request.state.correlation_id
)
```

## Padrões de Resiliência
### Circuit Breaker
...
```

**Entregáveis:**
- Documentação completa em `docs/`
- README atualizado
- Exemplos de código
- Diagramas de fluxo

### 6.2 Documentação da API
**Objetivo:** OpenAPI/Swagger atualizado

**Tarefas:**
- [ ] Atualizar schemas de erro no OpenAPI
- [ ] Adicionar exemplos de respostas de erro
- [ ] Documentar headers (X-Correlation-ID)
- [ ] Documentar códigos de status

**Implementação:**
```python
# resync/api/endpoints.py
from fastapi import APIRouter, HTTPException
from resync.api.models.error_response import ErrorResponse

router = APIRouter()

@router.get(
    "/orders/{order_id}",
    response_model=Order,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Order not found",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://api.resync.com/errors/not-found",
                        "title": "Resource Not Found",
                        "status": 404,
                        "detail": "Order with ID '123' not found",
                        "instance": "/api/orders/123",
                        "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error"
        }
    }
)
async def get_order(order_id: str):
    """Recupera pedido por ID"""
    pass
```

**Entregáveis:**
- OpenAPI spec atualizado
- Swagger UI com exemplos
- Postman collection atualizada

---

## 🚀 FASE 7: DEPLOY E MONITORAMENTO (Dias 22-23)

### 7.1 Configuração de Monitoramento
**Objetivo:** Observabilidade completa

**Tarefas:**
- [ ] Configurar agregação de logs (ELK/Loki)
- [ ] Configurar métricas (Prometheus)
- [ ] Criar dashboards (Grafana)
- [ ] Configurar alertas
- [ ] Implementar tracing distribuído (Jaeger/Zipkin)

**Métricas:**
```python
# resync/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Contadores de erro
error_counter = Counter(
    'api_errors_total',
    'Total de erros da API',
    ['error_code', 'endpoint', 'method']
)

# Histograma de latência
request_duration = Histogram(
    'api_request_duration_seconds',
    'Duração das requisições',
    ['endpoint', 'method', 'status']
)

# Gauge de circuit breakers
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Estado do circuit breaker (0=closed, 1=open, 2=half-open)',
    ['service']
)
```

**Entregáveis:**
- Configuração de logging centralizado
- Dashboards de monitoramento
- Alertas configurados
- `docs/MONITORING_GUIDE.md`

### 7.2 Deploy Gradual
**Objetivo:** Deploy seguro das mudanças

**Tarefas:**
- [ ] Criar feature flags para novas funcionalidades
- [ ] Implementar canary deployment
- [ ] Configurar rollback automático
- [ ] Monitorar métricas pós-deploy

**Estratégia:**
1. **Fase 1 (10%):** Deploy para 10% do tráfego
2. **Fase 2 (50%):** Se métricas OK, aumentar para 50%
3. **Fase 3 (100%):** Deploy completo

**Entregáveis:**
- Pipeline de CI/CD atualizado
- Feature flags configurados
- Plano de rollback
- `docs/DEPLOYMENT_GUIDE.md`

---

## 📈 FASE 8: REVISÃO E OTIMIZAÇÃO (Dias 24-25)

### 8.1 Revisão de Código
**Objetivo:** Garantir qualidade das implementações

**Tarefas:**
- [ ] Code review de todas as mudanças
- [ ] Validar aderência aos padrões
- [ ] Verificar cobertura de testes
- [ ] Revisar documentação

**Checklist:**
- [ ] Todas as exceções têm tratamento adequado
- [ ] Todos os endpoints retornam erros padronizados
- [ ] Correlation IDs estão presentes
- [ ] Logging estruturado implementado
- [ ] Padrões de resiliência aplicados
- [ ] Complexidade ciclomática < 6
- [ ] Sem duplicação de código
- [ ] Type hints completos
- [ ] Nomenclatura consistente
- [ ] DI implementado corretamente
- [ ] Testes com cobertura > 90%
- [ ] Documentação completa

**Entregáveis:**
- Relatório de code review
- Lista de ajustes necessários
- Aprovação final

### 8.2 Otimização de Performance
**Objetivo:** Garantir que melhorias não impactaram performance

**Tarefas:**
- [ ] Executar benchmarks
- [ ] Comparar com baseline
- [ ] Otimizar pontos críticos
- [ ] Validar uso de recursos

**Métricas:**
- Latência P50, P95, P99
- Throughput (req/s)
- Taxa de erro
- Uso de CPU/Memória
- Tempo de resposta de erros

**Entregáveis:**
- Relatório de performance
- Comparativo antes/depois
- Otimizações aplicadas

### 8.3 Treinamento da Equipe
**Objetivo:** Capacitar equipe nos novos padrões

**Tarefas:**
- [ ] Criar material de treinamento
- [ ] Realizar sessões de treinamento
- [ ] Criar guia de referência rápida
- [ ] Estabelecer processo de code review

**Tópicos:**
1. Hierarquia de exceções e quando usar cada uma
2. Como implementar padrões de resiliência
3. Estrutura de respostas de erro da API
4. Sistema de logging estruturado
5. Boas práticas de qualidade de código
6. Uso do sistema de DI

**Entregáveis:**
- Material de treinamento
- Guia de referência rápida
- Gravação das sessões
- Quiz de validação

---

## 📊 MÉTRICAS DE SUCESSO

### Métricas Quantitativas
- [ ] **Cobertura de Testes:** > 90%
- [ ] **Complexidade Ciclomática:** < 6 em todas as funções
- [ ] **Duplicação de Código:** < 3%
- [ ] **Type Coverage:** 100% em código público
- [ ] **Taxa de Erro:** Redução de 50%
- [ ] **MTTR (Mean Time To Recovery):** Redução de 40%
- [ ] **Tempo de Resposta de Erros:** < 100ms
- [ ] **Alertas Falsos Positivos:** < 5%

### Métricas Qualitativas
- [ ] Todos os erros têm correlation ID
- [ ] Logs estruturados em JSON
- [ ] Respostas de erro seguem RFC 8292
- [ ] Circuit breakers implementados em integrações externas
- [ ] Idempotência em operações críticas
- [ ] Documentação completa e atualizada
- [ ] Equipe treinada nos novos padrões

---

## 🛠️ FERRAMENTAS E TECNOLOGIAS

### Análise de Código
- **radon:** Complexidade ciclomática
- **pylint:** Duplicação e qualidade
- **mypy:** Verificação de tipos
- **bandit:** Análise de segurança
- **ruff:** Linting rápido
- **black:** Formatação

### Testes
- **pytest:** Framework de testes
- **pytest-asyncio:** Testes assíncronos
- **pytest-cov:** Cobertura de código
- **locust:** Testes de carga
- **mutmut:** Mutation testing

### Monitoramento
- **structlog:** Logging estruturado
- **prometheus-client:** Métricas
- **opentelemetry:** Tracing distribuído

### Resiliência
- **pybreaker:** Circuit breaker
- **tenacity:** Retry com backoff
- **redis:** Cache e idempotency keys

---

## 📅 CRONOGRAMA RESUMIDO

| Fase | Duração | Dias | Entregáveis Principais |
|------|---------|------|------------------------|
| 1. Análise e Preparação | 2 dias | 1-2 | Relatórios de auditoria |
| 2. Tratamento de Erros | 5 dias | 3-7 | Sistema de exceções, logging, resiliência |
| 3. Respostas de API | 3 dias | 8-10 | Respostas padronizadas, alertas |
| 4. Qualidade de Código | 6 dias | 11-16 | Código refatorado, DI melhorado |
| 5. Testes e Validação | 3 dias | 17-19 | Suite de testes completa |
| 6. Documentação | 2 dias | 20-21 | Documentação técnica e API |
| 7. Deploy e Monitoramento | 2 dias | 22-23 | Sistema em produção monitorado |
| 8. Revisão e Otimização | 2 dias | 24-25 | Revisão final, treinamento |

**Total:** 25 dias úteis (~5 semanas)

---

## 🎯 PRÓXIMOS PASSOS

1. **Revisar e aprovar este plano** com stakeholders
2. **Alocar recursos** (desenvolvedores, DevOps, QA)
3. **Configurar ambiente** de desenvolvimento e staging
4. **Iniciar Fase 1** - Análise e Preparação
5. **Estabelecer rituais** de acompanhamento (daily, review semanal)

---

## 📝 NOTAS IMPORTANTES

- Este plano é iterativo e pode ser ajustado conforme necessário
- Priorize qualidade sobre velocidade
- Mantenha comunicação constante com a equipe
- Documente decisões e aprendizados
- Celebre conquistas incrementais

---

## 🔗 REFERÊNCIAS

1. Gartner - Digital Transformation Failures
2. RFC 8292 - Problem Details for HTTP APIs
3. Martin Fowler - Refactoring
4. SOLID Principles
5. Clean Code - Robert C. Martin
6. Release It! - Michael T. Nygard (Circuit Breaker, Resilience)
7. Site Reliability Engineering - Google
8. Stripe API Documentation
9. Twitter API Error Handling
10. Microsoft REST API Guidelines

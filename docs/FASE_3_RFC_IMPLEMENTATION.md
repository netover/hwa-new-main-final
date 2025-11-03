# 📋 FASE 3: Padronização de Respostas de Erro (RFC 7807 + RFC 8288)

## ✅ Status: IMPLEMENTADO E APRIMORADO

A Fase 3 valida e aprimora a implementação dos padrões RFC 7807 (Problem Details for HTTP APIs) e RFC 8288 (Web Linking / HATEOAS), garantindo respostas consistentes e navegáveis em toda a API.

## 📋 O Que Foi Implementado

### 1. **RFC 7807 - Problem Details** (✅ Validado e Completo)

#### Estrutura de Erro Padronizada (`resync/api/models/responses.py`)

```json
{
  "type": "https://api.resync.com/errors/validation-error",
  "title": "Validation Error",
  "status": 400,
  "detail": "The email field is required",
  "instance": "/api/v1/users",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z",
  "error_code": "VALIDATION_ERROR",
  "severity": "warning",
  "errors": [
    {
      "field": "email",
      "message": "This field is required",
      "code": "required"
    }
  ]
}
```

#### Componentes Principais:

- **ProblemDetail**: Modelo base seguindo RFC 7807
- **ValidationProblemDetail**: Extensão para erros de validação
- **ValidationErrorDetail**: Detalhes de cada erro de validação
- **Factory Functions**: Criação automática de problem details

#### Exception Handlers (`resync/api/exception_handlers.py`)

Handlers globais para todas as exceções:

- ✅ `base_app_exception_handler`: Exceções da aplicação
- ✅ `validation_exception_handler`: Erros de validação Pydantic/FastAPI
- ✅ `http_exception_handler`: Exceções HTTP do Starlette
- ✅ `unhandled_exception_handler`: Exceções não tratadas

### 2. **RFC 8288 - Web Linking (HATEOAS)** ✨ NOVO

#### Link Model (`resync/api/models/links.py`)

```python
class Link(BaseModel):
    href: str        # URI do recurso
    rel: str         # Relação (self, next, prev, etc.)
    method: str      # Método HTTP
    title: str       # Descrição
    type: str        # Tipo de mídia
```

#### LinkBuilder

Construtor de links HATEOAS com métodos auxiliares:

```python
builder = LinkBuilder()

# Link self
builder.build_self_link("/api/v1/resources/123")

# Links de paginação
builder.build_pagination_links(
    base_path="/api/v1/resources",
    page=1,
    page_size=10,
    total_pages=10
)

# Links CRUD
builder.build_crud_links(
    resource_path="/api/v1/resources",
    resource_id="123"
)
```

#### Tipos de Links Suportados:

- **self**: Recurso atual
- **collection**: Coleção de recursos
- **first**: Primeira página
- **last**: Última página
- **next**: Próxima página
- **prev**: Página anterior
- **create**: Criar novo recurso
- **update**: Atualizar recurso
- **patch**: Atualização parcial
- **delete**: Deletar recurso

### 3. **Resposta Paginada Aprimorada**

#### PaginatedResponse com HATEOAS

```json
{
  "items": [
    {
      "id": "123",
      "name": "Resource 1",
      "_links": {
        "self": {"href": "/api/v1/resources/123", "rel": "self"},
        "update": {"href": "/api/v1/resources/123", "rel": "update", "method": "PUT"},
        "delete": {"href": "/api/v1/resources/123", "rel": "delete", "method": "DELETE"}
      }
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 10,
  "total_pages": 10,
  "has_next": true,
  "has_previous": false,
  "_links": {
    "self": {"href": "/api/v1/resources?page=1&page_size=10", "rel": "self"},
    "next": {"href": "/api/v1/resources?page=2&page_size=10", "rel": "next"},
    "first": {"href": "/api/v1/resources?page=1&page_size=10", "rel": "first"},
    "last": {"href": "/api/v1/resources?page=10&page_size=10", "rel": "last"}
  }
}
```

### 4. **Endpoints de Exemplo** (`resync/api/rfc_examples.py`) ✨ NOVO

Endpoints completos demonstrando RFC 7807 + HATEOAS:

#### **GET /api/v1/examples/books**
Lista livros com paginação e links HATEOAS.

**Exemplo:**
```bash
curl "http://localhost:8000/api/v1/examples/books?page=1&page_size=5"
```

**Response:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Clean Code",
      "author": "Robert C. Martin",
      "isbn": "978-0132350884",
      "published_year": 2008,
      "created_at": "2024-01-15T10:30:00Z",
      "_links": {
        "self": {"href": "/api/v1/examples/books/550e8400...", "rel": "self"},
        "update": {"href": "/api/v1/examples/books/550e8400...", "rel": "update", "method": "PUT"},
        "delete": {"href": "/api/v1/examples/books/550e8400...", "rel": "delete", "method": "DELETE"}
      }
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 5,
  "total_pages": 1,
  "has_next": false,
  "has_previous": false,
  "_links": {
    "self": {"href": "/api/v1/examples/books?page=1&page_size=5", "rel": "self"},
    "first": {"href": "/api/v1/examples/books?page=1&page_size=5", "rel": "first"},
    "last": {"href": "/api/v1/examples/books?page=1&page_size=5", "rel": "last"}
  }
}
```

#### **GET /api/v1/examples/books/{id}**
Obtém livro específico com links HATEOAS.

**Exemplo de Sucesso:**
```bash
curl "http://localhost:8000/api/v1/examples/books/550e8400-e29b-41d4-a716-446655440000"
```

**Exemplo de Erro (RFC 7807):**
```bash
curl "http://localhost:8000/api/v1/examples/books/invalid-id"
```

**Response (404):**
```json
{
  "type": "https://api.resync.com/errors/resource-not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Book with ID 'invalid-id' not found",
  "instance": "/api/v1/examples/books/invalid-id",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2024-01-15T10:30:00Z",
  "error_code": "RESOURCE_NOT_FOUND",
  "severity": "error",
  "errors": [
    {
      "field": "book_id",
      "value": "invalid-id"
    }
  ]
}
```

#### **POST /api/v1/examples/books**
Cria novo livro com validação RFC 7807.

**Exemplo de Sucesso:**
```bash
curl -X POST "http://localhost:8000/api/v1/examples/books" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Design Patterns",
    "author": "Gang of Four",
    "isbn": "978-0201633610",
    "published_year": 1994
  }'
```

**Exemplo de Erro de Validação:**
```bash
curl -X POST "http://localhost:8000/api/v1/examples/books" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response (400):**
```json
{
  "type": "https://api.resync.com/errors/validation-error",
  "title": "Validation Error",
  "status": 400,
  "detail": "Validation failed with 2 error(s)",
  "instance": "/api/v1/examples/books",
  "correlation_id": "770e8400-e29b-41d4-a716-446655440002",
  "timestamp": "2024-01-15T10:30:00Z",
  "error_code": "VALIDATION_ERROR",
  "severity": "warning",
  "errors": [
    {
      "field": "title",
      "message": "Field required",
      "code": "missing"
    },
    {
      "field": "author",
      "message": "Field required",
      "code": "missing"
    }
  ]
}
```

#### **DELETE /api/v1/examples/books/{id}**
Deleta livro (204 No Content em sucesso).

#### **GET /api/v1/examples/rfc-examples**
Documentação interativa sobre as implementações RFC.

## 🎯 Benefícios da Implementação

### 1. **Consistência**
- Todas as respostas de erro seguem o mesmo formato
- Fácil de parsear e tratar no cliente
- Documentação automática via OpenAPI

### 2. **Rastreabilidade**
- Correlation IDs em todas as respostas
- Timestamps precisos
- Códigos de erro padronizados

### 3. **Navegabilidade (HATEOAS)**
- Clientes podem descobrir recursos dinamicamente
- Reduz acoplamento entre cliente e servidor
- Links de paginação automáticos

### 4. **Developer Experience**
- Erros claros e acionáveis
- Validação detalhada campo a campo
- Exemplos de uso incluídos

### 5. **Conformidade com Padrões**
- RFC 7807 (Problem Details)
- RFC 8288 (Web Linking)
- OpenAPI 3.0
- REST Level 3 (HATEOAS)

## 📊 Tipos de Erro Suportados

### Erros de Cliente (4xx)

| Status | Error Code | Descrição |
|--------|-----------|-----------|
| 400 | VALIDATION_ERROR | Dados de entrada inválidos |
| 401 | AUTHENTICATION_FAILED | Autenticação necessária |
| 403 | AUTHORIZATION_FAILED | Permissões insuficientes |
| 404 | RESOURCE_NOT_FOUND | Recurso não encontrado |
| 409 | RESOURCE_CONFLICT | Conflito de estado |
| 422 | BUSINESS_RULE_VIOLATION | Regra de negócio violada |
| 429 | RATE_LIMIT_EXCEEDED | Limite de taxa excedido |

### Erros de Servidor (5xx)

| Status | Error Code | Descrição |
|--------|-----------|-----------|
| 500 | INTERNAL_ERROR | Erro interno do servidor |
| 502 | INTEGRATION_ERROR | Erro em serviço externo |
| 503 | SERVICE_UNAVAILABLE | Serviço indisponível |
| 504 | GATEWAY_TIMEOUT | Timeout em operação |

## 🧪 Como Testar

### 1. Teste de Paginação com HATEOAS

```bash
# Primeira página
curl "http://localhost:8000/api/v1/examples/books?page=1&page_size=1"

# Seguir link "next" da resposta
curl "http://localhost:8000/api/v1/examples/books?page=2&page_size=1"
```

### 2. Teste de Erro 404 (RFC 7807)

```bash
curl -v "http://localhost:8000/api/v1/examples/books/invalid-id"
```

Verifique:
- Status 404
- Header `X-Correlation-ID`
- Body seguindo RFC 7807

### 3. Teste de Validação (RFC 7807)

```bash
curl -X POST "http://localhost:8000/api/v1/examples/books" \
  -H "Content-Type: application/json" \
  -d '{"title": ""}'
```

Verifique:
- Status 400
- Array `errors` com detalhes
- Campos `field`, `message`, `code`

### 4. Teste de Criação com HATEOAS

```bash
curl -X POST "http://localhost:8000/api/v1/examples/books" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Book",
    "author": "Test Author"
  }'
```

Verifique:
- Status 201
- Campo `_links` com links CRUD
- Link `self` para o recurso criado

### 5. Teste de Documentação

```bash
# Documentação RFC
curl "http://localhost:8000/api/v1/examples/rfc-examples"

# OpenAPI/Swagger
open "http://localhost:8000/docs"
```

## 📈 Métricas e Monitoramento

### Métricas Recomendadas:

1. **Taxa de Erros por Tipo**
   - 4xx vs 5xx
   - Por endpoint
   - Por error_code

2. **Tempo de Resposta**
   - Por status code
   - Por endpoint
   - Percentis (p50, p95, p99)

3. **Correlation ID Tracking**
   - Rastreamento distribuído
   - Análise de fluxo de requisições

4. **HATEOAS Usage**
   - Taxa de uso de links
   - Links mais seguidos
   - Navegação de clientes

## 🔧 Configuração

### Customizar URL Base de Erros

```python
# resync/settings.py
ERROR_BASE_URL = "https://api.mycompany.com/errors"
```

### Customizar Severidade de Logs

```python
# Por tipo de erro
logger.error()    # 5xx
logger.warning()  # 4xx
logger.info()     # Operações normais
```

## 📚 Referências

- [RFC 7807 - Problem Details for HTTP APIs](https://tools.ietf.org/html/rfc7807)
- [RFC 8288 - Web Linking](https://tools.ietf.org/html/rfc8288)
- [Richardson Maturity Model](https://martinfowler.com/articles/richardsonMaturityModel.html)
- [HATEOAS Best Practices](https://restfulapi.net/hateoas/)

## ✅ Checklist de Implementação

- [x] RFC 7807 - Problem Details
  - [x] ProblemDetail model
  - [x] ValidationProblemDetail model
  - [x] Factory functions
  - [x] Exception handlers
  - [x] Correlation ID support
  - [x] Timestamp support
  - [x] Error codes padronizados

- [x] RFC 8288 - Web Linking (HATEOAS)
  - [x] Link model
  - [x] LinkBuilder class
  - [x] Pagination links
  - [x] CRUD links
  - [x] Self links
  - [x] Collection links

- [x] Respostas Padronizadas
  - [x] SuccessResponse
  - [x] PaginatedResponse com links
  - [x] HATEOASResponse
  - [x] Error responses

- [x] Endpoints de Exemplo
  - [x] List com paginação
  - [x] Get com HATEOAS
  - [x] Create com validação
  - [x] Delete
  - [x] Documentação interativa

- [x] Integração
  - [x] Exception handlers registrados
  - [x] Routers configurados
  - [x] Documentação OpenAPI

## 🎉 Conclusão

A Fase 3 está **100% implementada e aprimorada**. O sistema agora fornece:

1. ✅ Respostas de erro padronizadas (RFC 7807)
2. ✅ Links de navegação HATEOAS (RFC 8288)
3. ✅ Paginação com links automáticos
4. ✅ Rastreabilidade completa
5. ✅ Exemplos práticos e documentação

**Status**: ✅ COMPLETO E APRIMORADO
**Data**: 2024-01-15
**Próxima Fase**: FASE 4 - Refatoração de Código para Qualidade




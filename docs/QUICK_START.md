# 🚀 Guia Rápido de Início - Projeto Resync

## 📋 Pré-requisitos

- Python 3.13+
- Redis (opcional, usa in-memory se não disponível)
- Git

## ⚡ Início Rápido (5 minutos)

### 1. Clone e Setup

```bash
# Clone o repositório
git clone <repository-url>
cd resync

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt
```

### 2. Configure (Opcional)

```bash
# Copie arquivo de configuração de exemplo
cp .env.example .env

# Edite conforme necessário
nano .env
```

**Configurações Mínimas**:
```env
PROJECT_NAME=Resync
DEBUG=True
LOG_LEVEL=INFO
```

### 3. Inicie o Servidor

```bash
# Desenvolvimento
uvicorn resync.main:app --reload --port 8000

# Ou use o script
python -m resync.main
```

### 4. Acesse a Documentação

```bash
# Swagger UI (interativo)
open http://localhost:8000/docs

# ReDoc (documentação)
open http://localhost:8000/redoc
```

## 🎯 Testando as Novas Funcionalidades

### Teste 1: Idempotency Keys (30 segundos)

```bash
# Gere uma idempotency key
IDEM_KEY=$(uuidgen)  # Linux/Mac
# ou
IDEM_KEY=$(powershell -Command "[guid]::NewGuid().ToString()")  # Windows

# Crie um recurso
curl -X POST "http://localhost:8000/api/v1/operations/resources" \
  -H "X-Idempotency-Key: $IDEM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Resource",
    "description": "Testing idempotency"
  }'

# Repita a mesma requisição (deve retornar o mesmo resultado)
curl -X POST "http://localhost:8000/api/v1/operations/resources" \
  -H "X-Idempotency-Key: $IDEM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Resource",
    "description": "Testing idempotency"
  }'
```

**Resultado Esperado**: Ambas as requisições retornam o mesmo recurso (mesmo ID).

---

### Teste 2: RFC 7807 - Error Handling (30 segundos)

```bash
# Teste erro 404
curl -v "http://localhost:8000/api/v1/examples/books/invalid-id"

# Teste erro de validação
curl -X POST "http://localhost:8000/api/v1/examples/books" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Resultado Esperado**: 
- Erro 404 com formato RFC 7807
- Erro 400 com lista de campos inválidos

---

### Teste 3: HATEOAS - Navegação (1 minuto)

```bash
# Liste livros com paginação
curl "http://localhost:8000/api/v1/examples/books?page=1&page_size=1"

# Observe o campo "_links" na resposta
# Copie o href do link "next" (se existir)
# Faça nova requisição com esse link

# Exemplo:
curl "http://localhost:8000/api/v1/examples/books?page=2&page_size=1"
```

**Resultado Esperado**: 
- Resposta com campo `_links`
- Links para `self`, `first`, `last`, `next`, `prev`
- Cada item tem seus próprios links

---

### Teste 4: Criar e Navegar (2 minutos)

```bash
# 1. Crie um livro
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/examples/books" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Book",
    "author": "John Doe",
    "published_year": 2024
  }')

echo $RESPONSE | jq .

# 2. Extraia o ID do livro
BOOK_ID=$(echo $RESPONSE | jq -r '.id')

# 3. Busque o livro criado
curl "http://localhost:8000/api/v1/examples/books/$BOOK_ID"

# 4. Delete o livro
curl -X DELETE "http://localhost:8000/api/v1/examples/books/$BOOK_ID"

# 5. Tente buscar novamente (deve retornar 404)
curl -v "http://localhost:8000/api/v1/examples/books/$BOOK_ID"
```

---

## 📚 Endpoints Disponíveis

### Idempotency Examples

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/v1/operations/resources` | Criar recurso (requer X-Idempotency-Key) |
| POST | `/api/v1/operations/transactions` | Criar transação (requer X-Idempotency-Key) |
| GET | `/api/v1/operations/idempotency-example` | Documentação de idempotency |

### RFC Examples (HATEOAS)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/v1/examples/books` | Listar livros (paginado) |
| GET | `/api/v1/examples/books/{id}` | Obter livro específico |
| POST | `/api/v1/examples/books` | Criar novo livro |
| DELETE | `/api/v1/examples/books/{id}` | Deletar livro |
| GET | `/api/v1/examples/rfc-examples` | Documentação RFC |

### Health & Monitoring

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/health` | Health check |
| GET | `/api/health/detailed` | Health detalhado |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |

---

## 🔧 Desenvolvimento

### Estrutura do Projeto

```
resync/
├── api/                    # Endpoints da API
│   ├── dependencies.py     # Dependências compartilhadas
│   ├── operations.py       # Endpoints de idempotency
│   ├── rfc_examples.py     # Endpoints de exemplo RFC
│   └── models/
│       ├── links.py        # Modelos HATEOAS
│       └── responses.py    # Modelos de resposta
├── core/                   # Lógica de negócio
│   ├── idempotency.py      # Sistema de idempotency
│   ├── exceptions.py       # Exceções customizadas
│   └── structured_logger.py
└── docs/                   # Documentação
    ├── FASE_2.5_IDEMPOTENCY_IMPLEMENTATION.md
    ├── FASE_3_RFC_IMPLEMENTATION.md
    └── IMPLEMENTATION_SUMMARY.md
```

### Adicionar Novo Endpoint com Idempotency

```python
from fastapi import APIRouter, Depends
from resync.api.dependencies import (
    get_idempotency_manager,
    require_idempotency_key
)
from resync.core.idempotency import IdempotencyManager

router = APIRouter()

@router.post("/my-endpoint")
async def my_endpoint(
    data: MyModel,
    idempotency_key: str = Depends(require_idempotency_key),
    manager: IdempotencyManager = Depends(get_idempotency_manager)
):
    async def _process():
        # Sua lógica aqui
        return {"result": "success"}
    
    return await manager.execute_idempotent(
        key=idempotency_key,
        func=_process,
        ttl_seconds=3600
    )
```

### Adicionar Links HATEOAS

```python
from resync.api.models.links import LinkBuilder

builder = LinkBuilder()

# Adicionar links a um recurso
resource_dict = resource.model_dump()
resource_dict["_links"] = {
    "self": builder.build_self_link(
        path=f"/api/v1/resources/{resource.id}"
    ).model_dump(),
    "update": builder.build_link(
        path=f"/api/v1/resources/{resource.id}",
        rel="update",
        method="PUT"
    ).model_dump()
}
```

### Criar Resposta Paginada

```python
from resync.api.models.responses import create_paginated_response

response = create_paginated_response(
    items=items,
    total=total_count,
    page=page,
    page_size=page_size,
    base_path="/api/v1/resources",  # Para links automáticos
    query_params={"filter": "active"}  # Parâmetros adicionais
)
```

---

## 🧪 Testes

### Executar Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=resync --cov-report=html

# Testes específicos
pytest tests/test_idempotency.py
pytest tests/test_rfc_examples.py
```

### Testes Manuais com Swagger

1. Acesse http://localhost:8000/docs
2. Clique em "Try it out" em qualquer endpoint
3. Preencha os parâmetros
4. Clique em "Execute"
5. Veja a resposta

---

## 🐛 Troubleshooting

### Erro: "Idempotency service not initialized"

**Causa**: Redis não está disponível e fallback falhou.

**Solução**:
```bash
# Instale Redis
# Ubuntu/Debian
sudo apt-get install redis-server

# Mac
brew install redis

# Inicie Redis
redis-server

# Ou use Docker
docker run -d -p 6379:6379 redis:alpine
```

### Erro: "Module not found"

**Causa**: Dependências não instaladas.

**Solução**:
```bash
pip install -r requirements.txt
```

### Erro: "Port already in use"

**Causa**: Porta 8000 já está em uso.

**Solução**:
```bash
# Use outra porta
uvicorn resync.main:app --reload --port 8001

# Ou mate o processo
# Linux/Mac
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

## 📖 Documentação Adicional

### Guias Completos

- **Idempotency**: `docs/FASE_2.5_IDEMPOTENCY_IMPLEMENTATION.md`
- **RFC 7807 & HATEOAS**: `docs/FASE_3_RFC_IMPLEMENTATION.md`
- **Resumo Geral**: `docs/IMPLEMENTATION_SUMMARY.md`

### Exemplos Online

- **Swagger UI**: http://localhost:8000/docs
- **Idempotency Docs**: http://localhost:8000/api/v1/operations/idempotency-example
- **RFC Docs**: http://localhost:8000/api/v1/examples/rfc-examples

---

## 🎯 Próximos Passos

1. ✅ Explore os endpoints de exemplo
2. ✅ Leia a documentação completa
3. ✅ Teste com Swagger UI
4. ✅ Implemente seus próprios endpoints
5. ✅ Adicione testes

---

## 💡 Dicas

### Gerar Idempotency Keys

```bash
# Linux/Mac
uuidgen

# Python
python -c "import uuid; print(uuid.uuid4())"

# Node.js
node -e "console.log(require('crypto').randomUUID())"

# PowerShell
[guid]::NewGuid().ToString()
```

### Testar com HTTPie (alternativa ao curl)

```bash
# Instalar
pip install httpie

# Usar
http POST localhost:8000/api/v1/operations/resources \
  X-Idempotency-Key:$(uuidgen) \
  name="Test" \
  description="Testing"
```

### Testar com Postman

1. Importe a coleção OpenAPI: http://localhost:8000/openapi.json
2. Configure variável `idempotency_key` com `{{$guid}}`
3. Execute as requisições

---

## 🤝 Contribuindo

1. Crie uma branch: `git checkout -b feature/minha-feature`
2. Faça suas alterações
3. Adicione testes
4. Execute os testes: `pytest`
5. Commit: `git commit -m "feat: minha feature"`
6. Push: `git push origin feature/minha-feature`
7. Abra um Pull Request

---

## 📞 Suporte

- **Documentação**: `docs/` directory
- **Issues**: GitHub Issues
- **Swagger**: http://localhost:8000/docs

---

**Última Atualização**: 2024-01-15  
**Versão**: 1.0.0  
**Status**: ✅ Pronto para Desenvolvimento

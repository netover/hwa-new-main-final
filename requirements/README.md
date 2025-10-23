# 📦 Requirements Management

Este diretório contém a estrutura organizada de dependências para o projeto Resync.

## 📁 Estrutura de Arquivos

```
requirements/
├── base.txt      # Dependências core de produção (locked versions)
├── dev.txt       # Dependências de desenvolvimento (-r base.txt + dev tools)
├── prod.txt      # Dependências de produção (-r base.txt + gunicorn)
└── README.md     # Este arquivo
```

## 🚀 Como Usar

### Desenvolvimento
```bash
# Instalar todas as dependências de desenvolvimento
pip install -r requirements/dev.txt
```

### Produção
```bash
# Instalar apenas dependências de produção
pip install -r requirements/prod.txt
```

### CI/CD
```bash
# Para testes automatizados
pip install -r requirements/dev.txt

# Para build de produção
pip install -r requirements/prod.txt
```

## 📋 Conteúdo dos Arquivos

### base.txt
- **Framework Web**: FastAPI, Uvicorn
- **Validação**: Pydantic
- **Banco de Dados**: Redis, Neo4j
- **Segurança**: Cryptography, JOSE, PassLib
- **Performance**: Orjson, Psutil
- **IA/ML**: OpenAI, LiteLLM
- **Documentos**: PyPDF, python-docx, openpyxl

### dev.txt
- Todas as dependências de `base.txt`
- **Testes**: pytest, pytest-asyncio, pytest-cov
- **Qualidade**: mypy, pylint, ruff, black, isort
- **Segurança**: bandit, safety
- **Mutation Testing**: mutmut
- **Type Stubs**: types-*

### prod.txt
- Todas as dependências de `base.txt`
- **WSGI Server**: Gunicorn

## 🔒 Segurança

- ✅ **Versões locked**: Todas as dependências usam versões específicas (=)
- ✅ **Separação clara**: Produção vs desenvolvimento
- ✅ **Auditoria**: Dependências atualizadas para versões seguras
- ✅ **Minimalismo**: Produção instala apenas o necessário

## 📊 Estatísticas

- **base.txt**: ~25 dependências core
- **dev.txt**: ~40 dependências (base + ferramentas dev)
- **prod.txt**: ~26 dependências (base + gunicorn)

## 🔄 Migração

O arquivo `requirements.txt` na raiz está **DEPRECATED** e será removido em futuras versões. Use os arquivos nesta pasta.

Para migrar projetos existentes:
```bash
# Remover instalações antigas
pip uninstall -r requirements.txt -y

# Instalar nova estrutura
pip install -r requirements/dev.txt  # ou prod.txt
```

## 🚨 Alertas de Segurança

- `cryptography==42.0.0`: Atualizado da versão 41.0.8 (potencialmente vulnerável)
- `openai==1.50.0`: Atualizado da versão 1.3.5 (desatualizada)
- Removidas dependências desnecessárias em produção (mutmut, pytest-cov, etc.)

## 🤝 Contribuição

Ao adicionar novas dependências:

1. **Produção**: Adicione em `base.txt`
2. **Desenvolvimento**: Adicione em `dev.txt`
3. **Teste**: Verifique instalação com `pip install -r requirements/dev.txt`
4. **Security**: Execute `safety check` após mudanças


# Guia de Configuração de Segurança - Resync

## 🚨 CRÍTICO: Configurações de Segurança Obrigatórias

### 1. Credenciais de Administrador
**ARQUIVO:** `settings.toml`
**VARIÁVEIS:** `ADMIN_USERNAME`, `ADMIN_PASSWORD`

```toml
# ❌ INSEGURO - Não use em produção
ADMIN_PASSWORD = ""

# ✅ SEGURO - Use variáveis de ambiente
# Defina no ambiente:
# export ADMIN_USERNAME="seu_admin_seguro"
# export ADMIN_PASSWORD="senha_muito_forte_aqui"
```

### 2. Configuração CORS
**ARQUIVO:** `settings.toml`
**SEÇÃO:** `[default.CORS]`

```toml
# ❌ INSEGURO - Permite qualquer origem
ALLOWED_ORIGINS = []

# ✅ SEGURO - Restringir a domínios específicos
ALLOWED_ORIGINS = ["https://seudominio.com", "https://app.seudominio.com"]
ALLOW_CREDENTIALS = false
```

### 3. Chaves de API LLM
**ARQUIVO:** `settings.toml`
**VARIÁVEL:** `LLM_API_KEY`

```toml
# ❌ INSEGURO
LLM_API_KEY = ""

# ✅ SEGURO - Use variável de ambiente
# export LLM_API_KEY="sk-your-actual-api-key-here"
```

### 4. Configuração do Servidor
**ARQUIVO:** `resync/settings.py`
**VARIÁVEL:** `server_host`

```python
# ✅ SEGURO - Padrão localhost
server_host: str = Field(default="127.0.0.1", env="SERVER_HOST")
```

### 5. Credenciais do Banco de Dados
**ARQUIVO:** `settings.toml`
**VARIÁVEIS:** `NEO4J_USER`, `NEO4J_PASSWORD`

```toml
# ❌ INSEGURO
NEO4J_PASSWORD = ""

# ✅ SEGURO - Use variáveis de ambiente
# export NEO4J_USER="neo4j_user"
# export NEO4J_PASSWORD="strong_db_password"
```

## 🔧 Configurações por Ambiente

### Desenvolvimento
```bash
export APP_ENV=development
export ADMIN_PASSWORD="dev_password_change_me"
export LLM_API_KEY="sk-dev-key"
```

### Produção
```bash
export APP_ENV=production
export ADMIN_USERNAME="prod_admin"
export ADMIN_PASSWORD="PRODUCTION_STRONG_PASSWORD"
export LLM_API_KEY="sk-production-key"
export NEO4J_USER="prod_user"
export NEO4J_PASSWORD="PRODUCTION_DB_PASSWORD"
export SERVER_HOST="127.0.0.1"  # Nunca use 0.0.0.0 em produção
```

### Testes
```bash
export APP_ENV=test
export ADMIN_PASSWORD="test_password"
export LLM_API_KEY="sk-test-key"
```

## 🛡️ Verificações de Segurança

### Comando para verificar configurações inseguras:
```bash
# Verificar se há senhas vazias
grep -r "PASSWORD.*=.*\"\"" settings.toml

# Verificar configurações CORS inseguras
grep -A5 "\[default\.CORS\]" settings.toml
```

### Vulnerabilidades Corrigidas
- ✅ **MD5 → SHA256**: Substituído uso inseguro de MD5 por SHA256
- ✅ **Jinja2 Autoescape**: Habilitado autoescape para prevenir XSS
- ✅ **Host Binding**: Removido binding inseguro 0.0.0.0
- ✅ **Tratamento de Exceções**: Removido catch genérico perigoso

## 🚨 Checklist de Segurança para Deploy

- [ ] `ADMIN_PASSWORD` definido via variável de ambiente
- [ ] `LLM_API_KEY` definido via variável de ambiente
- [ ] `NEO4J_PASSWORD` definido via variável de ambiente
- [ ] `CORS.ALLOWED_ORIGINS` configurado apenas para domínios autorizados
- [ ] `SERVER_HOST` definido como `127.0.0.1` (não `0.0.0.0`)
- [ ] Logs em nível `WARNING` ou superior em produção
- [ ] CSP habilitado e não em `REPORT_ONLY`
- [ ] Rate limiting configurado adequadamente
- [ ] Backups de banco de dados configurados
- [ ] Certificados SSL/TLS válidos instalados

## 🔍 Monitoramento Contínuo

### Métricas Críticas para Monitorar:
- Tentativas de login falhidas
- Violações de CORS
- Violações de CSP
- Rate limits atingidos
- Conexões de IPs suspeitos

### Alertas de Segurança:
- Mudanças nas configurações críticas
- Acesso não autorizado a endpoints admin
- Tentativas de SQL injection
- Ataques XSS detectados

---

**IMPORTANTE:** Este documento deve ser revisado antes de cada deploy em produção. Configurações inseguras são a causa mais comum de breaches de segurança.


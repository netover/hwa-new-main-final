# Redis para Windows - Guia de Instalação e Melhores Práticas

## 📋 Visão Geral

Este guia documenta o processo de instalação e configuração do Redis no Windows para desenvolvimento e testes da aplicação Resync.

## 🚀 Instalação do Redis no Windows

### Método 1: Download Direto (Recomendado para Desenvolvimento)

1. **Baixar o Redis para Windows**:
   ```bash
   curl -L -o redis-windows.zip https://github.com/microsoftarchive/redis/releases/download/win-3.0.504/Redis-x64-3.0.504.zip
   ```

2. **Extrair os arquivos**:
   ```bash
   Expand-Archive -Path redis-windows.zip -DestinationPath . -Force
   ```

3. **Iniciar o servidor Redis**:
   ```bash
   .\redis-server.exe redis.windows.conf
   ```

4. **Verificar funcionamento**:
   ```bash
   .\redis-cli.exe ping
   # Deve retornar: PONG
   ```

### Método 2: Usando Docker (Recomendado para Produção)

```yaml
# docker-compose.yml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 1s
      timeout: 1s
      retries: 5
```

Iniciar com:
```bash
docker-compose up -d redis
```

## ⚙️ Configurações Recomendadas

### Arquivo de Configuração (redis.windows.conf)

```conf
# Configurações básicas
port 6379
bind 127.0.0.1  # Apenas localhost para desenvolvimento

# Persistência
save 900 1
save 300 10
save 60 10000

# Segurança
requirepass your_secure_password_here

# Memória
maxmemory 256mb
maxmemory-policy allkeys-lru

# Logging
loglevel notice
logfile "redis.log"
```

### Configurações de Segurança

1. **Definir senha**:
   ```bash
   .\redis-cli.exe config set requirepass "sua_senha_segura"
   ```

2. **Acesso remoto (produção)**:
   ```conf
   bind 0.0.0.0  # PERIGOSO em produção sem firewall
   protected-mode yes
   ```

## 🔧 Configuração da Aplicação

### Variáveis de Ambiente

```bash
# settings.toml
REDIS_URL = "redis://localhost:6379"
REDIS_PASSWORD = "sua_senha_segura"
REDIS_DB = 0

# Configurações de pool
REDIS_POOL_MIN_SIZE = 2
REDIS_POOL_MAX_SIZE = 10
REDIS_POOL_TIMEOUT = 30
```

### Configuração para Desenvolvimento

```toml
# settings.development.toml
REDIS_URL = "redis://localhost:6379/0"
REDIS_POOL_MIN_SIZE = 1
REDIS_POOL_MAX_SIZE = 5
```

## 🛠️ Comandos Úteis

### Operações Básicas

```bash
# Verificar status
.\redis-cli.exe ping
.\redis-cli.exe info

# Definir chave
.\redis-cli.exe set minha_chave "meu_valor"

# Obter chave
.\redis-cli.exe get minha_chave

# Listar chaves
.\redis-cli.exe keys "*"

# Deletar chave
.\redis-cli.exe del minha_chave

# Verificar uso de memória
.\redis-cli.exe info memory
```

### Monitoramento

```bash
# Monitorar comandos em tempo real
.\redis-cli.exe monitor

# Ver estatísticas detalhadas
.\redis-cli.exe info stats
```

## 🔍 Troubleshooting

### Problemas Comuns

1. **Porta 6379 ocupada**:
   ```bash
   netstat -ano | findstr :6379
   taskkill /F /PID <PID>
   ```

2. **Redis não inicia**:
   - Verificar se há outro processo Redis rodando
   - Verificar configurações de firewall
   - Verificar logs: `redis.log`

3. **Aplicação não conecta**:
   - Verificar se Redis está rodando
   - Testar conexão: `redis-cli ping`
   - Verificar configurações de rede

### Logs e Debugging

```bash
# Ver logs detalhados
.\redis-server.exe redis.windows.conf --loglevel verbose

# Monitorar conexões
.\redis-cli.exe client list
```

## 📊 Monitoramento e Performance

### Métricas Importantes

```bash
# Uso de memória
INFO memory

# Conexões ativas
INFO clients

# Estatísticas de comandos
INFO stats

# Persistência
INFO persistence
```

### Ferramentas de Monitoramento

1. **Redis Commander** (Interface Web):
   ```bash
   docker run -d -p 8081:8081 --name redis-commander \
     -e REDIS_HOST=localhost \
     -e REDIS_PORT=6379 \
     rediscommander/redis-commander
   ```

2. **Monitoramento via aplicação**:
   - Endpoint: `/health/redis`
   - Métricas: conexões, memória, latência

## 🏗️ Arquitetura Recomendada

### Desenvolvimento
```
┌─────────────────┐    ┌─────────────────┐
│   Aplicação     │    │     Redis       │
│   (Python)      │◄──►│   (localhost)   │
└─────────────────┘    └─────────────────┘
```

### Produção (Docker)
```
┌─────────────────┐    ┌─────────────────┐
│   Aplicação     │    │     Redis       │
│   (Container)   │◄──►│   (Container)   │
└─────────────────┘    └─────────────────┘
     │                        │
     └────────────────────────┘
           Network: redis-net
```

## ⚡ Performance Tuning

### Configurações de Performance

```conf
# Memória
maxmemory 1gb
maxmemory-policy allkeys-lru

# Conexões
tcp-keepalive 300

# I/O
appendonly yes
appendfsync everysec

# CPU
save 900 1
save 300 10
save 60 10000
```

### Benchmarking

```bash
# Teste de performance
.\redis-benchmark.exe -q

# Teste específico
.\redis-benchmark.exe -t set,get -n 100000
```

## 🔒 Segurança

### Recomendações de Segurança

1. **Não usar Redis sem senha em produção**
2. **Configurar firewall adequadamente**
3. **Usar redes internas para comunicação**
4. **Monitorar acessos e conexões**
5. **Atualizar Redis regularmente**

### Configuração Segura

```conf
# Segurança básica
requirepass sua_senha_muito_segura
protected-mode yes

# Rede
bind 127.0.0.1  # Apenas localhost
port 6379

# Desabilitar comandos perigosos
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command SHUTDOWN SHUTDOWN_REDIS
```

## 📝 Checklist de Instalação

- [ ] Baixar Redis para Windows
- [ ] Extrair arquivos
- [ ] Configurar arquivo redis.conf
- [ ] Definir senha de segurança
- [ ] Iniciar servidor Redis
- [ ] Testar conexão básica
- [ ] Configurar aplicação para usar Redis
- [ ] Testar integração aplicação-Redis
- [ ] Configurar monitoramento
- [ ] Documentar configurações

## 🔗 Recursos Adicionais

- [Redis Documentation](https://redis.io/documentation)
- [Redis Windows Releases](https://github.com/microsoftarchive/redis/releases)
- [Redis Security](https://redis.io/topics/security)
- [Redis Best Practices](https://redis.io/topics/admin)

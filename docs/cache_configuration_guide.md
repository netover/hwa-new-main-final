# Guia de Configuração de Cache

Este documento fornece um guia abrangente para configurar e otimizar os sistemas de cache utilizados no projeto Resync, incluindo AsyncTTLCache, TWS_OptimizedAsyncCache e Cache Hierarchy.

## Visão Geral dos Sistemas de Cache

O projeto utiliza múltiplas camadas de cache para otimizar o desempenho:

1. **AsyncTTLCache**: Cache básico com TTL e limpeza assíncrona
2. **TWS_OptimizedAsyncCache**: Versão otimizada para workloads TWS
3. **Cache Hierarchy**: Sistema hierárquico L1/L2 com diferentes estratégias

## Configurações via settings.toml

Todas as configurações de cache podem ser definidas no arquivo `settings.toml`:

```toml
# Async Cache Configuration
ASYNC_CACHE_TTL = 60
ASYNC_CACHE_CLEANUP_INTERVAL = 30
ASYNC_CACHE_NUM_SHARDS = 8
ASYNC_CACHE_MAX_WORKERS = 4

# Cache Hierarchy Configuration
CACHE_HIERARCHY_L1_MAX_SIZE = 5000
CACHE_HIERARCHY_L2_TTL = 600
CACHE_HIERARCHY_L2_CLEANUP_INTERVAL = 60
CACHE_HIERARCHY_NUM_SHARDS = 8
CACHE_HIERARCHY_MAX_WORKERS = 4

# KeyLock Configuration
KEY_LOCK_MAX_LOCKS = 2048
```

## 1. Configurações do AsyncTTLCache

### Parâmetros Principais

| Parâmetro | Padrão | Descrição | Faixa Recomendada |
|-----------|--------|-----------|-------------------|
| `ttl_seconds` | 60 | Tempo de vida dos itens em segundos | 30-300 |
| `cleanup_interval` | 30 | Intervalo de limpeza em segundos | 15-60 |
| `num_shards` | 8 | Número de shards para distribuição | 4-16 |

### Otimizações por Cenário

#### **Ambiente de Desenvolvimento**
```toml
ASYNC_CACHE_TTL = 120
ASYNC_CACHE_CLEANUP_INTERVAL = 60
ASYNC_CACHE_NUM_SHARDS = 4
```
- **Por quê?** Menos recursos, foco em desenvolvimento rápido

#### **Ambiente de Produção - Alto Tráfego**
```toml
ASYNC_CACHE_TTL = 60
ASYNC_CACHE_CLEANUP_INTERVAL = 15
ASYNC_CACHE_NUM_SHARDS = 16
ASYNC_CACHE_MAX_WORKERS = 8
```
- **Por quê?** Menor latência, maior paralelismo

#### **Ambiente com Memória Limitada**
```toml
ASYNC_CACHE_TTL = 30
ASYNC_CACHE_CLEANUP_INTERVAL = 10
ASYNC_CACHE_NUM_SHARDS = 8
```
- **Por quê?** Limpeza mais frequente para liberar memória

## 2. Configurações do TWS_OptimizedAsyncCache

Este cache é especificamente otimizado para workloads TWS (HCL Workload Automation).

### Parâmetros Específicos

| Parâmetro | Padrão | Descrição | Otimização |
|-----------|--------|-----------|------------|
| `concurrency_threshold` | 5 | Threshold para ajuste dinâmico | 3-10 |
| `max_workers` | 4 | Máximo de threads para operações paralelas | 2-8 |
| `num_shards` | 8 | Número de shards (otimizado para TWS) | 8-12 |

### Configuração para Diferentes Volumes de Jobs

#### **Baixo Volume (< 1000 jobs/dia)**
```toml
ASYNC_CACHE_NUM_SHARDS = 6
ASYNC_CACHE_MAX_WORKERS = 2
ASYNC_CACHE_CONCURRENCY_THRESHOLD = 3
```

#### **Médio Volume (1000-10000 jobs/dia)**
```toml
ASYNC_CACHE_NUM_SHARDS = 8
ASYNC_CACHE_MAX_WORKERS = 4
ASYNC_CACHE_CONCURRENCY_THRESHOLD = 5
```

#### **Alto Volume (> 10000 jobs/dia)**
```toml
ASYNC_CACHE_NUM_SHARDS = 12
ASYNC_CACHE_MAX_WORKERS = 8
ASYNC_CACHE_CONCURRENCY_THRESHOLD = 8
```

## 3. Configurações do Cache Hierarchy (L1/L2)

### Parâmetros L1 (Memória)
| Parâmetro | Padrão | Descrição | Otimização |
|-----------|--------|-----------|------------|
| `max_size` | 5000 | Tamanho máximo do cache L1 | 1000-10000 |
| `num_shards` | 8 | Número de shards L1 | 4-16 |

### Parâmetros L2 (Redis)
| Parâmetro | Padrão | Descrição | Otimização |
|-----------|--------|-----------|------------|
| `ttl` | 600 | TTL para itens L2 em segundos | 300-3600 |
| `cleanup_interval` | 60 | Intervalo de limpeza L2 | 30-120 |

### Configuração por Tipo de Aplicação

#### **Aplicação com Muitos Reads**
```toml
CACHE_HIERARCHY_L1_MAX_SIZE = 8000
CACHE_HIERARCHY_L2_TTL = 900
```
- **Por quê?** Prioriza retenção de dados frequentemente acessados

#### **Aplicação com Muitos Writes**
```toml
CACHE_HIERARCHY_L1_MAX_SIZE = 3000
CACHE_HIERARCHY_L2_TTL = 300
CACHE_HIERARCHY_L2_CLEANUP_INTERVAL = 30
```
- **Por quê?** Evita sobrecarga de memória com limpeza mais frequente

## 4. Configurações de KeyLock

### Parâmetro Principal
| Parâmetro | Padrão | Descrição | Otimização |
|-----------|--------|-----------|------------|
| `max_locks` | 2048 | Número máximo de locks simultâneos | 1024-4096 |

### Otimização por Concorrência

#### **Baixa Concorrência**
```toml
KEY_LOCK_MAX_LOCKS = 1024
```

#### **Alta Concorrência**
```toml
KEY_LOCK_MAX_LOCKS = 4096
ASYNC_CACHE_NUM_SHARDS = 16
```

## 5. Monitoramento e Métricas

### Métricas Disponíveis

O sistema coleta métricas detalhadas através do Prometheus:

- **Hit/Miss Ratios**: Taxa de acerto do cache
- **Latências**: Tempo de resposta das operações
- **Contenção de Locks**: Número de conflitos de lock
- **Uso de Memória**: Tamanho atual do cache

### Comando para Verificar Métricas

```bash
# Via Prometheus endpoint
curl http://localhost:9090/api/v1/query?query=cache_hierarchy_hit_ratio

# Via aplicação (se disponível)
curl http://localhost:8000/metrics
```

## 6. Configurações por Ambiente

### Desenvolvimento
```toml
[development]
ASYNC_CACHE_TTL = 120
ASYNC_CACHE_CLEANUP_INTERVAL = 60
ASYNC_CACHE_NUM_SHARDS = 4
CACHE_HIERARCHY_L1_MAX_SIZE = 1000
```

### Testes
```toml
[test]
ASYNC_CACHE_TTL = 30
ASYNC_CACHE_CLEANUP_INTERVAL = 15
ASYNC_CACHE_NUM_SHARDS = 2
CACHE_HIERARCHY_L1_MAX_SIZE = 500
```

### Produção
```toml
[production]
ASYNC_CACHE_TTL = 60
ASYNC_CACHE_CLEANUP_INTERVAL = 30
ASYNC_CACHE_NUM_SHARDS = 8
CACHE_HIERARCHY_L1_MAX_SIZE = 5000
CACHE_HIERARCHY_L2_TTL = 600
```

## 7. Dicas de Otimização

### 1. **Monitore o Hit Ratio**
```python
# Ideal: > 80%
hit_ratio = cache.get_metrics()['hit_ratio']
if hit_ratio < 0.8:
    # Considere aumentar o tamanho do cache ou TTL
    pass
```

### 2. **Ajuste Baseado na Latência**
```python
# Se latência > 10ms, considere:
# - Aumentar número de shards
# - Usar cache local (L1) maior
# - Otimizar distribuição de chaves
```

### 3. **Balanceie Memória vs Performance**
- **Mais shards** = Menos contenção, mais memória usada
- **TTL menor** = Dados mais frescos, mais operações de limpeza
- **Cache L1 maior** = Menos chamadas ao L2, mais uso de memória

## 8. Troubleshooting

### Problemas Comuns e Soluções

#### **Hit Ratio Muito Baixo**
```toml
# Aumente o tamanho do cache L1
CACHE_HIERARCHY_L1_MAX_SIZE = 8000

# Ou aumente o TTL
ASYNC_CACHE_TTL = 120
```

#### **Alta Contenção de Locks**
```toml
# Aumente o número de shards
ASYNC_CACHE_NUM_SHARDS = 12

# Aumente o número máximo de locks
KEY_LOCK_MAX_LOCKS = 4096
```

#### **Uso Excessivo de Memória**
```toml
# Reduza o tamanho do cache L1
CACHE_HIERARCHY_L1_MAX_SIZE = 2000

# Diminua o TTL
ASYNC_CACHE_TTL = 30

# Aumente a frequência de limpeza
ASYNC_CACHE_CLEANUP_INTERVAL = 15
```

## 9. Exemplos de Configuração Completa

### Configuração para Sistema de Alto Desempenho
```toml
[production.high_performance]
ASYNC_CACHE_TTL = 60
ASYNC_CACHE_CLEANUP_INTERVAL = 15
ASYNC_CACHE_NUM_SHARDS = 16
ASYNC_CACHE_MAX_WORKERS = 8
CACHE_HIERARCHY_L1_MAX_SIZE = 10000
CACHE_HIERARCHY_L2_TTL = 900
CACHE_HIERARCHY_NUM_SHARDS = 16
CACHE_HIERARCHY_MAX_WORKERS = 8
KEY_LOCK_MAX_LOCKS = 4096
```

### Configuração para Sistema Otimizado para Memória
```toml
[production.memory_optimized]
ASYNC_CACHE_TTL = 30
ASYNC_CACHE_CLEANUP_INTERVAL = 10
ASYNC_CACHE_NUM_SHARDS = 8
ASYNC_CACHE_MAX_WORKERS = 4
CACHE_HIERARCHY_L1_MAX_SIZE = 2000
CACHE_HIERARCHY_L2_TTL = 300
CACHE_HIERARCHY_L2_CLEANUP_INTERVAL = 30
KEY_LOCK_MAX_LOCKS = 2048
```

Este guia serve como referência para otimizar as configurações de cache de acordo com as necessidades específicas do seu ambiente e workload.

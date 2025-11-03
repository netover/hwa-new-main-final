# 🔄 RUNBOOK EXECUTÁVEL: MIGRAÇÃO SISTEMA DE CACHE
## Projeto Resync - Guia Passo-a-Passo para Execução Segura

---

## 🎯 CHECKLIST DE PRÉ-VALIDAÇÃO (OBRIGATÓRIO)

### ⛓️ INFRAESTRUTURA
- [ ] Ambiente staging idêntico à produção configurado
- [ ] Feature flags: `MIGRATION_USE_NEW_CACHE=false` (default)
- [ ] Métricas Prometheus ativas e dashboards Grafana configurados
- [ ] Alertas de monitoramento testados e funcionais
- [ ] Scripts de rollback validados em staging

### 💻 CÓDIGO E TESTES
- [ ] CacheMigrationManager implementado e testes passando (100%)
- [ ] ImprovedAsyncCache validado isoladamente
- [ ] Testes unitários e de integração executados
- [ ] Code review aprovado por arquitetura
- [ ] Pull requests criados para cada arquivo de migração

### 📊 PERFORMANCE E MONITORAMENTO
- [ ] Baseline de performance coletada (latência, throughput, memory)
- [ ] Performance benchmarks estabelecidos com thresholds
- [ ] Métricas de migração configuradas (legacy_hits, new_hits, fallbacks)
- [ ] Alertas críticos configurados (P0/P1/P2)
- [ ] Dashboards de produção prontos

### 👥 EQUIPE E COMUNICAÇÃO
- [ ] Responsabilidades claras definidas (DevOps, Developers, QA)
- [ ] Plano de comunicação estabelecido (Slack, email, standups)
- [ ] Stakeholders alinhados (Product, Business, Leadership)
- [ ] On-call schedule definido para período de migração
- [ ] Runbook distribuído e treinado com equipe

---

## 📅 EXECUÇÃO - SEMANA 1: PREPARAÇÃO

### DIA 1: Setup e Baseline (8h)
**Responsável**: DevOps + Developer

**08:00-10:00**: Configuração de Ambiente
```bash
# Configurar feature flags
export APP_MIGRATION_USE_NEW_CACHE=false
export APP_MIGRATION_ENABLE_METRICS=true

# Validar configurações
python -c "from resync.settings import settings; print(f'Cache migration: {settings.MIGRATION_USE_NEW_CACHE}')"
```

**10:00-12:00**: Baseline de Performance
```bash
# Executar benchmarks
python scripts/performance_baseline.py

# Coletar métricas atuais
curl -s http://localhost:9090/api/v1/query?query=cache_operations_total | jq .
```

**14:00-16:00**: Validação de Rollback
```bash
# Testar rollback procedures
./scripts/test_rollback.sh

# Validar que sistema volta ao normal
curl -f http://localhost/health || echo "Health check failed"
```

### DIA 2: Testes Abrangentes (8h)
**Responsável**: QA + Developer

**09:00-12:00**: Testes de Compatibilidade
```bash
# Executar testes de interface
pytest tests/test_migration_managers.py -v

# Validar contratos de API
python scripts/validate_interfaces.py
```

**14:00-17:00**: Testes de Stress
```bash
# Testes de concorrência
python scripts/stress_test_cache.py --concurrency=100 --duration=300

# Testes de memory pressure
python scripts/memory_pressure_test.py
```

### DIA 3: Code Review e Aprovação (6h)
**Responsável**: Team Lead + Architects

**09:00-12:00**: Technical Review
- [ ] MigrationManager code review
- [ ] Security assessment
- [ ] Performance implications
- [ ] Rollback procedures review

**14:00-16:00**: Stakeholder Alignment
- [ ] Business impact review
- [ ] Risk assessment final
- [ ] Go-live criteria definition
- [ ] Communication plan approval

**DECISÃO CRÍTICA**: Go/No-go para prosseguir com migração

---

## ⚡ EXECUÇÃO - SEMANA 2: MIGRAÇÃO CONTROLADA

### DIA 1: `resync/core/__init__.py` (RISCO ALTO)
**Impacto**: Crítico - Ponto central de dependência

**08:00-09:00**: Pre-flight Checks
```bash
# Verificar health pré-migração
curl -f http://staging/health || exit 1

# Baseline de métricas
python scripts/collect_baseline.py
```

**09:00-10:00**: Execução da Mudança
```python
# resync/core/__init__.py

# ANTES
from resync.core.async_cache import AsyncTTLCache

# DEPOIS
from resync.core.migration_managers import cache_migration_manager

# Atualizar boot manager
boot_manager.register_component("CacheSystem", cache_migration_manager)
```

**10:00-12:00**: Validação Imediata
```bash
# Deploy para staging
./deploy_staging.sh

# Executar testes
pytest tests/test_core_init.py -v

# Health checks
curl -f http://staging/health || exit 1
```

**14:00-16:00**: Monitoramento (4 horas)
```bash
# Monitorar métricas em tempo real
watch -n 30 'curl -s http://staging/metrics | grep cache'

# Verificar performance
python scripts/performance_check.py --baseline=baseline.json
```

**16:00-17:00**: Go/No-go Decision
```bash
# Comparar métricas
python scripts/compare_metrics.py --before=baseline.json --after=current.json

# Criteria: <5% performance degradation AND all health checks passing
```

**DECISÃO**: PROCEED or ROLLBACK

### DIA 2: `resync/core/health_service.py` (RISCO MÉDIO)

**Adaptações Necessárias**:
```python
# ANTES
await test_cache.stop()
metrics = test_cache.get_detailed_metrics()

# DEPOIS
await test_cache.shutdown()
metrics = test_cache.get_stats()
```

**Validação**: Health checks específicos funcionais

### DIA 3: `resync/core/llm_optimizer.py` (RISCO ALTO)

**Pontos Críticos**:
- Prompt cache (TTL 3600s)
- Response cache (TTL 300s)
- IA functionality intact

**Validação**: LLM responses within SLA

### DIA 4: `resync/core/cache_hierarchy.py` (RISCO ALTO)

**Adaptações Necessárias**:
- Implementar método `size()` compatível
- Manter operações L1/L2

### DIA 5: Arquivos de Teste (RISCO BAIXO)

**Arquivos**:
- `chaos_engineering.py`
- `llm_monitor.py`
- `stress_testing.py`

---

## 🧪 EXECUÇÃO - SEMANA 3: VALIDAÇÃO ABRANGENTE

### DIAS 1-2: End-to-End Testing

**Cenários de Produção**:
```bash
# Load testing
python scripts/load_test.py --users=1000 --duration=3600

# Chaos engineering
python scripts/chaos_test.py --scenario=network_partition

# Performance regression
python scripts/performance_regression.py
```

**Cenários de Failure**:
```bash
# Memory exhaustion
python scripts/memory_exhaustion_test.py

# Network failures
python scripts/network_failure_test.py

# Service restarts
python scripts/service_restart_test.py
```

### DIA 3: Performance Optimization

**Análise**:
```bash
# Performance comparison
python scripts/performance_analysis.py --before=migration_start --after=current

# Memory profiling
python scripts/memory_profiling.py
```

**Otimização**:
```python
# Ajustar configurações baseadas em dados
settings.ASYNC_CACHE_NUM_SHARDS = 32  # Aumentado de 16
settings.ASYNC_CACHE_CLEANUP_INTERVAL = 30  # Reduzido de 60
```

### DIA 4: Production Readiness Review

**Final Checklist**:
- [ ] Architecture review completo
- [ ] Security assessment aprovado
- [ ] Performance requirements met
- [ ] Rollback procedures validadas
- [ ] Deployment scripts prontos

---

## 🚀 EXECUÇÃO - SEMANA 4: DEPLOYMENT CONTROLADO

### H-24h: Validação Final em Staging

```bash
# Full production-like testing
./scripts/full_staging_test.sh

# Validate all KPIs
python scripts/validate_kpis.py --environment=staging
```

### H-2h: Preparação Produção

```bash
# Backup completo
./scripts/backup_production.sh

# Validate rollback scripts
./scripts/test_rollback_production.sh

# Communication to stakeholders
./scripts/notify_stakeholders.sh --message="Migration starting in 2 hours"
```

### H-30m: Deployment Safe State

```bash
# Disable feature flag (safe state)
export APP_MIGRATION_USE_NEW_CACHE=false

# Deploy new code
./deploy_production.sh

# Validate deployment
curl -f http://production/health || exit 1
```

### H+0: Gradual Rollout

```bash
# Enable 10% traffic
export APP_MIGRATION_USE_NEW_CACHE=true
./scripts/traffic_split.sh --percentage=10

# Monitor 15 minutes
watch -n 60 './scripts/monitor_migration.sh'

# Gradual increase
./scripts/traffic_split.sh --percentage=25
# ... monitor ...
./scripts/traffic_split.sh --percentage=50
# ... monitor ...
./scripts/traffic_split.sh --percentage=100
```

### H+1h: Full Production Monitoring

```bash
# 24/7 monitoring for 1 week
./scripts/start_production_monitoring.sh --duration=604800

# Performance trending
./scripts/performance_trending.sh --continuous

# User feedback monitoring
./scripts/monitor_user_feedback.sh
```

---

## 🚨 PROCEDURES DE ROLLBACK

### Rollback Imediato (< 5 minutos)
```bash
# Para degradação de performance ou erros críticos
export APP_MIGRATION_USE_NEW_CACHE=false
systemctl restart resync

# Validar recuperação
curl -f http://production/health || echo "CRITICAL: Health check failed"
```

### Rollback Completo (< 30 minutos)
```bash
# Para issues mais complexos
export APP_MIGRATION_USE_NEW_CACHE=false
git revert <migration_commit_ids>
./deploy_production.sh

# Monitorar recuperação
./scripts/monitor_recovery.sh --duration=3600
```

### Rollback Full (< 2 horas)
```bash
# Última opção - versão anterior conhecida
./deploy_previous_version.sh
# Restore database if necessary
# Full system validation
./scripts/full_system_validation.sh
```

---

## 📊 MONITORAMENTO CONTÍNUO

### Métricas Críticas (Monitorar Sempre)

**Performance Metrics**:
```prometheus
# Latência de operações
histogram_quantile(0.95, rate(cache_operation_duration_seconds[5m]))

# Taxa de sucesso
rate(cache_operations_total{status="success"}[5m]) / rate(cache_operations_total[5m])

# Memory usage
process_resident_memory_bytes / 1024 / 1024
```

**Business Metrics**:
```prometheus
# LLM response time
histogram_quantile(0.95, rate(llm_response_duration_seconds[5m]))

# API performance
histogram_quantile(0.95, rate(http_request_duration_seconds[5m]))

# Error rates
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

### Alertas Configurados

**P0 - IMEDIATA INTERVENÇÃO**:
- Performance degradation > 20%
- Error rate > 1%
- System unavailable

**P1 - RAPID RESPONSE (1h)**:
- Performance degradation > 10%
- Memory usage > 90%
- Cache hit rate < 80%

**P2 - MONITORAR (4h)**:
- Performance degradation > 5%
- Increased fallback events

---

## 📞 COMUNICAÇÃO DURANTE MIGRAÇÃO

### Status Updates
- **Daily Standups**: Progress updates e blocking issues
- **Hourly Updates**: Durante deployment window
- **Immediate Alerts**: Para issues P0/P1
- **Stakeholder Updates**: Regular communications

### Escalation Matrix
- **P0 Issues**: Page + conference bridge immediately
- **P1 Issues**: Slack alerts + 1h response time
- **P2 Issues**: Daily review + monitoring

### Comunicação Templates
```bash
# Status update
./scripts/send_status_update.sh --status="PHASE_2_DAY_1_COMPLETE" --issues="0"

# Incident communication
./scripts/incident_communication.sh --severity=P1 --message="Performance degradation detected, monitoring closely"

# Success communication
./scripts/success_communication.sh --message="Migration phase 1 completed successfully, proceeding to phase 2"
```

---

## 📝 DOCUMENTAÇÃO PÓS-MIGRAÇÃO

### Immediate Tasks
- [ ] Update runbook with lessons learned
- [ ] Document performance baselines atualizados
- [ ] Archive migration dashboards
- [ ] Update architecture diagrams

### Long-term Tasks
- [ ] Code cleanup (remove legacy code after 30 days)
- [ ] Performance monitoring dashboards permanentes
- [ ] Migration playbook para futuras migrações
- [ ] Team retrospective e improvements identificados

---

## 🎯 SUCCESS CRITERIA VALIDATION

### Automated Validation
```bash
# Executar após cada phase
python scripts/validate_success_criteria.py --phase=PHASE_2_DAY_1

# Resultado esperado:
✅ Performance: > 95% baseline
✅ Functionality: 100% APIs working
✅ Reliability: < 0.1% error rate
✅ Rollback: < 5 min capability
```

### Manual Validation
- [ ] User experience review
- [ ] Business metrics validation
- [ ] Security assessment
- [ ] Compliance requirements met

---

**STATUS**: Runbook completo e executável criado.

**READY FOR EXECUTION**: Equipe pode seguir este runbook passo-a-passo para migração segura e controlada.

🚀 **LET'S MIGRATE SAFELY!**



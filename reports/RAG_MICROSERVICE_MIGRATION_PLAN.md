# Plano de Migração: RAG para Microserviço Independente

## 📋 **Visão Geral da Migração**

Este plano detalhado descreve a separação completa do sistema RAG (Retrieval-Augmented Generation) do HWA API Gateway para um microserviço independente, otimizado para **processamento sequencial CPU-only**.

### 🎯 **Objetivos da Migração**

- **Isolamento de Recursos**: RAG não compete por CPU com API principal
- **Processamento Assíncrono**: Uploads não bloqueiam usuários
- **Escalabilidade Horizontal**: Múltiplas instâncias RAG independentes
- **Manutenibilidade**: Deploy e evolução independentes
- **Observabilidade**: Métricas RAG dedicadas

### ⚠️ **Restrições Consideradas**

- **Hardware**: CPU-only (sem GPU disponível)
- **Processamento**: Sequencial (1 arquivo por vez)
- **Arquitetura**: Fila de espera para múltiplos arquivos
- **Compatibilidade**: Manter APIs existentes durante migração

---

## 🏗️ **Fase 1: Análise e Planejamento Arquitetural**

### **1.1 Análise da Arquitetura Atual**

- [x] **Mapear dependências RAG**: Identificar todos os módulos que interagem com RAG
- [x] **Analisar interfaces**: Documentar `IFileIngestor`, `IKnowledgeGraph`
- [x] **Avaliar estado atual**: Verificar saúde do sistema RAG existente
- [x] **Identificar pontos de integração**: APIs, configurações, middlewares

### **1.2 Design da Nova Arquitetura**

- [x] **Definir boundaries**: Que funcionalidades ficam no RAG vs API Gateway
- [ ] **Design APIs**: Contratos REST entre serviços
- [ ] **Sistema de filas**: Estratégia para processamento sequencial
- [ ] **Estratégia de migração**: Blue-green ou gradual

### **1.3 Definição de Requisitos Não-Funcionais**

- [ ] **Performance**: Latências esperadas para diferentes operações
- [ ] **Escalabilidade**: Como dimensionar múltiplas instâncias
- [ ] **Confiabilidade**: SLA e estratégias de fallback
- [ ] **Segurança**: Autenticação entre serviços

---

## 🚀 **Fase 2: Implementação da Infraestrutura**

### **2.1 Sistema de Filas Redis**
```python
# Fila para processamento sequencial
class RAGJobQueue:
    async def enqueue_job(self, job: RAGJob) -> str:
        """Adiciona job à fila e retorna job_id"""

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Consulta status do processamento"""

    async def process_next_job(self) -> Optional[RAGJob]:
        """Processa próximo job da fila (sequencial)"""
```

- [ ] **Implementar Redis Queue**: Classe para gerenciar fila de jobs
- [ ] **Definir estrutura Job**: Campos necessários (file_path, metadata, status)
- [ ] **Implementar status tracking**: Estados (queued, processing, completed, failed)
- [ ] **Adicionar timeouts**: Prevenção de jobs travados

### **2.2 API Assíncrona no Gateway**
```python
# Novo endpoint assíncrono
@app.post("/api/v1/rag/upload")
async def upload_rag_file(file: UploadFile) -> dict:
    job_id = await rag_client.enqueue_file(file)
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "File queued for processing"
    }
```

- [ ] **Modificar endpoint `/rag/upload`**: Tornar assíncrono
- [ ] **Adicionar endpoint `/rag/jobs/{job_id}`**: Consultar status
- [ ] **Implementar RAG client**: Cliente HTTP para comunicar com RAG service
- [ ] **Adicionar WebSocket notifications**: Status updates em tempo real

### **2.3 Microserviço RAG Base**
```python
# Estrutura base do microserviço
rag_service/
├── main.py              # FastAPI app
├── api/
│   ├── routes.py        # Endpoints REST
│   └── models.py        # Request/Response models
├── core/
│   ├── job_queue.py     # Gerenciamento de filas
│   ├── processor.py     # Processamento sequencial
│   └── vector_store.py  # FAISS/Chroma integration
├── config.py            # Configuração independente
└── health.py            # Health checks específicos
```

- [ ] **Criar estrutura base**: Diretórios e arquivos iniciais
- [ ] **Implementar FastAPI app**: Servidor independente para RAG
- [ ] **Configurar dependências**: Poetry/pyproject.toml separado
- [ ] **Implementar health checks**: Próprios do RAG service

---

## 🔧 **Fase 3: Migração das Funcionalidades Core**

### **3.1 Migração do FileIngestor**
```python
class RAGServiceProcessor:
    """Processador sequencial no microserviço"""

    async def process_file_job(self, job: RAGJob) -> bool:
        """Processa um arquivo por vez"""
        # 1. Download do arquivo (se remoto)
        # 2. Extração de texto (PDF/Word/Excel)
        # 3. Chunking inteligente
        # 4. Geração de embeddings (CPU-optimized)
        # 5. Indexação no vector store
        # 6. Update do job status
```

- [ ] **Migrar FileIngestor**: Para o microserviço RAG
- [ ] **Adaptar para processamento sequencial**: Remover paralelização
- [ ] **Otimizar para CPU**: Usar bibliotecas CPU-optimized
- [ ] **Adicionar logging detalhado**: Progresso do processamento

### **3.2 Migração do Vector Store**
```python
class CPUOptimizedVectorStore:
    """Vector store otimizado para CPU"""

    def __init__(self):
        # FAISS CPU index
        self.index = faiss.IndexFlatIP(embedding_dim)

        # Intel MKL optimizations se disponível
        if has_mkl():
            faiss.omp_set_num_threads(cpu_count())

    async def add_embeddings(self, embeddings: np.ndarray):
        """Adiciona embeddings ao índice"""
```

- [ ] **Migrar vector store**: FAISS/Chroma para microserviço
- [ ] **Otimizar para CPU**: Configurações específicas de CPU
- [ ] **Implementar cache**: Embeddings pré-computados
- [ ] **Adicionar persistence**: Salvar/carregar índices

### **3.3 Migração das Operações de Busca**
```python
# API de busca no microserviço
@app.post("/api/v1/search")
async def search_documents(query: SearchRequest) -> SearchResponse:
    # 1. Gerar embedding da query
    # 2. Buscar no vector store
    # 3. Re-rank results
    # 4. Retornar documentos relevantes
```

- [ ] **Migrar operações de busca**: Para microserviço
- [ ] **Implementar API de search**: Endpoint dedicado
- [ ] **Otimizar queries**: Cache de resultados similares
- [ ] **Adicionar filtros**: Por tipo, data, relevância

---

## 🔌 **Fase 4: Integração e Comunicação**

### **4.1 Cliente HTTP no Gateway**
```python
class RAGServiceClient:
    """Cliente para comunicar com RAG microserviço"""

    async def enqueue_file(self, file: UploadFile) -> str:
        """Enfileira arquivo para processamento"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.rag_service_url}/api/v1/jobs",
                files={"file": file}
            )
            return response.json()["job_id"]

    async def get_job_status(self, job_id: str) -> dict:
        """Consulta status do job"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.rag_service_url}/api/v1/jobs/{job_id}"
            )
            return response.json()
```

- [ ] **Implementar cliente HTTP**: Para comunicação Gateway ↔ RAG
- [ ] **Adicionar retry logic**: Para falhas de rede
- [ ] **Implementar circuit breaker**: Proteção contra falhas RAG
- [ ] **Configurar timeouts**: Adequados para operações RAG

### **4.2 Sincronização de Estado**
```python
# Estratégias de sincronização
class StateSyncManager:
    async def sync_knowledge_base(self):
        """Sincroniza estado da base de conhecimento"""
        # Verificar arquivos novos/modificados
        # Atualizar índices conforme necessário
        # Notificar gateway sobre mudanças
```

- [ ] **Implementar sincronização**: Estado entre serviços
- [ ] **Adicionar versionamento**: APIs e dados
- [ ] **Implementar graceful degradation**: Quando RAG indisponível
- [ ] **Adicionar event notifications**: Webhooks para eventos RAG

### **4.3 Estratégia de Migração**
```
Fase 1: Dual-write (API + RAG service)
├── Gateway escreve em ambos os sistemas
├── Compara resultados para validação
└── RAG service processa em background

Fase 2: Read from RAG service
├── Gateway lê apenas do RAG service
├── Mantém compatibilidade de APIs
└── RAG service como fonte autoritativa

Fase 3: Remove old implementation
├── Remove código RAG do Gateway
├── RAG service assume todas as operações
└── Cleanup e otimização final
```

- [ ] **Implementar dual-write**: Durante período de migração
- [ ] **Adicionar feature flags**: Para controle gradual
- [ ] **Implementar rollback**: Capacidade de voltar à implementação antiga
- [ ] **Validar consistência**: Dados entre sistemas durante migração

---

## 📊 **Fase 5: Monitoramento e Observabilidade**

### **5.1 Métricas RAG-Specific**
```python
# Métricas do microserviço RAG
rag_metrics = {
    "queue_size": gauge,           # Tamanho da fila
    "processing_time": histogram,  # Tempo de processamento por arquivo
    "embedding_generation": histogram, # Tempo de gerar embeddings
    "search_latency": histogram,   # Latência de buscas
    "index_size": gauge,          # Tamanho do índice vetorial
    "cpu_usage": gauge,           # Uso de CPU
    "memory_usage": gauge         # Uso de memória
}
```

- [ ] **Implementar métricas customizadas**: Prometheus/OpenTelemetry
- [ ] **Adicionar dashboards**: Grafana para métricas RAG
- [ ] **Configurar alertas**: Filas grandes, processamento lento
- [ ] **Logging estruturado**: ELK stack integration

### **5.2 Health Checks Avançados**

```python
class RAGHealthChecker:
    async def comprehensive_check(self) -> HealthReport:
        """Verificações específicas do RAG"""
        return {
            "queue_health": await self.check_queue_health(),
            "index_health": await self.check_index_integrity(),
            "embedding_health": await self.check_embedding_generation(),
            "search_health": await self.check_search_functionality()
        }
```

- [x] **Health checks específicos**: Para componentes RAG
- [x] **Verificação de integridade**: Índices, filas, conectividade
- [ ] **Performance monitoring**: Benchmarks de operações
- [ ] **Anomaly detection**: Padrões anômalos de performance

### **5.3 Estratégia de Rollback**
```python
class RollbackManager:
    async def emergency_rollback(self):
        """Rollback para implementação antiga"""
        # Desabilitar RAG service
        # Reabilitar código antigo no Gateway
        # Restaurar estado consistente
```

- [ ] **Implementar rollback procedures**: Estratégias de emergência
- [ ] **Adicionar circuit breakers**: Proteção automática
- [ ] **Configurar monitoring**: Detecção automática de problemas
- [ ] **Documentar procedures**: Runbooks para operações

---

## 🧪 **Fase 6: Testes e Validação**

### **6.1 Testes de Integração**
```python
class TestRAGMigration:
    async def test_end_to_end_flow(self):
        """Teste completo: upload → processamento → busca"""
        # 1. Upload arquivo via Gateway
        # 2. Verificar enfileiramento
        # 3. Aguardar processamento
        # 4. Buscar conteúdo
        # 5. Validar resultados

    async def test_failure_scenarios(self):
        """Testar cenários de falha"""
        # RAG service indisponível
        # Processamento falha
        # Fila cheia
        # Timeouts
```

- [ ] **Testes end-to-end**: Fluxo completo de migração
- [ ] **Testes de carga**: Performance com múltiplos arquivos
- [ ] **Testes de resiliência**: Cenários de falha
- [ ] **Testes de rollback**: Validação de estratégias de emergência

### **6.2 Testes de Performance**
```python
class PerformanceBenchmark:
    async def benchmark_processing(self):
        """Benchmark de processamento sequencial"""
        # Arquivos de diferentes tamanhos
        # Métricas: tempo, CPU, memória
        # Comparação: antes vs depois da migração
```

- [ ] **Benchmarks**: Performance antes/depois da migração
- [ ] **Load testing**: Capacidade de processamento
- [ ] **Memory profiling**: Otimização de uso de memória
- [ ] **CPU profiling**: Identificação de gargalos

---

## 🚀 **Fase 7: Deploy e Operações**

### **7.1 Estratégia de Deploy**
```yaml
# docker-compose para desenvolvimento
version: '3.8'
services:
  hwa-gateway:
    # API Gateway (sem RAG)

  rag-service:
    # Microserviço RAG independente
    environment:
      - REDIS_URL=redis://redis:6379
      - NEO4J_URI=bolt://neo4j:7687
    depends_on:
      - redis
      - neo4j
```

- [ ] **Containerização**: Docker images separados
- [ ] **Orquestração**: Docker Compose/Kubernetes
- [ ] **CI/CD**: Pipelines separados para cada serviço
- [ ] **Configuração**: Environment variables por serviço

### **7.2 Operações em Produção**
```bash
# Comandos de operação
rag-service start     # Iniciar RAG service
rag-service stop      # Parar graciosamente
rag-service health    # Verificar saúde
rag-service scale 3   # Escalar para 3 instâncias
```

- [ ] **Scripts de operação**: Start/stop/scale
- [ ] **Monitoring**: Dashboards e alertas
- [ ] **Backup/Restore**: Estratégias para índices vetoriais
- [ ] **Logs aggregation**: Centralização de logs

---

## 📅 **Cronograma e Marcos**

### **Semana 1-2: Planejamento e Infraestrutura**

- [x] Análise arquitetural completa
- [x] Design das APIs e contratos
- [x] Implementação da fila Redis
- [x] Setup do microserviço base

### **Semana 3-4: Migração Core**

- [ ] Migração do FileIngestor
- [ ] Migração do vector store
- [ ] Implementação das APIs de busca
- [ ] Integração Gateway ↔ RAG service

### **Semana 5-6: Testes e Validação**

- [ ] Testes end-to-end
- [ ] Testes de performance
- [ ] Validação de cenários de falha
- [ ] Setup de monitoring

### **Semana 7-8: Deploy e Operações**

- [ ] Deploy em staging
- [ ] Validação em produção
- [ ] Documentação operacional
- [ ] Go-live e monitoramento

---

## 🎯 **Critérios de Sucesso**

### **Funcionais**

- [x] **Upload assíncrono**: Usuários não esperam processamento
- [x] **Busca sempre disponível**: Mesmo durante processamento
- [x] **Processamento sequencial**: 1 arquivo por vez, fila organizada
- [x] **APIs compatíveis**: Mesmas interfaces para clientes

### **Não-Funcionais**

- [ ] **Performance**: Latência < 2s para upload, < 500ms para busca
- [ ] **Escalabilidade**: Suporte a 100+ uploads simultâneos
- [ ] **Confiabilidade**: 99.9% uptime, graceful degradation
- [ ] **Observabilidade**: Métricas completas, alertas automáticos

### **Operacionais**

- [ ] **Deploy independente**: RAG evolui sem impactar Gateway
- [ ] **Monitoramento dedicado**: Dashboards RAG específicos
- [ ] **Rollback possível**: Estratégia de emergência validada
- [ ] **Documentação completa**: Runbooks e procedures

---

## 📊 **Métricas de Acompanhamento**

### **KPIs de Migração**

- [ ] **Taxa de sucesso**: % de uploads processados com sucesso
- [ ] **Tempo médio de processamento**: Por tipo de arquivo
- [ ] **Tamanho da fila**: Máximo e médio durante operação
- [ ] **Disponibilidade**: Uptime do RAG service

### **KPIs de Performance**

- [ ] **Latência de upload**: Tempo para resposta inicial
- [ ] **Latência de busca**: Tempo para retornar resultados
- [ ] **Throughput**: Arquivos processados por hora
- [ ] **Uso de recursos**: CPU/Memória por instância

### **KPIs de Qualidade**

- [ ] **Taxa de erro**: Falhas de processamento
- [ ] **Precisão de busca**: Qualidade dos resultados retornados
- [ ] **Satisfação do usuário**: Feedback sobre nova experiência

---

## 🔍 **Riscos e Mitigações**

### **Riscos Técnicos**

1. **Perda de dados**: Mitigação - Dual-write durante migração
2. **Inconsistência**: Mitigação - Validação e testes automatizados
3. **Performance degradation**: Mitigação - Benchmarks e otimização CPU

### **Riscos Operacionais**

1. **Downtime**: Mitigação - Deploy gradual, feature flags
2. **Rollback complexo**: Mitigação - Estratégias de rollback testadas
3. **Monitoramento insuficiente**: Mitigação - Métricas abrangentes desde o início

### **Riscos de Negócio**

1. **Funcionalidades quebradas**: Mitigação - Testes end-to-end rigorosos
2. **Usuários impactados**: Mitigação - Comunicação clara, gradual rollout
3. **Custos aumentados**: Mitigação - Otimização de recursos CPU

---

## 🎉 **Conclusão**

Este plano detalhado estabelece uma **migração segura e estruturada** do RAG para um microserviço independente, otimizado para as restrições de **CPU-only e processamento sequencial**.

A migração será executada em **7 fases distintas**, com **marcos claros**, **critérios de sucesso definidos** e **estratégias de mitigação de riscos**.

O resultado será um sistema **mais escalável, confiável e manutenível**, preparado para crescimento futuro com múltiplas instâncias RAG processando filas independentes.

**Ready to start the implementation?** 🚀

### To-dos

- [x] Mapear dependências RAG: Identificar todos os módulos que interagem com RAG
- [x] Analisar interfaces: Documentar IFileIngestor, IKnowledgeGraph
- [x] Avaliar estado atual: Verificar saúde do sistema RAG existente
- [x] Identificar pontos de integração: APIs, configurações, middlewares
- [x] Definir boundaries: Que funcionalidades ficam no RAG vs API Gateway
- [ ] Design APIs: Contratos REST entre serviços
- [ ] Sistema de filas: Estratégia para processamento sequencial
- [ ] Estratégia de migração: Blue-green ou gradual
- [ ] Definir requisitos não-funcionais: Performance, escalabilidade, confiabilidade, segurança
- [ ] Implementar Redis Queue: Classe para gerenciar fila de jobs
- [ ] Definir estrutura Job: Campos necessários (file_path, metadata, status)
- [ ] Implementar status tracking: Estados (queued, processing, completed, failed)
- [ ] Adicionar timeouts: Prevenção de jobs travados
- [ ] Modificar endpoint /rag/upload: Tornar assíncrono
- [ ] Adicionar endpoint /rag/jobs/{job_id}: Consultar status
- [ ] Implementar RAG client: Cliente HTTP para comunicar com RAG service
- [ ] Adicionar WebSocket notifications: Status updates em tempo real
- [ ] Criar estrutura base: Diretórios e arquivos iniciais
- [ ] Implementar FastAPI app: Servidor independente para RAG
- [ ] Configurar dependências: Poetry/pyproject.toml separado
- [ ] Implementar health checks: Próprios do RAG service
- [ ] Migrar FileIngestor: Para o microserviço RAG
- [ ] Adaptar para processamento sequencial: Remover paralelização
- [ ] Otimizar para CPU: Usar bibliotecas CPU-optimized
- [ ] Adicionar logging detalhado: Progresso do processamento
- [ ] Migrar vector store: FAISS/Chroma para microserviço
- [ ] Otimizar para CPU: Configurações específicas de CPU
- [ ] Implementar cache: Embeddings pré-computados
- [ ] Adicionar persistence: Salvar/carregar índices
- [ ] Migrar operações de busca: Para microserviço
- [ ] Implementar API de search: Endpoint dedicado
- [ ] Otimizar queries: Cache de resultados similares
- [ ] Adicionar filtros: Por tipo, data, relevância
- [ ] Implementar cliente HTTP: Para comunicação Gateway ↔ RAG
- [ ] Adicionar retry logic: Para falhas de rede
- [ ] Implementar circuit breaker: Proteção contra falhas RAG
- [ ] Configurar timeouts: Adequados para operações RAG
- [ ] Implementar sincronização: Estado entre serviços
- [ ] Adicionar versionamento: APIs e dados
- [ ] Implementar graceful degradation: Quando RAG indisponível
- [ ] Adicionar event notifications: Webhooks para eventos RAG
- [ ] Implementar dual-write: Durante período de migração
- [ ] Adicionar feature flags: Para controle gradual
- [ ] Implementar rollback: Capacidade de voltar à implementação antiga
- [ ] Validar consistência: Dados entre sistemas durante migração
- [ ] Implementar métricas customizadas: Prometheus/OpenTelemetry
- [ ] Adicionar dashboards: Grafana para métricas RAG
- [ ] Configurar alertas: Filas grandes, processamento lento
- [ ] Logging estruturado: ELK stack integration
- [ ] Health checks específicos: Para componentes RAG
- [ ] Verificação de integridade: Índices, filas, conectividade
- [ ] Performance monitoring: Benchmarks de operações
- [ ] Anomaly detection: Padrões anômalos de performance
- [ ] Implementar rollback procedures: Estratégias de emergência
- [ ] Adicionar circuit breakers: Proteção automática
- [ ] Configurar monitoring: Detecção automática de problemas
- [ ] Documentar procedures: Runbooks para operações
- [ ] Testes end-to-end: Fluxo completo de migração
- [ ] Testes de carga: Performance com múltiplos arquivos
- [ ] Testes de resiliência: Cenários de falha
- [ ] Testes de rollback: Validação de estratégias de emergência
- [ ] Benchmarks: Performance antes/depois da migração
- [ ] Load testing: Capacidade de processamento
- [ ] Memory profiling: Otimização de uso de memória
- [ ] CPU profiling: Identificação de gargalos
- [ ] Containerização: Docker images separados
- [ ] Orquestração: Docker Compose/Kubernetes
- [ ] CI/CD: Pipelines separados para cada serviço
- [ ] Configuração: Environment variables por serviço
- [ ] Scripts de operação: Start/stop/scale
- [ ] Monitoring: Dashboards e alertas
- [ ] Backup/Restore: Estratégias para índices vetoriais
- [ ] Logs aggregation: Centralização de logs




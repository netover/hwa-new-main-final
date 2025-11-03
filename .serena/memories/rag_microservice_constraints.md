Restrições de Hardware para Microserviço RAG:

**Hardware**: CPU-only (sem GPU disponível)
- Não há aceleração GPU para embeddings
- Processamento limitado a recursos CPU
- Escalabilidade vertical (mais CPUs) vs horizontal (GPUs)

**Implicações Arquiteturais**:
- Usar bibliotecas otimizadas para CPU (FAISS CPU, ONNX, Intel MKL)
- Otimizar para throughput de CPU ao invés de latência de GPU
- Estratégia de cache mais agressiva para compensar processamento
- Possível uso de múltiplas instâncias CPU para escalabilidade horizontal

**Vantagens que permanecem**:
- Isolamento de falhas
- Deploy independente
- Especialização tecnológica (mesmo em CPU)
- Gerenciamento separado
- Testabilidade isolada



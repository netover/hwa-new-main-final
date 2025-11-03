Restrições de Processamento RAG:

**Processamento**: Sequencial (1 arquivo por vez)
- Arquivos são processados um após o outro
- Não há paralelização no nível de arquivo
- Arquivos restantes ficam em fila de espera
- Processamento pode ser demorado (PDFs grandes, embeddings)

**Implicações Arquiteturais**:
- Microserviço RAG precisa gerenciar fila de processamento
- API principal deve ser assíncrona (não bloquear no upload)
- Status de processamento deve ser consultável
- Possível processamento em background

**Benefícios da Separação**:
- API responde imediatamente ao upload
- RAG processa em background sem bloquear usuários
- Fila gerenciada independentemente
- Status de processamento consultável via API
- Escalabilidade: múltiplas instâncias processando filas diferentes



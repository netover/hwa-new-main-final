# Guia de Troubleshooting do Resync

Este documento serve como um guia de referência para diagnosticar e resolver erros comuns que podem ocorrer na aplicação Resync. Os erros são categorizados com base na hierarquia de exceções customizadas do projeto.

## 1. Erros de Configuração (`ConfigError`)

Erros desta categoria geralmente ocorrem durante a inicialização da aplicação e estão relacionados a arquivos de configuração (`settings.toml`, `.env`) ou variáveis de ambiente.

---

### 1.1 `MissingConfigError`

- **Erro de Exemplo no Log**: `CRITICAL: Missing or empty required settings: TWS_HOST, TWS_USER`
- **Causa Provável**: Uma ou mais variáveis de ambiente ou configurações essenciais não foram definidas. O `main.py` realiza uma validação no startup e falha se variáveis críticas estiverem ausentes.
- **Solução**:
  1. Verifique se o arquivo `.env` existe na raiz do projeto e está sendo carregado corretamente.
  2. Certifique-se de que todas as variáveis necessárias (como `TWS_HOST`, `TWS_USER`, `TWS_PASSWORD`, `LLM_ENDPOINT`, etc.) estão definidas no seu arquivo `.env` ou como variáveis de ambiente no seu sistema de produção.
  3. Consulte o arquivo `settings.toml` para ver a lista completa de configurações e seus valores padrão.

---

### 1.2 `InvalidConfigError`

- **Erro de Exemplo no Log**: `CRITICAL: Invalid TWS_PORT: 'abc' (must be integer 1-65535)`
- **Causa Provável**: O valor de uma configuração é inválido (ex: uma porta definida como texto em vez de número, ou um `APP_ENV` inválido).
- **Solução**:
  1. Revise o valor da configuração mencionada no log de erro.
  2. Corrija o tipo ou o valor para que corresponda ao formato esperado (ex: `TWS_PORT` deve ser um número inteiro).

---

### 1.3 `DataParsingError` (em `agent_manager.py`)

- **Erro de Exemplo no Log**: `ERROR: Error decoding JSON from config/runtime.json: ...`
- **Causa Provável**: O arquivo de configuração dos agentes (`agents.json` ou `runtime.json`) contém um erro de sintaxe JSON (ex: uma vírgula a mais, aspas faltando).
- **Solução**:
  1. Abra o arquivo de configuração dos agentes.
  2. Use um validador de JSON (como os disponíveis em editores de código como VS Code ou online) para encontrar e corrigir o erro de sintaxe.

## 2. Erros de Rede (`NetworkError`)

Estes erros ocorrem durante a comunicação com serviços externos, como a API do TWS, o LLM ou o banco de dados Neo4j.

---

### 2.1 `ConnectionFailedError` / `APIError` (em `tws_service.py`)

- **Erro de Exemplo no Log**: `ERROR: HTTP error occurred: 503 - Service Unavailable` ou `ERROR: Network error during API request: [Errno 111] Connection refused`
- **Causa Provável**:
  - O servidor do TWS está offline ou inacessível a partir da máquina onde o Resync está rodando.
  - As configurações de `TWS_HOST` ou `TWS_PORT` estão incorretas.
  - Há um firewall bloqueando a conexão.
- **Solução**:
  1. Verifique se o serviço do TWS está ativo.
  2. Confirme se as variáveis de ambiente `TWS_HOST` e `TWS_PORT` estão corretas.
  3. Teste a conectividade da máquina do Resync para o host do TWS usando ferramentas como `ping` ou `telnet`.

---

### 2.2 `LLMError` (em `ia_auditor.py` ou `knowledge_graph.py`)

- **Erro de Exemplo no Log**: `ERROR: IA Auditor: LLM analysis failed: ...` ou `ERROR: LLM API returned an error status during Text-to-Cypher: 401 Unauthorized`
- **Causa Provável**:
  - A chave de API do LLM (`LLM_API_KEY`) está incorreta ou expirou.
  - O endpoint do LLM (`LLM_ENDPOINT`) está incorreto ou o serviço está offline.
  - O modelo especificado (`AUDITOR_MODEL_NAME` ou `AGENT_MODEL_NAME`) não existe ou não está disponível.
- **Solução**:
  1. Verifique se o serviço do LLM (ex: Ollama, API da OpenAI) está em execução e acessível.
  2. Confirme se a `LLM_API_KEY` e o `LLM_ENDPOINT` estão configurados corretamente no seu `.env`.
  3. Verifique se os nomes dos modelos estão corretos e disponíveis no provedor de LLM.

---

### 2.3 `WebSocketError` (em `chat.py`)

- **Erro de Exemplo no Log**: `INFO: Client disconnected from agent 'tws-specialist'.` (Normal) ou `CRITICAL: Unexpected critical error in WebSocket for agent 'tws-specialist'` (Anormal).
- **Causa Provável**:
  - O cliente (frontend) fechou a conexão WebSocket.
  - Perda de conectividade de rede entre o cliente e o servidor.
  - Um erro não tratado no backend quebrou a conexão.
- **Solução**:
  1. Se a desconexão for normal, nenhuma ação é necessária.
  2. Se for um erro crítico, analise o log `exc_info=True` para identificar a causa raiz do problema no backend. Pode ser um erro em um dos serviços chamados pelo endpoint do chat.

## 3. Erros de Processamento (`ProcessingError`)

Erros relacionados à lógica de negócio interna da aplicação.

---

### 3.1 `FileProcessingError` (em `file_ingestor.py`)

- **Erro de Exemplo no Log**: `CRITICAL: Unexpected error reading PDF ...` ou `ERROR: Failed to process document ...`
- **Causa Provável**:
  - O arquivo sendo processado está corrompido ou em um formato inválido (ex: um arquivo `.txt` renomeado para `.pdf`).
  - A biblioteca usada para ler o arquivo (ex: `pypdf`) encontrou um problema interno.
  - Permissões de leitura ausentes para o arquivo no sistema de arquivos.
- **Solução**:
  1. Verifique a integridade do arquivo que causou o erro. Tente abri-lo manualmente.
  2. Certifique-se de que a aplicação Resync tem as permissões de leitura necessárias para o diretório `rag_base_data/`.
  3. Se o erro persistir com um arquivo válido, pode ser um bug na biblioteca de leitura. Considere atualizar a biblioteca ou reportar o problema.

---

### 3.2 `AuditError` (em `ia_auditor.py` ou `audit_lock.py`)

- **Erro de Exemplo no Log**: `WARNING: IA Auditor: Could not acquire lock for memory ...` ou `CRITICAL: Unexpected critical error cleaning up expired audit locks.`
- **Causa Provável**:
  - **Falha ao adquirir lock**: Múltiplos processos do `IAAuditor` tentaram analisar a mesma memória ao mesmo tempo. O sistema de lock funcionou como esperado, e apenas um processo continuou.
  - **Erro na limpeza de locks**: Um problema de conexão com o Redis ou um erro inesperado ocorreu durante a limpeza de locks expirados.
- **SoluÇÃO**:
  1. **Falha ao adquirir lock**: Geralmente é um aviso (`WARNING`) e não requer ação imediata, pois o sistema se auto-corrige. Se ocorrer com muita frequência, pode indicar alta contenção, e o número de workers do `IAAuditor` pode precisar de ajuste.
  2. **Erro na limpeza**: Verifique a saúde do serviço Redis. Se o Redis estiver funcionando, o log `CRITICAL` indica um bug que precisa ser investigado pela equipe de desenvolvimento.

---

### 3.3 `DatabaseError` (em `knowledge_graph.py` ou `audit_queue.py`)

- **Erro de Exemplo no Log**: `ERROR: IA Auditor: Could not fetch memories from the database: ...` ou `ERROR: Redis error during lock release: ...`
- **Causa Provável**:
  - O serviço do Neo4j ou Redis está offline.
  - As credenciais ou URL de conexão (`NEO4J_URI`, `REDIS_URL`) estão incorretas.
  - Um erro de sintaxe em uma query Cypher gerada pelo LLM.
- **Solução**:
  1. Verifique o status dos serviços Neo4j e Redis.
  2. Confirme se as URLs de conexão e credenciais no arquivo `.env` estão corretas.
  3. Se o erro for relacionado a uma query Cypher, o log geralmente mostrará a query inválida. Isso pode indicar um problema com o prompt do LLM ou com o modelo sendo usado para gerar as queries.



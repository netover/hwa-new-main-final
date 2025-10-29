# ✅ Checklist de Deployment para Produção - Resync

Este documento serve como um guia passo a passo para implantar a aplicação Resync em um ambiente de produção. Siga cada etapa cuidadosamente para garantir uma implantação segura e bem-sucedida.

---

## 1. Preparação do Ambiente (Pre-Deployment)

- [ ] **Servidor de Produção**: Provisionar um servidor (VM ou container) com Python 3.13+ e acesso à internet.

- [ ] **Serviços Externos**: Garantir que as seguintes dependências externas estejam acessíveis a partir do servidor de produção:
  - [ ] **Neo4j**: Instância do banco de dados Neo4j em execução e acessível.
  - [ ] **Redis**: Instância do Redis em execução para cache, locks e rate limiting.
  - [ ] **TWS API**: Conectividade de rede com o host e a porta da API do HCL Workload Automation.
  - [ ] **LLM Endpoint**: Conectividade com o endpoint do Large Language Model (seja local, como Ollama, ou na nuvem, como OpenAI/OpenRouter).

- [ ] **Configuração de Firewall**:
  - [ ] Abrir a porta da aplicação (ex: `8000`) para tráfego de entrada.
  - [ ] Garantir que o tráfego de saída para os serviços externos (Neo4j, Redis, TWS, LLM) seja permitido.

- [ ] **Arquivo de Configuração (`.env`)**:
  - [ ] Criar um arquivo `.env` no diretório raiz da aplicação no servidor. **Não comite este arquivo no Git.**
  - [ ] Definir `APP_ENV=production`.
  - [ ] Preencher **TODAS** as credenciais e segredos com valores de produção:
    - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
    - `REDIS_URL`
    - `TWS_HOST`, `TWS_PORT`, `TWS_USER`, `TWS_PASSWORD`
    - `LLM_ENDPOINT`, `LLM_API_KEY` (se aplicável)
    - `ADMIN_USERNAME`, `ADMIN_PASSWORD` (usar valores fortes e únicos)
  - [ ] Revisar e ajustar os parâmetros de performance no `settings.production.toml` ou via variáveis de ambiente, como `TWS_MAX_CONNECTIONS`, `TWS_READ_TIMEOUT`, etc.

---

## 2. Processo de Implantação (Deployment)

- [ ] **Código Fonte**: No servidor, clone a versão estável mais recente da branch `main` do repositório Git.
  ```bash
  git clone https://github.com/your-repo/hwa-new.git
  cd hwa-new
  ```

- [ ] **Ambiente Virtual**: Crie e ative um ambiente virtual Python para isolar as dependências.
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```

- [ ] **Instalação de Dependências**: Instale as bibliotecas necessárias a partir do `requirements/prod.txt` (produção) ou `requirements/dev.txt` (desenvolvimento).
  ```bash
  pip install -r requirements/prod.txt
  ```

---

## 3. Execução e Verificação (Post-Deployment)

- [ ] **Gerenciador de Processos**: Configure um gerenciador de processos robusto como `systemd` ou `gunicorn` para executar a aplicação. Isso garante que a aplicação reinicie automaticamente em caso de falha.
  - **Exemplo com `gunicorn` e `uvicorn`**:
    ```bash
    gunicorn -w 4 -k uvicorn.workers.UvicornWorker resync.main:app --bind 0.0.0.0:8000
    ```
    *(Onde `-w 4` define 4 processos de trabalho. Ajuste conforme os núcleos de CPU do seu servidor.)*

- [ ] **Iniciar a Aplicação**: Inicie a aplicação usando o gerenciador de processos configurado.

- [ ] **Verificação de Logs**: Monitore os logs de startup para garantir que não há erros de configuração ou conexão. A aplicação deve registrar a inicialização bem-sucedida dos serviços.

- [ ] **Health Checks**: Verifique os endpoints de saúde da aplicação para confirmar que tudo está operacional.
  - [ ] **Health Geral**: Acesse `http://<seu_servidor>:8000/api/health`. A resposta deve ser `{"status": "ok"}`.
  - [ ] **Configuração**: Acesse `http://<seu_servidor>:8000/api/config`. Verifique se as configurações carregadas correspondem ao ambiente de produção.

---

## 4. Manutenção e Monitoramento

- [ ] **Monitoramento de Logs**: Configure um sistema de agregação de logs (ex: ELK Stack, Graylog, Datadog) para monitorar os logs da aplicação em tempo real e criar alertas para erros críticos.

- [ ] **Métricas Prometheus**: Integre o endpoint `/api/metrics` com uma instância do Prometheus para monitorar a saúde e a performance da aplicação (ex: contagem de agentes, latência de requisições).

- [ ] **Procedimento de Invalidação de Cache**: Documente e comunique à equipe de operações como usar o endpoint `POST /api/v1/cache/invalidate` com as credenciais de administrador para forçar a atualização de dados do TWS quando necessário.
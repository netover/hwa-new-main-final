#!/bin/bash

# ==============================================================================
# Script para Invalidar o Cache da Aplicação Resync
#
# Este script é projetado para ser executado por um cron job para limpar
# periodicamente o cache de dados do TWS, garantindo que a aplicação
# busque dados frescos.
# ==============================================================================

# --- Configuração ---
# O diretório onde o seu arquivo .env está localizado.
# Este script assume que ele está na raiz do projeto.
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
ENV_FILE="$PROJECT_DIR/.env"

# O URL do endpoint de invalidação de cache.
INVALIDATE_URL="http://localhost:8000/api/v1/cache/invalidate?scope=system"

# --- Lógica ---

# Verifica se o arquivo .env existe
if [ ! -f "$ENV_FILE" ]; then
  echo "Erro: Arquivo .env não encontrado em $ENV_FILE" >&2
  exit 1
fi

# Carrega as variáveis de ambiente do arquivo .env
set -a # Exporta automaticamente as variáveis lidas
source "$ENV_FILE"
set +a

# Executa o comando curl para invalidar o cache
# -s: Modo silencioso (sem barra de progresso)
# -f: Falha silenciosamente (não mostra erro HTTP, mas retorna um código de saída diferente de zero)
curl -sf -X POST "$INVALIDATE_URL" -u "$ADMIN_USERNAME:$ADMIN_PASSWORD"
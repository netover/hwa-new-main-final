"""
Script para Popular a Base de Conhecimento (Knowledge Graph).

Este script varre os diretórios configurados em `settings.KNOWLEDGE_BASE_DIRS`,
processa todos os arquivos suportados (PDF, DOCX, etc.) e ingere seu conteúdo
no Knowledge Graph usando o FileIngestor.

É ideal para inicializar o sistema com uma base de conhecimento existente
ou para atualizá-lo em lote.

Como usar:
1. Certifique-se de que seu ambiente virtual está ativado.
2. Configure os diretórios desejados em `settings.toml` na variável `KNOWLEDGE_BASE_DIRS`.
   Exemplo: `KNOWLEDGE_BASE_DIRS = ["rag_base_data/"]`
3. Execute o script a partir da raiz do projeto:
   `python -m scripts.populate_knowledge_base`
"""

from __future__ import annotations

import asyncio
import logging

# Adiciona o diretório raiz ao sys.path para permitir importações relativas
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from resync.core.file_ingestor import FileIngestor, load_existing_rag_documents
from resync.core.interfaces import IKnowledgeGraph
from resync.core.knowledge_graph import AsyncKnowledgeGraph

# Configuração do logging para exibir o progresso
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Função principal que inicializa os serviços e inicia o processo de ingestão.
    """
    logger.info("Iniciando o script para popular a base de conhecimento...")
    knowledge_graph: IKnowledgeGraph
    try:
        # 1. Inicializa o Knowledge Graph
        knowledge_graph = AsyncKnowledgeGraph()  # type: ignore[no-untyped-call]
        logger.info("Knowledge Graph inicializado.")

        # 2. Inicializa o File Ingestor com a dependência do Knowledge Graph
        file_ingestor = FileIngestor(knowledge_graph=knowledge_graph)
        logger.info("File Ingestor inicializado.")

        # 3. Chama a função para carregar e processar os documentos
        processed_count = await load_existing_rag_documents(file_ingestor)
        logger.info(
            f"Processo de ingestão concluído. {processed_count} documentos foram processados."
        )

    finally:
        # 4. Garante que a conexão com o banco de dados seja fechada
        if knowledge_graph and hasattr(knowledge_graph, "close"):
            await knowledge_graph.close()  # type: ignore[no-untyped-call]
            logger.info("Conexão com o Knowledge Graph fechada.")


if __name__ == "__main__":
    asyncio.run(main())

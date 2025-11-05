#!/usr/bin/env python3
"""
Script para corrigir imports nos arquivos migrados
"""

import re
from pathlib import Path


def fix_imports_in_file(
    file_path: Path, old_import: str, new_import: str
) -> None:
    """Corrige imports em um arquivo específico."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Substitui o import antigo pelo novo
        updated_content = re.sub(
            rf"from\s+{re.escape(old_import)}\s+",
            f"from {new_import} ",
            content,
        )

        updated_content = re.sub(
            rf"import\s+{re.escape(old_import)}",
            f"import {new_import}",
            updated_content,
        )

        # Se houver mudanças, escreve no arquivo
        if updated_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"Atualizado: {file_path}")
        else:
            print(f"Sem mudanças necessárias em: {file_path}")
    except Exception as exc:  # noqa: BLE001 - log genérico do script
        print(f"Erro ao atualizar {file_path}: {exc}")


def fix_all_imports() -> None:
    """Corrige todos os imports nos arquivos migrados."""

    # Mapeamento de imports antigos para novos
    import_mappings = [
        # Configurações
        ("resync.settings", "resync.config.settings"),

        # Utilitários
        ("resync.core.simple_logger", "resync.utils.simple_logger"),
        ("resync.core.exceptions", "resync.utils.exceptions"),
        ("resync.core.interfaces", "resync.utils.interfaces"),

        # Componentes Core
        (
            "resync.core.connection_pool_manager",
            "resync.core.connection_pool_manager",
        ),
        ("resync.core.metrics", "resync.core.monitoring.metrics"),
        ("resync.core.fastapi_di", "resync.core.fastapi_di"),
        (
            "resync.core.circuit_breaker",
            "resync.core.monitoring.circuit_breaker",
        ),

        # Cache
        ("resync.core.cache", "resync.core.cache"),

        # Modelos e Saúde
        ("resync.core.health_models", "resync.models.health_models"),
        ("resync.core.health", "resync.core.health"),
    ]

    # Corrigir imports em todos os arquivos Python na nova estrutura
    for file_path in Path("resync").rglob("*.py"):
        if "__pycache__" in str(file_path):
            continue

        for old_import, new_import in import_mappings:
            fix_imports_in_file(file_path, old_import, new_import)


def main() -> None:
    """Função principal."""
    print("Corrigindo imports nos arquivos migrados...")
    fix_all_imports()
    print("Correção de imports concluída!")

if __name__ == "__main__":
    main()

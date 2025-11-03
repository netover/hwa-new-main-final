#!/usr/bin/env python3
"""
Script para atualizar imports após migração de arquivos para nova estrutura
"""

import os
import re
from pathlib import Path

def update_imports_in_file(file_path: Path, old_import: str, new_import: str):
    """Atualiza imports em um arquivo específico"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Substitui o import antigo pelo novo
        updated_content = re.sub(
            rf'from\s+{re.escape(old_import)}\s+',
            f'from {new_import} ',
            content
        )
        
        updated_content = re.sub(
            rf'import\s+{re.escape(old_import)}',
            f'import {new_import}',
            updated_content
        )
        
        # Se houver mudanças, escreve no arquivo
        if updated_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"Atualizado: {file_path}")
        else:
            print(f"Sem mudanças necessárias em: {file_path}")
    except Exception as e:
        print(f"Erro ao atualizar {file_path}: {e}")

def update_all_imports_in_directory(directory: Path):
    """Atualiza todos os imports em um diretório"""
    # Mapeamento de imports antigos para novos
    import_mappings = [
        # Configurações
        ("resync.settings", "resync.config.settings"),
        
        # Utilitários
        ("resync.core.simple_logger", "resync.utils.simple_logger"),
        ("resync.core.exceptions", "resync.utils.exceptions"),
        ("resync.core.interfaces", "resync.utils.interfaces"),
        
        # Componentes Core
        ("resync.core.connection_pool_manager", "resync.core.connection_pool_manager"),
        ("resync.core.metrics", "resync.core.monitoring.metrics"),
        ("resync.core.fastapi_di", "resync.core.fastapi_di"),
        ("resync.core.circuit_breaker", "resync.core.monitoring.circuit_breaker"),
        
        # Cache
        ("resync.core.cache", "resync.core.cache"),
        
        # Modelos e Saúde
        ("resync.core.health_models", "resync.models.health_models"),
        ("resync.core.health", "resync.core.health"),
    ]
    
    # Atualizar imports em todos os arquivos Python
    for file_path in directory.rglob("*.py"):
        if "__pycache__" not in str(file_path):
            for old_import, new_import in import_mappings:
                update_imports_in_file(file_path, old_import, new_import)

def main():
    """Função principal"""
    print("Atualizando imports após migração...")
    
    # Atualizar imports na nova estrutura
    update_all_imports_in_directory(Path("resync"))
    
    # Atualizar imports na estrutura original para apontar para a nova
    update_all_imports_in_directory(Path("resync"))
    
    print("Atualização de imports concluída!")

if __name__ == "__main__":
    main()






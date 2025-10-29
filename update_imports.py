#!/usr/bin/env python3
"""
Script para atualizar imports após reestruturação de diretórios
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
            f'from {new_import}',
            content
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

def main():
    """Função principal"""
    print("Atualizando imports após reestruturação...")
    
    # Atualizar imports em arquivos principais
    update_mappings = [
        # Arquivos que podem importar health service
        ("resync/main.py", "resync.core.health.health_service", "resync.core.health.health_service_consolidated"),
        ("resync/api/health.py", "resync.core.health.health_service", "resync.core.health.health_service_consolidated"),
        
        # Arquivos que podem importar cache
        ("resync/main.py", "resync.core.cache", "resync.core.cache.unified_cache"),
        ("resync/api/cache.py", "resync.core.cache", "resync.core.cache.unified_cache"),
        
        # Arquivos que podem importar segurança
        ("resync/main.py", "resync.core.security", "resync.core.security"),
        ("resync/api/security.py", "resync.core.security", "resync.core.security"),
        
        # Arquivos que podem importar configurações
        ("resync/main.py", "resync.config", "resync.config"),
        ("resync/api/health.py", "resync.config", "resync.config"),
    ]
    
    # Aplicar atualizações
    for file_path, old_import, new_import in update_mappings:
        update_imports_in_file(file_path, old_import, new_import)
    
    print("Atualização de imports concluída!")

if __name__ == "__main__":
    main()

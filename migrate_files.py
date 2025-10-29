#!/usr/bin/env python3
"""
Script para migrar arquivos de forma segura, evitando problemas de codificação
"""

import os
import shutil
from pathlib import Path

def copy_file_safely(src: Path, dst: Path):
    """Copia um arquivo de forma segura, preservando codificação"""
    try:
        # Criar diretório de destino se não existir
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Ler arquivo de origem como bytes
        with open(src, 'rb') as f:
            content_bytes = f.read()
        
        # Escrever no destino como bytes
        with open(dst, 'wb') as f:
            f.write(content_bytes)
        
        print(f"Copiado: {src} -> {dst}")
        return True
    except Exception as e:
        print(f"Erro ao copiar {src}: {e}")
        return False

def copy_directory_safely(src: Path, dst: Path):
    """Copia um diretório de forma segura"""
    try:
        # Criar diretório de destino se não existir
        dst.mkdir(parents=True, exist_ok=True)
        
        # Copiar todos os arquivos do diretório
        for item in src.iterdir():
            src_item = src / item.name
            
            if src_item.is_file():
                dst_item = dst / item.name
                copy_file_safely(src_item, dst_item)
            elif src_item.is_dir() and item.name != "__pycache__":
                dst_item = dst / item.name
                copy_directory_safely(src_item, dst_item)
        
        return True
    except Exception as e:
        print(f"Erro ao copiar diretório {src}: {e}")
        return False

def create_directory_structure():
    """Cria a estrutura de diretórios da nova organização"""
    directories = [
        "resync_new/api/v1",
        "resync_new/core/cache",
        "resync_new/core/health",
        "resync_new/core/security",
        "resync_new/core/monitoring",
        "resync_new/config",
        "resync_new/models",
        "resync_new/services",
        "resync_new/utils",
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Criado diretório: {directory}")

def migrate_critical_files():
    """Migra os arquivos críticos identificados na análise de dependências"""
    # Mapeamento de arquivos críticos
    critical_files = [
        # Configurações
        ("resync/settings.py", "resync_new/config/settings.py"),
        
        # Utilitários
        ("resync/core/simple_logger.py", "resync_new/utils/simple_logger.py"),
        ("resync/core/exceptions.py", "resync_new/utils/exceptions.py"),
        ("resync/core/interfaces.py", "resync_new/utils/interfaces.py"),
        
        # Componentes Core
        ("resync/core/connection_pool_manager.py", "resync_new/core/connection_pool_manager.py"),
        ("resync/core/metrics.py", "resync_new/core/monitoring/metrics.py"),
        ("resync/core/fastapi_di.py", "resync_new/core/fastapi_di.py"),
        ("resync/core/circuit_breaker.py", "resync_new/core/monitoring/circuit_breaker.py"),
        
        # Modelos e Saúde
        ("resync/core/health_models.py", "resync_new/models/health_models.py"),
    ]
    
    success_count = 0
    total_count = len(critical_files)
    
    for src_path, dst_path in critical_files:
        src = Path(src_path)
        dst = Path(dst_path)
        
        if src.exists():
            if src.is_file():
                if copy_file_safely(src, dst):
                    success_count += 1
            elif src.is_dir():
                if copy_directory_safely(src, dst):
                    success_count += 1
        else:
            print(f"Arquivo não encontrado: {src}")
    
    print(f"\nArquivos críticos copiados: {success_count}/{total_count}")
    return success_count == total_count

def migrate_directories():
    """Migra diretórios inteiros"""
    directories = [
        ("resync/core/cache", "resync_new/core/cache"),
        ("resync/core/health", "resync_new/core/health"),
        ("resync/core/security.py", "resync_new/core/security/security.py"),
        ("resync/config", "resync_new/config"),
        ("resync/models", "resync_new/models"),
        ("resync/services", "resync_new/services"),
        ("resync/core/utils", "resync_new/utils"),
        ("resync/api", "resync_new/api"),
    ]
    
    success_count = 0
    total_count = len(directories)
    
    for src_path, dst_path in directories:
        src = Path(src_path)
        dst = Path(dst_path)
        
        if src.exists():
            if src.is_file():
                if copy_file_safely(src, dst):
                    success_count += 1
            elif src.is_dir():
                if copy_directory_safely(src, dst):
                    success_count += 1
        else:
            print(f"Arquivo não encontrado: {src}")
    
    print(f"\nDiretórios copiados: {success_count}/{total_count}")
    return success_count == total_count

def create_init_files():
    """Cria arquivos __init__.py para os diretórios"""
    init_files = [
        "resync_new/api/__init__.py",
        "resync_new/api/v1/__init__.py",
        "resync_new/core/__init__.py",
        "resync_new/core/cache/__init__.py",
        "resync_new/core/health/__init__.py",
        "resync_new/core/security/__init__.py",
        "resync_new/core/monitoring/__init__.py",
        "resync_new/config/__init__.py",
        "resync_new/models/__init__.py",
        "resync_new/services/__init__.py",
        "resync_new/utils/__init__.py",
    ]
    
    for init_file in init_files:
        Path(init_file).touch(exist_ok=True)
        print(f"Criado: {init_file}")

def main():
    """Função principal"""
    print("Iniciando migração segura de arquivos...")
    
    # Criar estrutura de diretórios
    print("\n=== Criando Estrutura de Diretórios ===")
    create_directory_structure()
    
    # Migrar arquivos críticos
    print("\n=== Migrando Arquivos Críticos ===")
    critical_files_ok = migrate_critical_files()
    
    # Migrar diretórios
    print("\n=== Migrando Diretórios ===")
    directories_ok = migrate_directories()
    
    # Criar arquivos __init__.py
    print("\n=== Criando Arquivos __init__.py ===")
    create_init_files()
    
    # Resumo
    print("\n=== Resumo da Migração ===")
    print(f"Arquivos Críticos: {'✓ OK' if critical_files_ok else '✗ FALHOU'}")
    print(f"Diretórios: {'✓ OK' if directories_ok else '✗ FALHOU'}")
    
    if critical_files_ok and directories_ok:
        print("\n🎉 Migração concluída com sucesso!")
        return 0
    else:
        print("\n❌ Migração falhou. Verifique os erros acima.")
        return 1

if __name__ == "__main__":
    exit(main())

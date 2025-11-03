#!/usr/bin/env python3
"""
Script para substituir estrutura antiga pela nova após validação
"""

import os
import shutil
from pathlib import Path

def backup_and_replace_structure():
    """Faz backup da estrutura antiga e substitui pela nova"""
    try:
        # Criar backup da estrutura antiga
        backup_dir = Path(f"resync_backup_{get_timestamp()}")
        print(f"Criando backup em: {backup_dir}")
        
        if Path("resync").exists():
            shutil.copytree("resync", backup_dir)
            print(f"Backup criado com sucesso em: {backup_dir}")
        else:
            print("Diretório resync não encontrado!")
            return False
        
        # Remover estrutura antiga
        print("Removendo estrutura antiga...")
        if Path("resync").exists():
            shutil.rmtree("resync")
            print("Estrutura antiga removida")
        
        # Renomear nova estrutura para antiga
        print("Renomeando nova estrutura para resync...")
        if Path("resync").exists():
            shutil.move("resync", "resync")
            print("Nova estrutura renomeada para resync com sucesso")
        else:
            print("Diretório resync não encontrado!")
            return False
        
        return True
    except Exception as e:
        print(f"Erro ao substituir estrutura: {e}")
        return False

def get_timestamp():
    """Gera timestamp para backup"""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def main():
    """Função principal"""
    print("Substituindo estrutura antiga pela nova...")
    
    if backup_and_replace_structure():
        print("\n🎉 Estrutura substituída com sucesso!")
        return 0
    else:
        print("\n❌ Falha ao substituir estrutura.")
        return 1

if __name__ == "__main__":
    exit(main())







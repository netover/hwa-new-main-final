#!/usr/bin/env python3
"""
Script de limpeza para arquivos não utilizados no projeto resync/
Gerado em 2025-10-26 15:24:56

AVISO: Execute este script apenas após revisar os arquivos listados abaixo!
"""

import os
import shutil
from pathlib import Path

def backup_file(file_path: Path) -> None:
    """Cria um backup do arquivo antes de remover"""
    backup_path = Path(f"{file_path}.backup")
    shutil.copy2(file_path, backup_path)
    print(f"Backup criado: {backup_path}")

def remove_file(file_path: Path) -> None:
    """Remove o arquivo após criar backup"""
    if file_path.exists():
        backup_file(file_path)
        file_path.unlink()
        print(f"Arquivo removido: {file_path}")
    else:
        print(f"Arquivo não encontrado: {file_path}")

def main():
    """Função principal"""
    print("Iniciando limpeza de arquivos não utilizados...\n")

    # resync\settings_legacy.py
    remove_file(Path("resync/settings_legacy.py"))

    print("\nLimpeza concluída!")

if __name__ == "__main__":
    main()

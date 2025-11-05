#!/usr/bin/env python3
"""Ferramenta para migrar arquivos com segurança e preservar a codificação."""

from pathlib import Path


def copy_file_safely(src: Path, dst: Path) -> bool:
    """Copia um arquivo de forma segura, preservando a codificação."""

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)

        with open(src, "rb") as source_file:
            content_bytes = source_file.read()

        with open(dst, "wb") as target_file:
            target_file.write(content_bytes)

        print(f"Copiado: {src} -> {dst}")
        return True
    except OSError as exc:
        print(f"Erro ao copiar {src}: {exc}")
    return False


def copy_directory_safely(src: Path, dst: Path) -> bool:
    """Copia um diretório de forma segura."""

    try:
        dst.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            src_item = src / item.name

            if src_item.is_file():
                dst_item = dst / item.name
                copy_file_safely(src_item, dst_item)
            elif src_item.is_dir() and item.name != "__pycache__":
                dst_item = dst / item.name
                copy_directory_safely(src_item, dst_item)

        return True
    except OSError as exc:
        print(f"Erro ao copiar diretório {src}: {exc}")
    return False


def create_directory_structure() -> None:
    """Cria a estrutura de diretórios da nova organização."""

    directories = [
        "resync/api/v1",
        "resync/core/cache",
        "resync/core/health",
        "resync/core/security",
        "resync/core/monitoring",
        "resync/config",
        "resync/models",
        "resync/services",
        "resync/utils",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Criado diretório: {directory}")


def migrate_critical_files() -> bool:
    """Migra os arquivos críticos identificados na análise de dependências."""

    critical_files = [
        ("resync/settings.py", "resync/config/settings.py"),
        ("resync/core/simple_logger.py", "resync/utils/simple_logger.py"),
        ("resync/core/exceptions.py", "resync/utils/exceptions.py"),
        ("resync/core/interfaces.py", "resync/utils/interfaces.py"),
        (
            "resync/core/connection_pool_manager.py",
            "resync/core/connection_pool_manager.py",
        ),
        ("resync/core/metrics.py", "resync/core/monitoring/metrics.py"),
        ("resync/core/fastapi_di.py", "resync/core/fastapi_di.py"),
        (
            "resync/core/circuit_breaker.py",
            "resync/core/monitoring/circuit_breaker.py",
        ),
        ("resync/core/health_models.py", "resync/models/health_models.py"),
    ]

    success_count = 0
    total_count = len(critical_files)

    for src_path, dst_path in critical_files:
        src = Path(src_path)
        dst = Path(dst_path)

        if src.exists():
            if src.is_file() and copy_file_safely(src, dst):
                success_count += 1
            elif src.is_dir() and copy_directory_safely(src, dst):
                success_count += 1
        else:
            print(f"Arquivo não encontrado: {src}")

    print(f"\nArquivos críticos copiados: {success_count}/{total_count}")
    return success_count == total_count


def migrate_directories() -> bool:
    """Migra diretórios inteiros."""

    directories = [
        ("resync/core/cache", "resync/core/cache"),
        ("resync/core/health", "resync/core/health"),
        ("resync/core/security.py", "resync/core/security/security.py"),
        ("resync/config", "resync/config"),
        ("resync/models", "resync/models"),
        ("resync/services", "resync/services"),
        ("resync/core/utils", "resync/utils"),
        ("resync/api", "resync/api"),
    ]

    success_count = 0
    total_count = len(directories)

    for src_path, dst_path in directories:
        src = Path(src_path)
        dst = Path(dst_path)

        if src.exists():
            if src.is_file() and copy_file_safely(src, dst):
                success_count += 1
            elif src.is_dir() and copy_directory_safely(src, dst):
                success_count += 1
        else:
            print(f"Arquivo não encontrado: {src}")

    print(f"\nDiretórios copiados: {success_count}/{total_count}")
    return success_count == total_count


def create_init_files() -> None:
    """Cria arquivos ``__init__.py`` para os diretórios."""

    init_files = [
        "resync/api/__init__.py",
        "resync/api/v1/__init__.py",
        "resync/core/__init__.py",
        "resync/core/cache/__init__.py",
        "resync/core/health/__init__.py",
        "resync/core/security/__init__.py",
        "resync/core/monitoring/__init__.py",
        "resync/config/__init__.py",
        "resync/models/__init__.py",
        "resync/services/__init__.py",
        "resync/utils/__init__.py",
    ]

    for init_file in init_files:
        Path(init_file).touch(exist_ok=True)
        print(f"Criado: {init_file}")


def main() -> int:
    """Executa a rotina principal de migração."""

    print("Iniciando migração segura de arquivos...")

    print("\n=== Criando Estrutura de Diretórios ===")
    create_directory_structure()

    print("\n=== Migrando Arquivos Críticos ===")
    critical_files_ok = migrate_critical_files()

    print("\n=== Migrando Diretórios ===")
    directories_ok = migrate_directories()

    print("\n=== Criando Arquivos __init__.py ===")
    create_init_files()

    print("\n=== Resumo da Migração ===")
    critical_status = "✓ OK" if critical_files_ok else "✗ FALHOU"
    directories_status = "✓ OK" if directories_ok else "✗ FALHOU"
    print(f"Arquivos Críticos: {critical_status}")
    print(f"Diretórios: {directories_status}")

    if critical_files_ok and directories_ok:
        print("\n🎉 Migração concluída com sucesso!")
        return 0

    print("\n❌ Migração falhou. Verifique os erros acima.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())






#!/usr/bin/env python3
"""Script para testar funcionalidades após a migração de arquivos."""

import importlib
import sys
import traceback

from resync.core.health.health_service import get_consolidated_health_service


def test_import(module_name: str) -> bool:
    """Testa se um módulo pode ser importado."""

    try:
        importlib.import_module(module_name)
        print(f"✓ Importação bem-sucedida: {module_name}")
        return True
    except ImportError as exc:
        print(f"✗ Falha na importação: {module_name}")
        print(f"  Erro: {exc}")
        traceback.print_exc()
    return False


def _run_import_checks(title: str, modules: list[str]) -> bool:
    """Executa importações e imprime um resumo formatado."""

    print(f"\n=== {title} ===")
    success_count = 0
    total_count = len(modules)

    for module in modules:
        if test_import(module):
            success_count += 1

    summary = (
        f"\nResultado: {success_count}/{total_count} "
        "módulos importados com sucesso"
    )
    print(summary)
    return success_count == total_count


def test_new_structure() -> bool:
    """Valida as importações da nova estrutura de diretórios."""

    critical_modules = [
        "resync.config.settings",
        "resync.utils.simple_logger",
        "resync.utils.exceptions",
        "resync.utils.interfaces",
        "resync.core.connection_pool_manager",
        "resync.core.monitoring.metrics",
        "resync.core.fastapi_di",
        "resync.core.monitoring.circuit_breaker",
        "resync.core.cache",
        "resync.models.health_models",
        "resync.core.health",
    ]
    return _run_import_checks("Testando Nova Estrutura", critical_modules)


def test_old_structure() -> bool:
    """Verifica se a estrutura antiga funciona com imports atualizados."""

    legacy_modules = [
        "resync.settings",
        "resync.core.simple_logger",
        "resync.core.exceptions",
        "resync.core.interfaces",
        "resync.core.connection_pool_manager",
        "resync.core.metrics",
        "resync.core.fastapi_di",
        "resync.core.circuit_breaker",
        "resync.core.cache",
        "resync.core.health_models",
        "resync.core.health",
    ]
    return _run_import_checks(
        "Testando Estrutura Antiga com Imports Atualizados",
        legacy_modules,
    )


def test_api_endpoints() -> bool:
    """Avalia a importação dos principais endpoints da API."""

    print("\n=== Testando Endpoints da API ===")
    endpoints = [
        "resync.api.v1.routes.health",
        "resync.api.v1.routes.auth",
        "resync.api.v1.routes.agents",
        "resync.core.health.health_service",
    ]

    results = [test_import(endpoint) for endpoint in endpoints]
    return all(results)


def test_health_service() -> bool:
    """Confere se o serviço consolidado de saúde responde corretamente."""

    print("\n=== Testando Health Service Consolidado ===")
    try:
        service = get_consolidated_health_service()
        print("✓ Health service consolidado funcionando")

        if hasattr(service, "get_system_health"):
            print("✓ Método get_system_health disponível")

        return True
    except Exception as exc:  # noqa: BLE001 - script de diagnóstico
        print(f"✗ Erro ao testar health service: {exc}")
        traceback.print_exc()
    return False


def main() -> int:
    """Executa todos os testes pós-migração."""

    print("Testando funcionalidades após migração...")

    new_structure_ok = test_new_structure()
    old_structure_ok = test_old_structure()
    api_endpoints_ok = test_api_endpoints()
    health_service_ok = test_health_service()

    print("\n=== Resumo Final ===")
    print(f"Estrutura Nova: {'✓ OK' if new_structure_ok else '✗ FALHOU'}")
    print(f"Estrutura Antiga: {'✓ OK' if old_structure_ok else '✗ FALHOU'}")
    print(f"Endpoints API: {'✓ OK' if api_endpoints_ok else '✗ FALHOU'}")
    print(f"Health Service: {'✓ OK' if health_service_ok else '✗ FALHOU'}")

    results = (
        new_structure_ok,
        old_structure_ok,
        api_endpoints_ok,
        health_service_ok,
    )
    all_tests_passed = all(results)

    if all_tests_passed:
        print("\n🎉 Todos os testes passaram! Migração bem-sucedida.")
        return 0

    print("\n❌ Alguns testes falharam. Verifique os erros acima.")
    return 1


if __name__ == "__main__":
    sys.exit(main())





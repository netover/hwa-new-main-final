#!/usr/bin/env python3
"""
Script para testar funcionalidades após migração de arquivos
"""

import sys
import importlib
import traceback
from pathlib import Path

# Import health service for testing
from resync.core.health.health_service import get_consolidated_health_service

def test_import(module_name):
    """Testa se um módulo pode ser importado"""
    try:
        importlib.import_module(module_name)
        print(f"✓ Importação bem-sucedida: {module_name}")
        return True
    except Exception as e:
        print(f"✗ Falha na importação: {module_name}")
        print(f"  Erro: {e}")
        traceback.print_exc()
        return False

def test_new_structure():
    """Testa importação dos módulos na nova estrutura"""
    print("=== Testando Nova Estrutura ===")

    # Módulos críticos que foram migrados
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

    success_count = 0
    total_count = len(critical_modules)

    for module in critical_modules:
        if test_import(module):
            success_count += 1

    print(f"\nResultado: {success_count}/{total_count} módulos importados com sucesso")
    return success_count == total_count

def test_old_structure():
    """Testa se a estrutura antiga ainda funciona com os imports atualizados"""
    print("\n=== Testando Estrutura Antiga com Imports Atualizados ===")

    # Módulos críticos na estrutura antiga
    critical_modules = [
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

    success_count = 0
    total_count = len(critical_modules)

    for module in critical_modules:
        if test_import(module):
            success_count += 1

    print(f"\nResultado: {success_count}/{total_count} módulos importados com sucesso")
    return success_count == total_count

def test_api_endpoints():
    """Testa se os endpoints da API ainda funcionam"""
    print("\n=== Testando Endpoints da API ===")

    try:
        # Testar importação dos endpoints
        test_import("resync.api.v1.routes.health")
        test_import("resync.api.v1.routes.auth")
        test_import("resync.api.v1.routes.agents")

        # Testar importação do health service consolidado
        test_import("resync.core.health.health_service")

        return True
    except Exception as e:
        print(f"Erro ao testar endpoints: {e}")
        return False

def test_health_service():
    """Testa se o health service consolidado funciona"""
    print("\n=== Testando Health Service Consolidado ===")

    try:
        # Tentar obter instância do serviço
        service = get_consolidated_health_service()
        print("✓ Health service consolidado funcionando")

        # Testar método de verificação de saúde
        if hasattr(service, 'get_system_health'):
            print("✓ Método get_system_health disponível")

        return True
    except Exception as e:
        print(f"✗ Erro ao testar health service: {e}")
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    print("Testando funcionalidades após migração...")

    # Testar nova estrutura
    new_structure_ok = test_new_structure()

    # Testar estrutura antiga com imports atualizados
    old_structure_ok = test_old_structure()

    # Testar endpoints da API
    api_endpoints_ok = test_api_endpoints()

    # Testar health service consolidado
    health_service_ok = test_health_service()

    # Resumo final
    print("\n=== Resumo Final ===")
    print(f"Estrutura Nova: {'✓ OK' if new_structure_ok else '✗ FALHOU'}")
    print(f"Estrutura Antiga: {'✓ OK' if old_structure_ok else '✗ FALHOU'}")
    print(f"Endpoints API: {'✓ OK' if api_endpoints_ok else '✗ FALHOU'}")
    print(f"Health Service: {'✓ OK' if health_service_ok else '✗ FALHOU'}")

    all_tests_passed = all([new_structure_ok, old_structure_ok, api_endpoints_ok, health_service_ok])

    if all_tests_passed:
        print("\n🎉 Todos os testes passaram! Migração bem-sucedida.")
        return 0

    print("\n❌ Alguns testes falharam. Verifique os erros acima.")
    return 1

if __name__ == "__main__":
    sys.exit(main())





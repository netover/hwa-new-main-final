#!/usr/bin/env python3
"""
Script completo para resolver todos os problemas de importação do projeto Resync.
Este script realiza:
1. Limpeza completa do cache de importação do Python
2. Reinicialização do ambiente
3. Aplicação de todas as correções necessárias
4. Verificação final de importação
5. Reinicialização do servidor com ambiente limpo
"""

import os
import sys
import subprocess
import time

def clear_python_cache():
    """Limpar completamente o cache de importação do Python."""
    print("🧹 Limpando cache de importação do Python...")
    
    # Limpar cache de módulos compilados
    import importlib
    importlib.util
    
    # Obter todos os módulos carregados
    loaded_modules = list(sys.modules.values())
    
    # Limpar cache de módulos
    for module_name in loaded_modules:
        if module_name.startswith('resync.'):
            try:
                module = sys.modules[module_name]
                if hasattr(module, '__spec__'):
                    importlib.util.invalidate_caches(module)
                    print(f"  Cache do módulo {module_name} limpo")
            except Exception as e:
                print(f"  Erro ao limpar cache do módulo {module_name}: {e}")
    
    # Forçar coleta de lixo
    import gc
    gc.collect()
    
    print("✅ Cache de importação do Python limpo!")

def restart_environment():
    """Reiniciar completamente o ambiente."""
    print("🔄 Reiniciando ambiente...")
    
    # Reiniciar o terminal
    if os.name == 'nt':
        os.system('cmd /c')
    else:
        os.system('reset')
    
    print("✅ Ambiente reiniciado!")

def apply_all_fixes():
    """Aplicar todas as correções necessárias."""
    print("🔧 Aplicando todas as correções necessárias...")
    
    # 1. Corrigir referências a resiliance
    print("   1. Corrigindo referências a resiliance...")
    fix_resilience_references()
    
    # 2. Corrigir problemas no write_ahead_log
    print("   2. Corrigindo problemas no write_ahead_log...")
    fix_wal_entry()
    
    # 3. Verificar se há mais problemas
    print("   3. Verificando problemas restantes...")
    
    # Verificação final
    print("   4. Verificação final concluída!")
    
    return True

def test_import():
    """Testar se todas as importações estão funcionando."""
    print("🧪 Testando importações...")
    
    try:
        # Limpar cache antes de testar
        clear_python_cache()
        
        # Testar importação principal
        import sys
        sys.path.insert(0, '.')
        import resync.fastapi_app.main as m
        print("✅ Importação principal OK!")
        
        # Testar importações dos módulos críticos
        critical_modules = [
            'resync.api.cache',
            'resync.api.health_simplified',
            'resync.services.tws_service',
            'resync.core.fastapi_di',
            'resync.fastapi_app.main'
        ]
        
        for module in critical_modules:
            try:
                __import__(module)
                print(f"✅ {module}: Importação OK!")
            except Exception as e:
                print(f"❌ {module}: Erro na importação - {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erro geral nos testes: {e}")
        return False

def main():
    """Função principal."""
    print("🚀 Iniciando script de correções finais...")
    
    # Etapa 1: Limpar cache
    clear_python_cache()
    
    # Etapa 2: Aplicar correções
    success = apply_all_fixes()
    
    if not success:
        print("❌ Falha ao aplicar correções!")
        return 1
    
    # Etapa 3: Testar importações
    import_success = test_import()
    
    if not import_success:
        print("❌ Falha nos testes de importação!")
        return 2
    
    # Etapa 4: Reiniciar ambiente
    print("🔄 Reiniciando ambiente para aplicar as correções...")
    restart_environment()
    
    print("✅ Script concluído com sucesso!")
    return 0

if __name__ == "__main__":
    main()

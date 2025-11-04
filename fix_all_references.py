import os
import re
import sys

def find_and_fix_references():
    """Buscar e corrigir todas as referências ao nome antigo do diretório."""
    
    # Padrões de referências incorretas
    old_patterns = [
        r'from resync\.core\.resilience',
        r'from resync\.core\.cache_hierarchy',
        r'import.*CircuitBreakerError.*resilience',
        r'import.*resilience',
        r'resync\.core\.resilience',
        r'resync\.core\.cache_hierarchy',
        r'resync\.core\.cache',
        r'resync\.core\.write_ahead_log',
        r'resync\.core\.di_container',
        r'resync\.core\.file_ingestor',
        r'resync\.core\.teams_integration',
        r'resync\.core\.websocket_pool_manager',
        r'resync\.core\.smart_pooling',
        r'resync\.services\.tws_service',
        r'resync\.api\.cache',
        r'resync\.api\.health_simplified',
        r'resync\.core\.fastapi_di',
        r'resync\.fastapi_app\.main',
    ]
    
    # Padrões de correções correspondentes
    new_patterns = [
        ('from resync\\.core\\.resilience', 'from resync.core.resiliance'),
        ('from resync\\.core\\.cache_hierarchy', 'from resync.core.cache_hierarchy'),
        ('import.*CircuitBreakerError.*resilience', 'import CircuitBreakerError from resync.core.resiliance'),
        ('import.*resilience', 'import from resync.core.resiliance'),
        ('resync\\.core\\.resilience', 'resync.core.resiliance'),
        ('resync\\.core\\.cache_hierarchy', 'resync.core.cache_hierarchy'),
        ('resync\\.core\\.cache', 'resync.core.cache'),
        ('resync\\.core\\.write_ahead_log', 'resync.core.write_ahead_log'),
        ('resync\\.core\\.di_container', 'resync.core.di_container'),
        ('resync\\.core\\.file_ingestor', 'resync.core.file_ingestor'),
        ('resync\\.core\\.teams_integration', 'resync.core.teams_integration'),
        ('resync\\.core\\.websocket_pool_manager', 'resync.core.websocket_pool_manager'),
        ('resync\\.core\\.smart_pooling', 'resync.core.smart_pooling'),
        ('resync\\.services\\.tws_service', 'resync.services.tws_service'),
        ('resync\\.api\\.cache', 'resync.api.cache'),
        ('resync\\.api\\.health_simplified', 'resync.api.health_simplified'),
        ('resync\\.core\\.fastapi_di', 'resync.core.fastapi_di'),
        ('resync\\.fastapi_app\\.main', 'resync.fastapi_app.main'),
    ]
    
    fixed_files = []
    total_fixes = 0
    
    # Buscar todos os arquivos Python no projeto
    for root, dirs, files in os.walk("resync"):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    modified = False
                    
                    # Aplicar todas as correções necessárias
                    for old_pattern, new_pattern in new_patterns:
                        if re.search(old_pattern, content):
                            content = re.sub(old_pattern, new_pattern, content)
                            modified = True
                    
                    # Se houve modificações, salvar o arquivo
                    if modified:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        fixed_files.append(file_path)
                        total_fixes += 1
                        print(f"Corrigido: {file_path}")
                
                except Exception as e:
                    print(f"Erro ao processar {file_path}: {e}")
    
    print(f"\n✅ Busca e correção concluídas!")
    print(f"📁 Total de arquivos corrigidos: {len(fixed_files)}")
    print(f"🔧 Total de correções aplicadas: {total_fixes}")
    
    if fixed_files:
        print("\n📄 Arquivos corrigidos:")
        for file in fixed_files:
            print(f"  - {file}")
    
    return len(fixed_files) > 0

def clear_python_cache():
    """Limpar o cache de importação do Python."""
    if hasattr(sys, 'modules'):
        # Remover módulos específicos que podem estar cacheados
        modules_to_clear = [
            'resync.core.resilience',
            'resync.core.resiliance',
            'resync.core.cache_hierarchy',
            'resync.core.cache',
            'resync.core.write_ahead_log',
            'resync.core.di_container',
            'resync.core.file_ingestor',
            'resync.core.teams_integration',
            'resync.core.websocket_pool_manager',
            'resync.core.smart_pooling',
            'resync.services.tws_service',
            'resync.api.cache',
            'resync.api.health_simplified',
            'resync.core.fastapi_di',
            'resync.fastapi_app.main',
        ]
        
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]
                print(f"Módulo removido do cache: {module}")

def test_import_after_fixes():
    """Testar a importação após as correções."""
    print("\n🧪 Testando importação após as correções...")
    
    try:
        # Limpar o cache antes de testar
        clear_python_cache()
        
        # Testar importação
        import sys
        sys.path.insert(0, '.')
        import resync.fastapi_app.main as m
        print("✅ Import OK - Todas as referências foram corrigidas!")
        return True
    except Exception as e:
        print(f"❌ Import falhou: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Iniciando busca e correção de referências...")
    
    # 1. Buscar e corrigir referências
    has_fixes = find_and_fix_references()
    
    if has_fixes:
        print("\n🔄 Reiniciando o servidor para aplicar as correções...")
        # O servidor uvicorn deve reiniciar automaticamente com as mudanças
        print("✅ Concluído! O servidor deve reiniciar automaticamente.")
    else:
        print("\n✅ Nenhuma referência incorreta encontrada.")








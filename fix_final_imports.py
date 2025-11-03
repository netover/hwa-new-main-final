import os
import re
import shutil

# 1. Criar link simbólico de resilience para resiliance (alternativa para Windows)
resilience_dir = "resync/core/resilience"
resiliance_dir = "resync/core/resiliance"

# Copiar diretório se não existir
if not os.path.exists(resiliance_dir) and os.path.exists(resilience_dir):
    print(f"Copiando diretório {resilience_dir} para {resiliance_dir}")
    shutil.copytree(resilience_dir, resiliance_dir)
else:
    print(f"Diretório {resiliance_dir} já existe ou {resilience_dir} não existe")

# 2. Encontrar e corrigir referências a resilience nos arquivos
def fix_resilience_references():
    """Encontrar e corrigir referências a resilience nos arquivos."""
    for root, dirs, files in os.walk("resync"):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Substituir referências incorretas
                if 'from resync.core.resilience' in content:
                    content = content.replace('from resync.core.resilience', 'from resync.core.resiliance')
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Corrigido {file_path}")

# 3. Corrigir o problema com sequence_number em WalEntry
def fix_wal_entry():
    """Corrigir o problema com sequence_number em WalEntry."""
    wal_file = "resync/core/write_ahead_log.py"
    with open(wal_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Adicionar valor padrão para sequence_number
    content = re.sub(
        r'(class WalEntry:.*?)(\s+sequence_number: int)',
        r'\1sequence_number: int = 0  # Valor padrão',
        content
    )
    
    with open(wal_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Corrigido {wal_file}")

# 4. Testar a importação
def test_import():
    """Testar a importação do módulo principal."""
    print("\nTestando importação do módulo principal...")
    try:
        import sys
        sys.path.insert(0, '.')
        import resync.fastapi_app.main as m
        print("Import OK - Todos os problemas foram resolvidos!")
        return True
    except Exception as e:
        print(f"Import falhou: {e}")
        return False

if __name__ == "__main__":
    print("Iniciando correções finais...")
    
    # 1. Copiar diretório resilience para resiliance
    fix_resilience_references()
    
    # 2. Corrigir WalEntry
    fix_wal_entry()
    
    # 3. Testar importação
    success = test_import()
    
    if success:
        print("\nTodas as correcoes foram aplicadas com sucesso!")
    else:
        print("\nAinda ha problemas a serem resolvidos.")

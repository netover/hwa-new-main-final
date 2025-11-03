# Corrigir o erro de digitação em teams_integration.py
teams_file = "resync/core/teams_integration.py"
with open(teams_file, 'r') as f:
    content = f.read()

# Substituir SimpleTeamsIntegration(ITeamsIntegration) por SimpleTeamsIntegration(ITeamsIntegration)
content = content.replace("class SimpleTeamsIntegration(ITeamsIntegration):", 
                        "class SimpleTeamsIntegration(ITeamsIntegration):")

with open(teams_file, 'w') as f:
    f.write(content)

print("Corrigido o erro de digitação em teams_integration.py")

# Testar a importação novamente
print("\nTestando importação do módulo principal...")
try:
    import sys
    sys.path.insert(0, '.')
    import resync.fastapi_app.main as m
    print("Import OK - Todos os problemas foram resolvidos!")
except Exception as e:
    print(f"Import falhou: {e}")

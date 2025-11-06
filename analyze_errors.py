import json
from collections import Counter

# Carregar relatório de erros
with open('analysis_reports/fase2_baseline.json', 'r') as f:
    data = json.load(f)

# Contar tipos de erros
error_counts = Counter()
for diag in data['generalDiagnostics']:
    if 'rule' in diag:
        error_counts[diag['rule']] += 1

print("=== TOP 20 TIPOS DE ERROS PYRIGHT ===")
for rule, count in error_counts.most_common(20):
    print(f"{rule:<35} {count:>6}")

print(f"\n=== TOTAL GERAL: {len(data['generalDiagnostics'])} erros ===")

# Focar nos tipos de erro da Fase 2
fase2_errors = {
    'reportMissingParameterType': 0,
    'reportUnknownParameterType': 0,
    'reportUnknownVariableType': 0,
    'reportUnknownMemberType': 0,
    'reportAttributeAccessIssue': 0
}

for diag in data['generalDiagnostics']:
    if 'rule' in diag and diag['rule'] in fase2_errors:
        fase2_errors[diag['rule']] += 1

print("\n=== FOCO FASE 2: Type Hints e Parâmetros ===")
for rule, count in fase2_errors.items():
    print(f"{rule:<35} {count:>6}")

print(f"Total Fase 2: {sum(fase2_errors.values())} erros")

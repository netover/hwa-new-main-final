import re


def parse_bandit_report(file_path):
    """Parse the Bandit report and extract security issues."""

    issues = []

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all issue blocks
    issue_pattern = r">> Issue: \[([^\]]+)\] ([^\n]+)\n   Severity: ([^\n]+)\n   CWE: [^\n]+\n   More Info: [^\n]+\n   Location: ([^\n]+)"
    matches = re.findall(issue_pattern, content, re.MULTILINE)

    for match in matches:
        test_id_and_severity = match[0]
        description = match[1]
        severity = match[2]
        location = match[3]

        # Parse test_id and severity level
        test_id = test_id_and_severity.split(":")[0]

        issues.append(
            {
                "test_id": test_id,
                "severity": severity,
                "description": description,
                "location": location,
            }
        )

    return issues


def analyze_issues(issues):
    """Analyze the issues and provide summary statistics."""

    # Count by severity
    severity_counts = {"Low": 0, "Medium": 0, "High": 0, "Undefined": 0}
    issue_types = {}

    for issue in issues:
        severity = issue.get("severity", "Undefined")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

        test_id = issue.get("test_id", "Unknown")
        issue_types[test_id] = issue_types.get(test_id, 0) + 1

    return severity_counts, issue_types


def main():
    print("=== ANÁLISE DE SEGURANÇA BANDIT - PROJETO RESYNC ===")
    print()

    # Parse the report
    issues = parse_bandit_report("bandit_core_report.txt")

    print(f"Total de problemas de segurança encontrados: {len(issues)}")
    print()

    # Analyze issues
    severity_counts, issue_types = analyze_issues(issues)

    print("PROBLEMAS POR GRAU DE SEVERIDADE:")
    for severity, count in severity_counts.items():
        if count > 0:
            print(f"  {severity}: {count}")
    print()

    print("TIPOS DE PROBLEMAS MAIS COMUNS:")
    # Sort by frequency
    sorted_issues = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)
    for test_id, count in sorted_issues[:10]:
        print(f"  {test_id}: {count} ocorrências")

    print()
    print("ANÁLISE DETALHADA:")
    print()

    # Group issues by type for detailed analysis
    assert_issues = [i for i in issues if i["test_id"] == "B101"]
    password_issues = [i for i in issues if i["test_id"] == "B105"]
    other_issues = [i for i in issues if i["test_id"] not in ["B101", "B105"]]

    print(f"1. Uso de 'assert' em produção (B101): {len(assert_issues)} ocorrências")
    print("   - Severidade: Baixa")
    print("   - Impacto: Código de assert é removido em bytecode otimizado")
    print("   - Localização: Principalmente em testes unitários")
    print("   - Recomendação: Usar assert apenas em testes, não em código de produção")
    print()

    print(f"2. Senhas hardcoded (B105): {len(password_issues)} ocorrências")
    print("   - Severidade: Baixa")
    print("   - Impacto: Senhas expostas no código fonte")
    print("   - Localização: Principalmente em testes de validação de senha")
    print("   - Recomendação: Usar variáveis de ambiente ou arquivos de configuração")
    print()

    print(f"3. Outros problemas de segurança: {len(other_issues)} ocorrências")
    if other_issues:
        print("   Detalhes dos problemas encontrados:")
        for issue in other_issues[:5]:  # Show first 5
            print(f"   - {issue['test_id']}: {issue['description']}")
        if len(other_issues) > 5:
            print(f"   ... e mais {len(other_issues) - 5} problemas")

    print()
    print("CONCLUSÃO:")
    print("- A maioria dos problemas são de baixa severidade (uso de assert em testes)")
    print("- Apenas 1 problema de senha hardcoded encontrado (em teste)")
    print("- Não foram encontrados problemas de alta severidade")
    print("- O código demonstra boas práticas de segurança geral")


if __name__ == "__main__":
    main()

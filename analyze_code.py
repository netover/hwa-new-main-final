#!/usr/bin/env python3
"""Script para análise detalhada do código."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
from radon.visitors import ComplexityVisitor


def analyze_file(filepath: Path) -> dict[str, Any]:
    """Analisa um arquivo Python."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Análise de complexidade
        try:
            visitor = ComplexityVisitor.from_code(content)
            complexities = []
            for item in visitor.functions:
                complexities.append(
                    {
                        "name": item.name,
                        "complexity": item.complexity,
                        "lineno": item.lineno,
                        "col_offset": item.col_offset,
                        "endline": item.endline,
                    }
                )
        except Exception:
            complexities = []

        # Análise AST
        try:
            tree = ast.parse(content)

            # Contar funções, classes, etc
            functions = sum(
                1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
            )
            classes = sum(
                1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            )
            imports = sum(
                1
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            )

            # Verificar type hints
            functions_with_hints = 0
            total_functions = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_functions += 1
                    if node.returns or any(arg.annotation for arg in node.args.args):
                        functions_with_hints += 1

            type_hint_coverage = (
                (functions_with_hints / total_functions * 100)
                if total_functions > 0
                else 0
            )

        except Exception:
            functions = classes = imports = 0
            type_hint_coverage = 0

        lines = content.split("\n")
        loc = len(lines)
        sloc = len([l for l in lines if l.strip() and not l.strip().startswith("#")])

        return {
            "file": str(filepath),
            "loc": loc,
            "sloc": sloc,
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "complexities": complexities,
            "type_hint_coverage": round(type_hint_coverage, 2),
            "high_complexity": [c for c in complexities if c["complexity"] > 6],
        }

    except Exception as e:
        return {"file": str(filepath), "error": str(e)}


def analyze_project(root_dir: str = "resync") -> dict[str, Any]:
    """Analisa todo o projeto."""
    root_path = Path(root_dir)

    results: dict[str, Any] = {
        "files": [],
        "summary": {
            "total_files": 0,
            "total_loc": 0,
            "total_sloc": 0,
            "total_functions": 0,
            "total_classes": 0,
            "high_complexity_functions": [],
            "files_without_type_hints": [],
            "avg_type_hint_coverage": 0,
        },
    }

    # Analisar todos os arquivos .py
    py_files = list(root_path.rglob("*.py"))

    for py_file in py_files:
        if "__pycache__" in str(py_file):
            continue

        analysis = analyze_file(py_file)
        results["files"].append(analysis)

        if "error" not in analysis:
            results["summary"]["total_files"] += 1
            results["summary"]["total_loc"] += analysis["loc"]
            results["summary"]["total_sloc"] += analysis["sloc"]
            results["summary"]["total_functions"] += analysis["functions"]
            results["summary"]["total_classes"] += analysis["classes"]

            # Funções com alta complexidade
            for comp in analysis["high_complexity"]:
                results["summary"]["high_complexity_functions"].append(
                    {
                        "file": analysis["file"],
                        "function": comp["name"],
                        "complexity": comp["complexity"],
                        "line": comp["lineno"],
                    }
                )

            # Arquivos sem type hints
            if analysis["type_hint_coverage"] < 50:
                results["summary"]["files_without_type_hints"].append(
                    {
                        "file": analysis["file"],
                        "coverage": analysis["type_hint_coverage"],
                    }
                )

    # Calcular média de cobertura de type hints
    if results["summary"]["total_files"] > 0:
        total_coverage = sum(
            f.get("type_hint_coverage", 0) for f in results["files"] if "error" not in f
        )
        results["summary"]["avg_type_hint_coverage"] = round(
            total_coverage / results["summary"]["total_files"], 2
        )

    # Ordenar por complexidade
    results["summary"]["high_complexity_functions"].sort(
        key=lambda x: x["complexity"], reverse=True
    )

    return results


def generate_report(
    results: dict[str, Any], output_file: str = "AUDIT_REPORT.md"
) -> None:
    """Gera relatório em Markdown."""

    report = f"""# Relatório de Auditoria de Código

## 📊 Resumo Geral

- **Total de Arquivos:** {results['summary']['total_files']}
- **Linhas de Código (LOC):** {results['summary']['total_loc']:,}
- **Linhas de Código Significativas (SLOC):** {results['summary']['total_sloc']:,}
- **Total de Funções:** {results['summary']['total_functions']}
- **Total de Classes:** {results['summary']['total_classes']}
- **Cobertura Média de Type Hints:** {results['summary']['avg_type_hint_coverage']}%

---

## 🔴 Funções com Alta Complexidade (> 6)

**Total:** {len(results['summary']['high_complexity_functions'])}

"""

    if results["summary"]["high_complexity_functions"]:
        report += "| Arquivo | Função | Complexidade | Linha |\n"
        report += "|---------|--------|--------------|-------|\n"

        for func in results["summary"]["high_complexity_functions"][:20]:  # Top 20
            file_short = func["file"].replace("\\", "/").split("resync/")[-1]
            report += f"| `{file_short}` | `{func['function']}` | **{func['complexity']}** | {func['line']} |\n"
    else:
        report += "✅ Nenhuma função com complexidade > 6 encontrada!\n"

    report += "\n---\n\n"
    report += "## 📝 Arquivos com Baixa Cobertura de Type Hints (< 50%)\n\n"
    report += f"**Total:** {len(results['summary']['files_without_type_hints'])}\n\n"

    if results["summary"]["files_without_type_hints"]:
        report += "| Arquivo | Cobertura |\n"
        report += "|---------|----------|\n"

        for file_info in sorted(
            results["summary"]["files_without_type_hints"], key=lambda x: x["coverage"]
        )[:20]:
            file_short = file_info["file"].replace("\\", "/").split("resync/")[-1]
            report += f"| `{file_short}` | {file_info['coverage']}% |\n"
    else:
        report += "✅ Todos os arquivos têm boa cobertura de type hints!\n"

    report += "\n---\n\n"
    report += "## 📋 Detalhes por Arquivo\n\n"

    for file_data in sorted(
        results["files"], key=lambda x: x.get("sloc", 0), reverse=True
    )[:10]:
        if "error" in file_data:
            continue

        file_short = file_data["file"].replace("\\", "/").split("resync/")[-1]
        report += f"### `{file_short}`\n\n"
        report += f"- **LOC:** {file_data['loc']}\n"
        report += f"- **SLOC:** {file_data['sloc']}\n"
        report += f"- **Funções:** {file_data['functions']}\n"
        report += f"- **Classes:** {file_data['classes']}\n"
        report += f"- **Type Hint Coverage:** {file_data['type_hint_coverage']}%\n"

        if file_data["high_complexity"]:
            report += (
                f"- **⚠️ Funções Complexas:** {len(file_data['high_complexity'])}\n"
            )
            for comp in file_data["high_complexity"][:5]:
                report += f"  - `{comp['name']}` (complexidade: {comp['complexity']}, linha: {comp['lineno']})\n"

        report += "\n"

    report += "\n---\n\n"
    report += "## 🎯 Recomendações\n\n"

    if results["summary"]["high_complexity_functions"]:
        report += "### 1. Reduzir Complexidade\n"
        report += f"- Refatorar {len(results['summary']['high_complexity_functions'])} funções com complexidade > 6\n"
        report += "- Aplicar Extract Method pattern\n"
        report += "- Seguir Single Responsibility Principle\n\n"

    if results["summary"]["avg_type_hint_coverage"] < 80:
        report += "### 2. Melhorar Type Hints\n"
        report += (
            f"- Cobertura atual: {results['summary']['avg_type_hint_coverage']}%\n"
        )
        report += "- Meta: > 90%\n"
        report += f"- Adicionar type hints em {len(results['summary']['files_without_type_hints'])} arquivos\n\n"

    report += "### 3. Próximos Passos\n"
    report += "- [ ] Implementar hierarquia de exceções padronizada\n"
    report += "- [ ] Adicionar sistema de correlation IDs\n"
    report += "- [ ] Implementar logging estruturado\n"
    report += "- [ ] Adicionar padrões de resiliência\n"
    report += "- [ ] Melhorar cobertura de testes\n"

    # Salvar relatório
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Relatorio gerado: {output_file}")

    # Também salvar JSON
    json_file = output_file.replace(".md", ".json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Dados JSON salvos: {json_file}")


if __name__ == "__main__":
    print("Iniciando analise do codigo...")
    results = analyze_project("resync")

    print("\nAnalise concluida!")
    print(f"   - Arquivos analisados: {results['summary']['total_files']}")
    print(
        f"   - Funcoes complexas: {len(results['summary']['high_complexity_functions'])}"
    )
    print(
        f"   - Cobertura de type hints: {results['summary']['avg_type_hint_coverage']}%"
    )

    print("\nGerando relatorio...")
    generate_report(results)

    print("\nAnalise completa!")

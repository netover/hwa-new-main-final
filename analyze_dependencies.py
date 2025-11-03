#!/usr/bin/env python3
"""
Script para analisar dependências entre arquivos Python no projeto resync
"""

import ast
import json
from pathlib import Path
from collections import defaultdict
from typing import Any


class DependencyAnalyzer:
    """Analyzer for Python project dependencies and file relationships."""

    def __init__(self, root_dir: str = "resync") -> None:
        self.root_dir = Path(root_dir)
        self.dependencies: defaultdict[str, set[str]] = defaultdict(set)
        self.reverse_dependencies: defaultdict[str, set[str]] = defaultdict(set)
        self.all_files: set[str] = set()

    def get_all_python_files(self) -> list[Path]:
        """Obtém todos os arquivos Python no diretório"""
        python_files: list[Path] = []
        for file_path in self.root_dir.rglob("*.py"):
            if "__pycache__" not in str(file_path):
                python_files.append(file_path)
                self.all_files.add(str(file_path))
        return python_files

    def extract_imports(self, file_path: Path) -> list[str]:
        """Extrai imports de um arquivo Python"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            imports: list[str] = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            return imports
        except (OSError, ValueError) as e:
            print(f"Erro ao analisar {file_path}: {e}")
            return []

    def is_internal_import(self, import_name: str) -> bool:
        """Verifica se um import é interno ao projeto"""
        return import_name.startswith("resync")

    def get_module_from_path(self, file_path: Path) -> str:
        """Converte caminho do arquivo para nome do módulo"""
        relative_path = file_path.relative_to(self.root_dir)
        # Remove o nome do arquivo
        module_parts = list(relative_path.parts[:-1])

        # Remove .py do nome do arquivo e adiciona aos partes do módulo
        file_name = file_path.stem
        if file_name != "__init__":
            module_parts.append(file_name)

        return ".".join(module_parts) if module_parts else "resync"

    def build_dependency_graph(self) -> None:
        """Constrói o grafo de dependências"""
        python_files = self.get_all_python_files()

        for file_path in python_files:
            module_name = self.get_module_from_path(file_path)
            imports = self.extract_imports(file_path)

            for import_name in imports:
                if self.is_internal_import(import_name):
                    self.dependencies[module_name].add(import_name)
                    self.reverse_dependencies[import_name].add(module_name)

    def find_critical_files(self) -> list[str]:
        """Identifica arquivos críticos com base nas dependências"""
        critical_files: list[str] = []

        # Arquivos que são mais importados
        # (maior número de dependências reversas)
        dependency_counts: dict[str, int] = {
            k: len(v) for k, v in self.reverse_dependencies.items()
        }
        sorted_by_dependencies: list[tuple[str, int]] = sorted(
            dependency_counts.items(), key=lambda x: x[1], reverse=True
        )

        # Arquivos no topo 20% de dependências
        top_20_percent = int(len(sorted_by_dependencies) * 0.2) or 1
        critical_files.extend(
            [item[0] for item in sorted_by_dependencies[:top_20_percent]]
        )

        return critical_files

    def find_entry_points(self) -> list[str]:
        """Identifica pontos de entrada.

        Arquivos que não são importados por outros.
        """
        entry_points: list[str] = []

        for module in self.all_files:
            module_name = self.get_module_from_path(Path(module))
            if not self.reverse_dependencies.get(module_name):
                entry_points.append(module_name)

        return entry_points

    def find_circular_dependencies(self) -> list[list[str]]:
        """Identifica dependências circulares"""
        circular_deps: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str, path: list[str]) -> None:
            if node in rec_stack:
                # Encontrou ciclo
                cycle_start = path.index(node)
                circular_deps.append(path[cycle_start:] + [node])
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.dependencies.get(node, []):
                dfs(neighbor, path + [node])

            rec_stack.remove(node)

        for node in self.dependencies:
            if node not in visited:
                dfs(node, [])

        return circular_deps

    def generate_report(self) -> dict[str, Any]:
        """Gera relatório de análise de dependências"""
        critical_files = self.find_critical_files()
        entry_points = self.find_entry_points()
        circular_deps = self.find_circular_dependencies()

        report: dict[str, Any] = {
            "total_files": len(self.all_files),
            "critical_files": critical_files,
            "entry_points": entry_points,
            "circular_dependencies": circular_deps,
            "dependency_graph": {
                k: list(v) for k, v in self.dependencies.items()
            },
            "reverse_dependency_graph": {
                k: list(v) for k, v in self.reverse_dependencies.items()
            }
        }

        return report

    def save_report(self, output_file: str = "dependency_report.json") -> dict:
        """Salva o relatório em um arquivo JSON"""
        report = self.generate_report()

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"Relatório salvo em {output_file}")
        return report


def main() -> None:
    """Função principal"""
    print("Analisando dependências do projeto resync...")

    analyzer = DependencyAnalyzer()
    analyzer.build_dependency_graph()

    report = analyzer.save_report()

    print("\n=== Resumo da Análise ===")
    print(f"Total de arquivos: {report['total_files']}")
    print(f"Arquivos críticos: {len(report['critical_files'])}")
    print(f"Pontos de entrada: {len(report['entry_points'])}")
    print(f"Dependências circulares: {len(report['circular_dependencies'])}")

    print("\n=== Arquivos Críticos ===")
    for file in report['critical_files'][:10]:  # Mostra apenas os 10 primeiros
        print(f"- {file}")

    print("\n=== Pontos de Entrada ===")
    for file in report['entry_points'][:10]:  # Mostra apenas os 10 primeiros
        print(f"- {file}")

    if report['circular_dependencies']:
        print("\n=== Dependências Circulares ===")
        for cycle in report['circular_dependencies']:
            print(" -> ".join(cycle))


if __name__ == "__main__":
    main()





#!/usr/bin/env python3

from __future__ import annotations

import ast
import sys


def analyze_imports(file_path: str) -> None:
    """Analyze imports in a Python file to identify potentially unused ones."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)

    # Collect all imports
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    (
                        node.lineno,
                        f"import {alias.name}"
                        + (f" as {alias.asname}" if alias.asname else ""),
                        alias.name,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(
                    (
                        node.lineno,
                        f"from {module} import {alias.name}"
                        + (f" as {alias.asname}" if alias.asname else ""),
                        alias.name,
                    )
                )

    # Find usage in the code
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Handle module.attribute usage
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    print(f"Analysis of {file_path}:")
    print(f"Total imports: {len(imports)}")
    print("Potentially unused imports:")

    for lineno, import_stmt, name in imports:
        if name not in used_names and name != "*":
            print(f"  Line {lineno}: {import_stmt}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze_imports.py <file>")
        sys.exit(1)

    analyze_imports(sys.argv[1])

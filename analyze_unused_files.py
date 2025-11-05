#!/usr/bin/env python3
"""
Script to analyze unused Python files in the resync/ directory.

This script identifies files that are not imported by any other file
in the project.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple


def _module_is_imported(module_path: str, imported_modules: Set[str]) -> bool:
    """Return True when ``module_path`` appears in ``imported_modules``."""

    return any(
        module_path.startswith(imported) for imported in imported_modules
    )


def get_all_python_files(directory: Path) -> List[Path]:
    """Get all Python files in the directory recursively."""
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    return python_files


def extract_imports(file_path: Path) -> List[str]:
    """Extract all resync imports from a Python file."""
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the AST
        tree = ast.parse(content)

        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith('resync.'):
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith('resync.'):
                    imports.append(node.module)
    except (OSError, ValueError) as e:
        print(f"Error parsing {file_path}: {e}")

    return imports


def build_dependency_graph(python_files: List[Path]) -> Dict[Path, List[str]]:
    """Build a dependency graph showing which files import which modules."""
    dependency_graph = {}

    for file_path in python_files:
        imports = extract_imports(file_path)
        dependency_graph[file_path] = imports

    return dependency_graph


def get_module_from_path(file_path: Path, base_dir: Path) -> str:
    """Convert a file path to a module path."""
    relative_path = file_path.relative_to(base_dir)
    module_parts = list(relative_path.parts)

    # Remove .py extension
    if module_parts[-1].endswith('.py'):
        module_parts[-1] = module_parts[-1][:-3]

    # Remove __init__ from module path
    if module_parts[-1] == '__init__':
        module_parts = module_parts[:-1]

    return '.'.join(module_parts)


def find_unused_files(
    python_files: List[Path],
    dependency_graph: Dict[Path, List[str]],
    base_dir: Path
) -> List[Tuple[Path, str, bool, bool]]:
    """Find files that are not imported by any other file."""
    # Create a set of imported modules
    imported_modules = set()
    for imports in dependency_graph.values():
        for imp in imports:
            # Extract the base module (resync.x.y.z -> resync.x.y)
            parts = imp.split('.')
            if len(parts) >= 2:
                imported_modules.add('.'.join(parts[:2]))
            imported_modules.add(imp)

    # Find files that are not imported
    unused_files = []
    entry_points = {'main.py', 'app.py', '__main__.py', 'run.py', 'server.py'}

    for file_path in python_files:
        module_path = get_module_from_path(file_path, base_dir)

        # Check if this module is imported
        is_imported = _module_is_imported(module_path, imported_modules)

        # Check file characteristics and collect unused files
        file_name = file_path.name
        if (
            not is_imported
            and file_name not in entry_points
            and 'test' not in file_name.lower()
            and 'tests' not in str(file_path).lower()
        ):
            file_str = str(file_path)
            unused_files.append((
                file_path, module_path,
                file_path.suffix == '.bak',
                'legacy' in file_str.lower()
            ))

    return unused_files


def find_duplicate_files(
    python_files: List[Path],
    base_dir: Path
) -> List[Tuple[List[Path], str]]:
    """Find files with similar names that might be duplicates."""
    # Group files by their base name (without path and extension)
    name_groups = {}

    for file_path in python_files:
        base_name = file_path.stem
        if base_name not in name_groups:
            name_groups[base_name] = []
        name_groups[base_name].append(file_path)

    # Find groups with more than one file
    duplicates = []
    for base_name, files in name_groups.items():
        if len(files) > 1:
            # Check if they're in different directories
            dirs = set(str(f.parent.relative_to(base_dir)) for f in files)
            if len(dirs) > 1:
                duplicates.append((files, base_name))

    return duplicates


def main():
    """Main function to analyze unused files."""
    base_dir = Path('resync')
    if not base_dir.exists():
        print(f"Directory {base_dir} does not exist!")
        return

    python_files = get_all_python_files(base_dir)
    print(f"Found {len(python_files)} Python files in {base_dir}")

    # Build dependency graph
    dependency_graph = build_dependency_graph(python_files)

    # Find unused files
    unused_files = find_unused_files(python_files, dependency_graph, base_dir)

    # Find duplicate files
    duplicates = find_duplicate_files(python_files, base_dir)

    # Print results
    print("\n=== UNUSED FILES ===")
    print("Files that are not imported by any other file:")
    for file_path, module_path, is_backup, is_legacy in unused_files:
        flags = []
        if is_backup:
            flags.append("BACKUP")
        if is_legacy:
            flags.append("LEGACY")

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {file_path} ({module_path}){flag_str}")

    print("\n=== DUPLICATE FILES ===")
    print("Files with similar names in different directories:")
    for files, base_name in duplicates:
        print(f"\n{base_name}:")
        for file_path in files:
            print(f"  - {file_path}")

    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Total Python files: {len(python_files)}")
    print(f"Unused files: {len(unused_files)}")
    print(f"Duplicate groups: {len(duplicates)}")

    # Create a list of files that can be safely removed
    safely_removable = []
    for file_path, module_path, is_backup, is_legacy in unused_files:
        if is_backup or is_legacy:
            safely_removable.append(file_path)

    print(
        "\nFiles that can be safely removed "
        f"(backups and legacy): {len(safely_removable)}"
    )
    for file_path in safely_removable:
        print(f"  {file_path}")

if __name__ == "__main__":
    main()





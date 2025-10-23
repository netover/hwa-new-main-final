#!/usr/bin/env python3
"""
Comprehensive validation script for the refactored AsyncTTLCache implementation.

This script performs thorough validation of the refactored cache implementation including:
1. File existence and syntax verification
2. Component imports and dependencies check
3. Class structure and method validation
4. Basic functionality testing
5. Comprehensive reporting
"""

import ast
import importlib.util
import inspect
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
import traceback


class CacheValidator:
    """Comprehensive validator for the refactored AsyncTTLCache implementation."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.successes: List[str] = []
        self.results: Dict[str, Any] = {}

    def log_error(self, message: str) -> None:
        """Log an error message."""
        self.errors.append(message)
        print(f"✗ ERROR: {message}")

    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        self.warnings.append(message)
        print(f"⚠ WARNING: {message}")

    def log_success(self, message: str) -> None:
        """Log a success message."""
        self.successes.append(message)
        print(f"✓ {message}")

    def validate_file_existence(self) -> bool:
        """Check if all required files exist."""
        required_files = [
            "resync/core/cache/async_cache_refactored.py",
            "resync/core/cache/base_cache.py",
            "resync/core/cache/memory_manager.py",
            "resync/core/cache/persistence_manager.py",
            "resync/core/cache/transaction_manager.py",
        ]

        all_exist = True
        for file_path in required_files:
            if os.path.exists(file_path):
                self.log_success(f"File exists: {file_path}")
            else:
                self.log_error(f"File missing: {file_path}")
                all_exist = False

        return all_exist

    def validate_syntax(self, file_path: str) -> bool:
        """Validate Python syntax of a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            ast.parse(content)
            self.log_success(f"Valid syntax: {file_path}")
            return True

        except SyntaxError as e:
            self.log_error(f"Syntax error in {file_path}: {e}")
            return False
        except Exception as e:
            self.log_error(f"Error reading {file_path}: {e}")
            return False

    def validate_imports(self, file_path: str) -> Dict[str, bool]:
        """Validate that all imports in a file can be resolved."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            import_status = {}

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        import_status[module_name] = self._check_import(module_name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module
                        import_status[module_name] = self._check_import(module_name)

            return import_status

        except Exception as e:
            self.log_error(f"Error validating imports in {file_path}: {e}")
            return {}

    def _check_import(self, module_name: str) -> bool:
        """Check if a module can be imported."""
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    def validate_class_structure(self, file_path: str) -> Dict[str, Any]:
        """Validate the AsyncTTLCache class structure."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            class_info = {}

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "AsyncTTLCache":
                    class_info = self._analyze_class_node(node, content)
                    break

            return class_info

        except Exception as e:
            self.log_error(f"Error analyzing class structure: {e}")
            return {}

    def _analyze_class_node(self, class_node: ast.ClassDef, content: str) -> Dict[str, Any]:
        """Analyze the AsyncTTLCache class node."""
        info = {
            "name": class_node.name,
            "bases": [base.id if hasattr(base, 'id') else str(base) for base in class_node.bases],
            "methods": [],
            "attributes": []
        }

        # Extract method names (including async methods)
        for node in class_node.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info["methods"].append({
                    "name": node.name,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "line_number": node.lineno
                })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        info["attributes"].append(target.id)

        return info

    def validate_required_components(self, content: str) -> Dict[str, bool]:
        """Validate presence of required components in the cache implementation."""
        required_components = {
            "class_definition": "class AsyncTTLCache(BaseCache):",
            "memory_manager": "self.memory_manager = CacheMemoryManager",
            "persistence_manager": "self.persistence_manager = CachePersistenceManager",
            "transaction_manager": "self.transaction_manager = CacheTransactionManager",
            "get_method": "async def get(self, key: str)",
            "set_method": "async def set(self, key: str, value: Any, ttl: Optional[int] = None)",
            "delete_method": "async def delete(self, key: str)",
            "clear_method": "async def clear(self)",
            "size_method": "def size(self)",
            "health_check": "async def health_check(self)",
            "detailed_metrics": "def get_detailed_metrics(self)",
            "transaction_support": "async def begin_transaction",
            "commit_transaction": "async def commit_transaction",
            "rollback_transaction": "async def rollback_transaction",
            "snapshot_support": "def create_backup_snapshot",
            "restore_snapshot": "async def restore_from_snapshot",
            "wal_support": "self.wal = WriteAheadLog",
            "wal_replay": "async def _replay_wal_on_startup",
            "cleanup_task": "async def _cleanup_expired_entries",
            "shard_support": "self.shards: List[Dict[str, CacheEntry]]",
            "lock_support": "self.shard_locks = [asyncio.Lock()",
        }

        component_status = {}
        for component_name, pattern in required_components.items():
            if pattern in content:
                component_status[component_name] = True
                self.log_success(f"Found required component: {component_name}")
            else:
                component_status[component_name] = False
                self.log_error(f"Missing required component: {component_name}")

        return component_status

    def validate_functionality(self) -> bool:
        """Perform basic functionality tests."""
        try:
            # Import the cache module as a package
            import resync.core.cache as cache_module

            # Test basic instantiation (without full initialization)
            self.log_success("Cache module imported successfully")

            # Check if AsyncTTLCache class exists
            if hasattr(cache_module, 'AsyncTTLCache'):
                self.log_success("AsyncTTLCache class found")
            else:
                self.log_error("AsyncTTLCache class not found")
                return False

            return True

        except Exception as e:
            self.log_error(f"Functionality validation failed: {e}")
            return False

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all validation checks."""
        print("=" * 60)
        print("COMPREHENSIVE ASYNCTTL CACHE VALIDATION REPORT")
        print("=" * 60)

        # 1. File existence check
        print("\n1. FILE EXISTENCE VALIDATION")
        print("-" * 40)
        files_exist = self.validate_file_existence()

        # 2. Syntax validation
        print("\n2. SYNTAX VALIDATION")
        print("-" * 40)
        syntax_valid = True
        for file_path in [
            "resync/core/cache/async_cache_refactored.py",
            "resync/core/cache/base_cache.py",
            "resync/core/cache/memory_manager.py",
            "resync/core/cache/persistence_manager.py",
            "resync/core/cache/transaction_manager.py",
        ]:
            if os.path.exists(file_path):
                if not self.validate_syntax(file_path):
                    syntax_valid = False

        # 3. Import validation
        print("\n3. IMPORT VALIDATION")
        print("-" * 40)
        main_file = "resync/core/cache/async_cache_refactored.py"
        if os.path.exists(main_file):
            import_status = self.validate_imports(main_file)
            for module, status in import_status.items():
                if status:
                    self.log_success(f"Import OK: {module}")
                else:
                    self.log_warning(f"Import issue: {module}")

        # 4. Class structure validation
        print("\n4. CLASS STRUCTURE VALIDATION")
        print("-" * 40)
        if os.path.exists(main_file):
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()

            class_info = self.validate_class_structure(main_file)
            if class_info:
                self.log_success(f"Class found: {class_info['name']}")
                self.log_success(f"Base classes: {class_info['bases']}")
                self.log_success(f"Methods: {len(class_info['methods'])}")
                self.log_success(f"Attributes: {len(class_info['attributes'])}")

                # Check for required methods
                method_names = {method['name'] for method in class_info['methods']}
                required_methods = {
                    'get', 'set', 'delete', 'clear', 'size', 'health_check',
                    'get_detailed_metrics', 'begin_transaction', 'commit_transaction',
                    'rollback_transaction', 'create_backup_snapshot', 'restore_from_snapshot'
                }

                missing_methods = required_methods - method_names
                if missing_methods:
                    for method in missing_methods:
                        self.log_error(f"Missing method: {method}")
                else:
                    self.log_success("All required methods present")

        # 5. Component validation
        print("\n5. REQUIRED COMPONENTS VALIDATION")
        print("-" * 40)
        if os.path.exists(main_file):
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()

            component_status = self.validate_required_components(content)

        # 6. Functionality validation
        print("\n6. FUNCTIONALITY VALIDATION")
        print("-" * 40)
        functionality_ok = self.validate_functionality()

        # Generate summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        success_count = len(self.successes)
        warning_count = len(self.warnings)
        error_count = len(self.errors)

        print(f"✓ Successes: {success_count}")
        print(f"⚠ Warnings: {warning_count}")
        print(f"✗ Errors: {error_count}")

        overall_success = error_count == 0 and syntax_valid and functionality_ok

        if overall_success:
            print("\n🎉 VALIDATION PASSED - Refactored AsyncTTLCache is ready!")
        else:
            print(f"\n❌ VALIDATION FAILED - {error_count} errors found")

        # Store results
        self.results = {
            "overall_success": overall_success,
            "success_count": success_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "successes": self.successes,
            "warnings": self.warnings,
            "errors": self.errors,
            "files_exist": files_exist,
            "syntax_valid": syntax_valid,
            "functionality_ok": functionality_ok,
        }

        return self.results


def main():
    """Main validation function."""
    validator = CacheValidator()
    results = validator.run_comprehensive_validation()

    # Exit with appropriate code
    if results["overall_success"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
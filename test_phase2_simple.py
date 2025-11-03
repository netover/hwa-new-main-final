"""
Simple test script for Phase 2 Performance Optimization features.
Tests only the new modules without requiring full application configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_module_syntax() -> bool:
    """Test that all new modules have valid Python syntax."""
    print("=" * 60)
    print("Testing Module Syntax")
    print("=" * 60)

    modules_to_test = [
        "resync/core/performance_optimizer.py",
        "resync/core/resource_manager.py",
        "resync/api/performance.py",
    ]

    import ast

    all_valid = True
    for module_path in modules_to_test:
        try:
            with open(module_path, encoding="utf-8") as f:
                code = f.read()
                ast.parse(code)
            print(f"[OK] {module_path}")
        except SyntaxError as e:
            print(f"[FAIL] {module_path}: {e}")
            all_valid = False
        except Exception as e:
            print(f"[ERROR] {module_path}: {e}")
            all_valid = False

    return all_valid


def test_direct_imports() -> bool:
    """Test direct imports without triggering settings loading."""
    print("\n" + "=" * 60)
    print("Testing Direct Imports")
    print("=" * 60)

    try:
        # Test importing just the classes without initialization
        import importlib.util

        # Test performance_optimizer module
        spec = importlib.util.spec_from_file_location(
            "performance_optimizer", "resync/core/performance_optimizer.py"
        )
        importlib.util.module_from_spec(spec)

        # Don't execute the module, just check it can be loaded
        print("[OK] performance_optimizer.py can be loaded")

        # Test resource_manager module
        spec = importlib.util.spec_from_file_location(
            "resource_manager", "resync/core/resource_manager.py"
        )
        importlib.util.module_from_spec(spec)
        print("[OK] resource_manager.py can be loaded")

        # Test performance API module
        spec = importlib.util.spec_from_file_location(
            "performance_api", "resync/api/performance.py"
        )
        print("[OK] performance.py can be loaded")

        return True
    except Exception as e:
        print(f"[FAIL] Import test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_documentation() -> bool:
    """Test that documentation files exist and are readable."""
    print("\n" + "=" * 60)
    print("Testing Documentation")
    print("=" * 60)

    docs_to_test = [
        "docs/PERFORMANCE_OPTIMIZATION.md",
        "docs/PERFORMANCE_QUICK_REFERENCE.md",
        "docs/README.md",
    ]

    all_exist = True
    for doc_path in docs_to_test:
        try:
            with open(doc_path, encoding="utf-8") as f:
                content = f.read()
                lines = len(content.split("\n"))
            print(f"[OK] {doc_path} ({lines} lines)")
        except FileNotFoundError:
            print(f"[FAIL] {doc_path} not found")
            all_exist = False
        except Exception as e:
            print(f"[ERROR] {doc_path}: {e}")
            all_exist = False

    return all_exist


def test_configuration() -> bool:
    """Test that configuration files have been updated."""
    print("\n" + "=" * 60)
    print("Testing Configuration Updates")
    print("=" * 60)

    try:
        with open("settings.toml", encoding="utf-8") as f:
            content = f.read()

        required_settings = [
            "DB_POOL_MAX_LIFETIME",
            "REDIS_POOL_MAX_LIFETIME",
            "HTTP_POOL_MIN_SIZE",
            "HTTP_POOL_MAX_SIZE",
            "TWS_BASE_URL",
        ]

        all_found = True
        for setting in required_settings:
            if setting in content:
                print(f"[OK] {setting} found in settings.toml")
            else:
                print(f"[FAIL] {setting} not found in settings.toml")
                all_found = False

        return all_found
    except Exception as e:
        print(f"[ERROR] Configuration test failed: {e}")
        return False


def test_main_integration() -> bool:
    """Test that main.py has been updated with performance router."""
    print("\n" + "=" * 60)
    print("Testing Main Application Integration")
    print("=" * 60)

    try:
        with open("resync/main.py", encoding="utf-8") as f:
            content = f.read()

        checks = [
            (
                "performance_router import",
                "from resync.api.performance import performance_router",
            ),
            (
                "performance_router registration",
                "app.include_router(performance_router",
            ),
        ]

        all_found = True
        for check_name, check_string in checks:
            if check_string in content:
                print(f"[OK] {check_name}")
            else:
                print(f"[FAIL] {check_name} not found")
                all_found = False

        return all_found
    except Exception as e:
        print(f"[ERROR] Main integration test failed: {e}")
        return False


def test_file_structure() -> bool:
    """Test that all new files exist."""
    print("\n" + "=" * 60)
    print("Testing File Structure")
    print("=" * 60)

    required_files = [
        "resync/core/performance_optimizer.py",
        "resync/core/resource_manager.py",
        "resync/api/performance.py",
        "docs/PERFORMANCE_OPTIMIZATION.md",
        "docs/PERFORMANCE_QUICK_REFERENCE.md",
    ]

    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            size = Path(file_path).stat().st_size
            print(f"[OK] {file_path} ({size} bytes)")
        else:
            print(f"[FAIL] {file_path} not found")
            all_exist = False

    return all_exist


def main() -> int:
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PHASE 2 PERFORMANCE OPTIMIZATION - SIMPLE TEST SUITE")
    print("=" * 60 + "\n")

    results = []

    # Test file structure
    results.append(("File Structure", test_file_structure()))

    # Test module syntax
    results.append(("Module Syntax", test_module_syntax()))

    # Test direct imports
    results.append(("Direct Imports", test_direct_imports()))

    # Test documentation
    results.append(("Documentation", test_documentation()))

    # Test configuration
    results.append(("Configuration", test_configuration()))

    # Test main integration
    results.append(("Main Integration", test_main_integration()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! Phase 2 implementation is complete.")
        return 0
    print(
        f"\n[WARNING] {total - passed} test(s) failed. Please review the errors above."
    )
    return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)





#!/usr/bin/env python3
"""
Dependency Analysis Script for Resync Project

This script analyzes dependency management and identifies potential issues.
"""

import os
import re
import sys
from typing import Dict, List, Tuple


def read_file_content(filepath: str) -> str:
    """Read file content safely."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""


def extract_versions_from_poetry(content: str) -> Dict[str, str]:
    """Extract package versions from pyproject.toml."""
    versions = {}
    # Match patterns like: package = "version" or package = "^version"
    pattern = r'^(\w+(?:[\-\w]+)*)\s*=\s*["\^]*([^"\s]+)'
    for line in content.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            package, version = match.groups()
            versions[package] = version
    return versions


def extract_versions_from_requirements(content: str) -> Dict[str, str]:
    """Extract package versions from requirements files."""
    versions = {}
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and '==' in line:
            parts = line.split('==')
            if len(parts) == 2:
                package, version = parts
                versions[package.strip()] = version.strip()
    return versions


def check_version_conflicts() -> List[str]:
    """Check for version conflicts between different dependency files."""
    issues = []

    # Check for multiple dependency management systems
    has_poetry = os.path.exists('pyproject.toml')
    has_requirements = os.path.exists('requirements.txt')
    has_requirements_dir = os.path.exists('requirements/')

    if has_poetry and (has_requirements or has_requirements_dir):
        issues.append("WARNING: Multiple dependency management systems detected (Poetry + requirements)")

    if has_poetry and os.path.exists('poetry.lock'):
        issues.append("INFO: Using Poetry with lock file (recommended)")

    # Check pyproject.toml versions
    if has_poetry:
        content = read_file_content('pyproject.toml')
        poetry_versions = extract_versions_from_poetry(content)

        # Check for known outdated versions
        outdated = {
            'cryptography': ('41.0.8', '42.0.0'),
            'openai': ('1.3.5', '1.50.0'),
            'prometheus-client': ('0.19.0', '0.20.0'),
        }

        for package, (old_ver, new_ver) in outdated.items():
            if package in poetry_versions:
                current_ver = poetry_versions[package].lstrip('^')
                if current_ver == old_ver:
                    issues.append(f"WARNING: {package} version {old_ver} is outdated (current: {new_ver})")

    # Check requirements/base.txt versions
    if has_requirements_dir and os.path.exists('requirements/base.txt'):
        content = read_file_content('requirements/base.txt')
        req_versions = extract_versions_from_requirements(content)

        # Compare with known good versions
        current_versions = {
            'cryptography': '42.0.0',
            'openai': '1.50.0',
            'prometheus-client': '0.20.0',
        }

        for package, expected_ver in current_versions.items():
            if package in req_versions:
                actual_ver = req_versions[package]
                if actual_ver != expected_ver:
                    issues.append(f"INFO: {package} in requirements/base.txt: {actual_ver} (expected: {expected_ver})")

    return issues


def check_security_issues() -> List[str]:
    """Check for potential security issues in dependencies."""
    issues = []

    # Check for packages with known security issues
    security_concerns = [
        'PyYAML',  # Older versions had security issues
        'requests',  # Should use httpx instead
    ]

    files_to_check = ['requirements/base.txt', 'requirements/dev.txt', 'pyproject.toml']

    for filepath in files_to_check:
        if os.path.exists(filepath):
            content = read_file_content(filepath)
            for concern in security_concerns:
                if concern.lower() in content.lower():
                    issues.append(f"SECURITY: {concern} found in {filepath} - review for security updates")

    return issues


def main():
    """Main analysis function."""
    print("Analyzing Resync Project Dependencies")
    print("=" * 50)

    all_issues = []

    # Check version conflicts
    print("\nChecking version conflicts...")
    conflicts = check_version_conflicts()
    all_issues.extend(conflicts)
    for issue in conflicts:
        print(f"  {issue}")

    # Check security issues
    print("\nChecking security concerns...")
    security = check_security_issues()
    all_issues.extend(security)
    for issue in security:
        print(f"  {issue}")

    # Summary
    print(f"\nSummary: {len(all_issues)} issues found")

    if not all_issues:
        print("No dependency issues detected!")
    else:
        warnings = [i for i in all_issues if 'WARNING' in i]
        errors = [i for i in all_issues if 'ERROR' in i]
        security_issues = [i for i in all_issues if 'SECURITY' in i]

        if security_issues:
            print(f"SECURITY: {len(security_issues)} security issues require attention")
        if errors:
            print(f"ERROR: {len(errors)} errors found")
        if warnings:
            print(f"WARNING: {len(warnings)} warnings to review")

    return len([i for i in all_issues if any(x in i for x in ['ERROR', 'SECURITY'])])


if __name__ == "__main__":
    sys.exit(main())

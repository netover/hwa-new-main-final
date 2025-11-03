#!/usr/bin/env python3
"""
Pyflakes Issues Fixer - Automated script to fix Pyflakes issues systematically.

This script provides automated fixes for common Pyflakes issues including:
- Unused imports
- Undefined names
- F-string placeholders
- Forward annotation syntax errors
- Unused variables
- Redefinitions

Usage:
    python scripts/fix_pyflakes_issues.py [options]

Options:
    --dry-run          Show what would be fixed without making changes
    --backup           Create backup files before making changes
    --verbose          Enable verbose logging
    --phase PHASE      Run only specific phase (forward_annotations, undefined_names, etc.)
    --report FILE      Generate detailed report to specified file
"""

import argparse
import logging
import os
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class PyflakesIssue:
    """Represents a single Pyflakes issue."""

    file_path: str
    line: int
    column: int
    message: str
    issue_type: str
    fixed: bool = False


@dataclass
class FixReport:
    """Report of fixes applied."""

    total_issues: int = 0
    fixed_issues: int = 0
    failed_fixes: int = 0
    issues_by_type: dict[str, int] = field(default_factory=dict)
    issues_by_file: dict[str, list[PyflakesIssue]] = field(
        default_factory=lambda: defaultdict(list)
    )
    errors: list[str] = field(default_factory=list)


class PyflakesFixer:
    """Main automation orchestrator for Pyflakes fixes."""

    def __init__(
        self, pyflakes_output: str, dry_run: bool = False, backup: bool = True
    ):
        self.pyflakes_output = pyflakes_output
        self.dry_run = dry_run
        self.backup = backup
        self.issues: list[PyflakesIssue] = []
        self.report = FixReport()
        self.logger = logging.getLogger(__name__)
        self.backups: dict[str, str] = {}  # file -> backup_path

        # Parse issues from pyflakes output
        self._parse_pyflakes_output()

    def _parse_pyflakes_output(self) -> None:
        """Parse pyflakes output and categorize issues."""
        # More robust pattern that handles various formats
        pattern = r"^(.+?):(\d+):(\d+):\s*(.+)"
        issue_patterns = {
            "unused_import": re.compile(r"'.+' imported but unused"),
            "undefined_name": re.compile(r"undefined name '(.+)'"),
            "fstring_placeholder": re.compile(r"f-string is missing placeholders"),
            "forward_annotation": re.compile(r"syntax error in forward annotation"),
            "unused_variable": re.compile(
                r"local variable '.+' is assigned to but never used"
            ),
            "redefinition": re.compile(r"redefinition of unused '(.+)' from line \d+"),
        }

        lines = self.pyflakes_output.strip().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Try to match the pattern
            match = re.match(pattern, line)
            if match:
                file_path, line_num, col_num, message = match.groups()
                try:
                    line_num, col_num = int(line_num), int(col_num)
                except ValueError:
                    self.logger.warning(f"Could not parse line numbers in: {line}")
                    i += 1
                    continue

                # Determine issue type
                issue_type = "unknown"
                for type_name, pat in issue_patterns.items():
                    if pat.search(message):
                        issue_type = type_name
                        break

                issue = PyflakesIssue(
                    file_path=file_path,
                    line=line_num,
                    column=col_num,
                    message=message,
                    issue_type=issue_type,
                )

                self.issues.append(issue)
                self.report.issues_by_type[issue_type] = (
                    self.report.issues_by_type.get(issue_type, 0) + 1
                )
                self.report.issues_by_file[file_path].append(issue)
            else:
                self.logger.warning(f"Could not parse line: {line}")

            i += 1

        self.report.total_issues = len(self.issues)
        self.logger.info(f"Parsed {len(self.issues)} issues from pyflakes output")

    def run_all_fixes(self) -> FixReport:
        """Run all fix phases in order."""
        phases = [
            ("forward_annotations", self.fix_forward_annotations),
            ("undefined_names", self.fix_undefined_names),
            ("fstring_placeholders", self.fix_fstring_placeholders),
            ("unused_imports", self.remove_unused_imports),
            ("unused_variables", self.remove_unused_variables),
            ("redefinitions", self.fix_redefinitions),
        ]

        for phase_name, phase_method in phases:
            self.logger.info(f"Starting phase: {phase_name}")
            try:
                phase_method()
            except Exception as e:
                self.logger.error(f"Error in phase {phase_name}: {e}")
                self.report.errors.append(f"Phase {phase_name} failed: {e}")

        return self.report

    def fix_forward_annotations(self) -> None:
        """Fix syntax errors in forward annotations."""
        # Forward annotations like '^[a-zA-Z0-9_.-]+$' need to be quoted
        issues = [
            i
            for i in self.issues
            if i.issue_type == "forward_annotation" and not i.fixed
        ]

        for issue in issues:
            try:
                self._fix_forward_annotation(issue)
            except Exception as e:
                self.logger.error(
                    f"Failed to fix forward annotation in {issue.file_path}:{issue.line}: {e}"
                )
                self.report.failed_fixes += 1

    def _fix_forward_annotation(self, issue: PyflakesIssue) -> None:
        """Fix a single forward annotation issue."""
        # Read the file
        with open(issue.file_path, encoding="utf-8") as f:
            lines = f.readlines()

        line_content = lines[issue.line - 1]

        # Look for regex patterns that need quoting
        # Pattern: '^[a-zA-Z0-9_.-]+$'
        regex_pattern = re.search(r"'(\^[^']+\$)'", line_content)
        if regex_pattern:
            old_pattern = regex_pattern.group(1)
            new_pattern = f'"{old_pattern}"'
            lines[issue.line - 1] = line_content.replace(
                f"'{old_pattern}'", new_pattern
            )

            if not self.dry_run:
                self._write_file_with_backup(issue.file_path, lines)

            issue.fixed = True
            self.report.fixed_issues += 1
            self.logger.info(
                f"Fixed forward annotation in {issue.file_path}:{issue.line}"
            )

    def fix_undefined_names(self) -> None:
        """Fix undefined name issues."""
        issues = [
            i for i in self.issues if i.issue_type == "undefined_name" and not i.fixed
        ]

        for issue in issues:
            try:
                self._fix_undefined_name(issue)
            except Exception as e:
                self.logger.error(
                    f"Failed to fix undefined name in {issue.file_path}:{issue.line}: {e}"
                )
                self.report.failed_fixes += 1

    def _fix_undefined_name(self, issue: PyflakesIssue) -> None:
        """Fix a single undefined name issue."""
        # Extract the undefined name from the message
        match = re.search(r"undefined name '(.+)'", issue.message)
        if not match:
            return

        undefined_name = match.group(1)

        # Read the file
        with open(issue.file_path, encoding="utf-8") as f:
            content = f.read()

        # Common fixes based on context
        fixes = {
            "sys": "import sys",
            "re": "import re",
            "logging": "import logging",
            "Optional": "from typing import Optional",
            "List": "from typing import List",
            "Dict": "from typing import Dict",
            "Any": "from typing import Any",
            "Union": "from typing import Union",
            "Tuple": "from typing import Tuple",
            "Set": "from typing import Set",
            "Callable": "from typing import Callable",
            "Awaitable": "from typing import Awaitable",
            "Type": "from typing import Type",
            "cast": "from typing import cast",
            "get_type_hints": "from typing import get_type_hints",
            "TYPE_CHECKING": "from typing import TYPE_CHECKING",
            "auto": "from enum import auto",
            "field": "from dataclasses import field",
            "asdict": "from dataclasses import asdict",
            "dataclass": "from dataclasses import dataclass",
            "abstractmethod": "from abc import abstractmethod",
            "ABC": "from abc import ABC",
        }

        if undefined_name in fixes:
            # Add the import at the top
            lines = content.splitlines()
            import_line = fixes[undefined_name]

            # Find the right place to insert the import
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.startswith("#"):
                    continue
                if line.startswith(("import ", "from ")):
                    insert_pos = i + 1
                else:
                    break

            lines.insert(insert_pos, import_line)

            if not self.dry_run:
                self._write_file_with_backup(issue.file_path, lines)

            issue.fixed = True
            self.report.fixed_issues += 1
            self.logger.info(f"Added import for {undefined_name} in {issue.file_path}")

    def fix_fstring_placeholders(self) -> None:
        """Fix f-strings missing placeholders."""
        issues = [
            i
            for i in self.issues
            if i.issue_type == "fstring_placeholder" and not i.fixed
        ]

        for issue in issues:
            try:
                self._fix_fstring_placeholder(issue)
            except Exception as e:
                self.logger.error(
                    f"Failed to fix f-string in {issue.file_path}:{issue.line}: {e}"
                )
                self.report.failed_fixes += 1

    def _fix_fstring_placeholder(self, issue: PyflakesIssue) -> None:
        """Fix a single f-string placeholder issue."""
        # Read the file
        with open(issue.file_path, encoding="utf-8") as f:
            lines = f.readlines()

        line_content = lines[issue.line - 1]

        # Look for f-strings without placeholders
        # Pattern: f"some text" -> "some text"
        fstring_match = re.search(r'f(["\'])([^"\']*)\1', line_content)
        if fstring_match:
            quote = fstring_match.group(1)
            content = fstring_match.group(2)
            new_line = line_content.replace(
                f"f{quote}{content}{quote}", f"{quote}{content}{quote}"
            )

            lines[issue.line - 1] = new_line

            if not self.dry_run:
                self._write_file_with_backup(issue.file_path, lines)

            issue.fixed = True
            self.report.fixed_issues += 1
            self.logger.info(
                f"Fixed f-string placeholder in {issue.file_path}:{issue.line}"
            )

    def remove_unused_imports(self) -> None:
        """Remove unused imports."""
        issues = [
            i for i in self.issues if i.issue_type == "unused_import" and not i.fixed
        ]

        # Group by file
        by_file = defaultdict(list)
        for issue in issues:
            by_file[issue.file_path].append(issue)

        for file_path, file_issues in by_file.items():
            try:
                self._remove_unused_imports_from_file(file_path, file_issues)
            except Exception as e:
                self.logger.error(
                    f"Failed to remove unused imports from {file_path}: {e}"
                )
                self.report.failed_fixes += len(file_issues)

    def _remove_unused_imports_from_file(
        self, file_path: str, issues: list[PyflakesIssue]
    ) -> None:
        """Remove unused imports from a single file."""
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Extract unused import names
        unused_imports = set()
        for issue in issues:
            match = re.search(r"'(.+)' imported but unused", issue.message)
            if match:
                unused_imports.add(match.group(1))

        # Remove the unused imports
        new_lines = []
        removed_count = 0

        for _line_num, line in enumerate(lines, 1):
            skip_line = False

            # Check if this line has an unused import
            for unused in unused_imports:
                if f"import {unused}" in line or f"from {unused}" in line:
                    # Check if it's part of a multi-line import
                    if line.strip().endswith("\\") or (
                        line.strip().startswith("from ") and "," in line
                    ):
                        # For simplicity, skip complex multi-line imports
                        continue
                    skip_line = True
                    removed_count += 1
                    break

            if not skip_line:
                new_lines.append(line)

        if removed_count > 0 and not self.dry_run:
            self._write_file_with_backup(file_path, new_lines)

        # Mark issues as fixed
        for issue in issues:
            if removed_count > 0:
                issue.fixed = True
                self.report.fixed_issues += 1

        self.logger.info(f"Removed {removed_count} unused imports from {file_path}")

    def remove_unused_variables(self) -> None:
        """Remove unused variables."""
        issues = [
            i for i in self.issues if i.issue_type == "unused_variable" and not i.fixed
        ]

        for issue in issues:
            try:
                self._remove_unused_variable(issue)
            except Exception as e:
                self.logger.error(
                    f"Failed to remove unused variable in {issue.file_path}:{issue.line}: {e}"
                )
                self.report.failed_fixes += 1

    def _remove_unused_variable(self, issue: PyflakesIssue) -> None:
        """Remove a single unused variable."""
        # Read the file
        with open(issue.file_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Extract variable name
        match = re.search(
            r"local variable '(.+)' is assigned to but never used", issue.message
        )
        if not match:
            return

        var_name = match.group(1)
        line_content = lines[issue.line - 1]

        # Simple case: variable assignment on its own line
        if (
            f"{var_name} =" in line_content
            and not line_content.strip().startswith("if ")
            and not line_content.strip().startswith("for ")
        ):
            # Remove the entire line
            lines.pop(issue.line - 1)

            if not self.dry_run:
                self._write_file_with_backup(issue.file_path, lines)

            issue.fixed = True
            self.report.fixed_issues += 1
            self.logger.info(
                f"Removed unused variable '{var_name}' in {issue.file_path}:{issue.line}"
            )

    def fix_redefinitions(self) -> None:
        """Fix redefinition issues."""
        issues = [
            i for i in self.issues if i.issue_type == "redefinition" and not i.fixed
        ]

        for issue in issues:
            try:
                self._fix_redefinition(issue)
            except Exception as e:
                self.logger.error(
                    f"Failed to fix redefinition in {issue.file_path}:{issue.line}: {e}"
                )
                self.report.failed_fixes += 1

    def _fix_redefinition(self, issue: PyflakesIssue) -> None:
        """Fix a single redefinition issue."""
        # Read the file
        with open(issue.file_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Extract the redefined name
        match = re.search(r"redefinition of unused '(.+)' from line \d+", issue.message)
        if not match:
            return

        redefined_name = match.group(1)
        line_content = lines[issue.line - 1]

        # Remove the redefinition line
        if redefined_name in line_content:
            lines.pop(issue.line - 1)

            if not self.dry_run:
                self._write_file_with_backup(issue.file_path, lines)

            issue.fixed = True
            self.report.fixed_issues += 1
            self.logger.info(
                f"Removed redefinition of '{redefined_name}' in {issue.file_path}:{issue.line}"
            )

    def _write_file_with_backup(self, file_path: str, lines: list[str]) -> None:
        """Write file with backup if enabled."""
        if self.backup and file_path not in self.backups:
            backup_path = f"{file_path}.backup"
            shutil.copy2(file_path, backup_path)
            self.backups[file_path] = backup_path
            self.logger.info(f"Created backup: {backup_path}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def rollback_changes(self) -> None:
        """Rollback all changes by restoring backups."""
        for original, backup in self.backups.items():
            if os.path.exists(backup):
                shutil.copy2(backup, original)
                os.remove(backup)
                self.logger.info(f"Restored {original} from backup")

        self.backups.clear()

    def generate_report(self, output_file: str | None = None) -> str:
        """Generate a comprehensive fix report."""
        report_lines = [
            "Pyflakes Issues Fix Report",
            "=" * 50,
            f"Total issues found: {self.report.total_issues}",
            f"Issues fixed: {self.report.fixed_issues}",
            f"Failed fixes: {self.report.failed_fixes}",
            "",
            "Issues by type:",
        ]

        for issue_type, count in self.report.issues_by_type.items():
            report_lines.append(f"  {issue_type}: {count}")

        report_lines.append("")
        report_lines.append("Issues by file:")

        for file_path, issues in self.report.issues_by_file.items():
            fixed_count = sum(1 for i in issues if i.fixed)
            total_count = len(issues)
            report_lines.append(f"  {file_path}: {fixed_count}/{total_count} fixed")

        if self.report.errors:
            report_lines.append("")
            report_lines.append("Errors encountered:")
            for error in self.report.errors:
                report_lines.append(f"  - {error}")

        report_text = "\n".join(report_lines)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report_text)
            self.logger.info(f"Report saved to {output_file}")

        return report_text


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Automated Pyflakes issues fixer")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup files before making changes",
    )
    parser.add_argument(
        "--no-backup",
        action="store_false",
        dest="backup",
        help="Don't create backup files",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--phase",
        choices=[
            "forward_annotations",
            "undefined_names",
            "fstring_placeholders",
            "unused_imports",
            "unused_variables",
            "redefinitions",
        ],
        help="Run only specific phase",
    )
    parser.add_argument(
        "--report", type=str, help="Generate detailed report to specified file"
    )
    parser.add_argument(
        "--pyflakes-output",
        type=str,
        default="pyflakes_output.txt",
        help="Path to pyflakes output file",
    )

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")

    # Read pyflakes output
    if not os.path.exists(args.pyflakes_output):
        print(f"Error: Pyflakes output file '{args.pyflakes_output}' not found")
        sys.exit(1)

    with open(args.pyflakes_output, encoding="utf-8") as f:
        pyflakes_output = f.read()

    # Create fixer
    fixer = PyflakesFixer(pyflakes_output, dry_run=args.dry_run, backup=args.backup)

    print(f"Found {fixer.report.total_issues} Pyflakes issues")

    # Run fixes
    if args.phase:
        # Run specific phase
        phase_method = getattr(fixer, f"fix_{args.phase}")
        try:
            phase_method()
        except Exception as e:
            print(f"Error running phase {args.phase}: {e}")
            sys.exit(1)
    else:
        # Run all phases
        fixer.run_all_fixes()

    # Generate report
    report = fixer.generate_report(args.report)
    print("\n" + report)

    if fixer.dry_run:
        print("\nDRY RUN - No changes were made")
    else:
        print(f"\nFixed {fixer.report.fixed_issues} issues")


if __name__ == "__main__":
    main()






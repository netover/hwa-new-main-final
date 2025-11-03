#!/usr/bin/env python3
"""
Script para consolidar e processar resultados de ferramentas de análise de código Python.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Issue:
    tool: str
    file: str
    line: int
    column: int
    code: str
    message: str
    severity: Severity
    category: str


class ResultProcessor:
    def __init__(self, reports_dir: str = "analysis_reports"):
        self.reports_dir = Path(reports_dir)
        self.issues: List[Issue] = []
        self.severity_weights = {
            Severity.CRITICAL: 1000,
            Severity.HIGH: 100,
            Severity.MEDIUM: 10,
            Severity.LOW: 1,
            Severity.INFO: 0.1
        }
    
    def process_pylint_results(self) -> List[Issue]:
        """Processa resultados do pylint."""
        issues = []
        file_path = self.reports_dir / "pylint_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: arquivo:linha:coluna: código mensagem
                match = re.match(r'^([^:]+):(\d+):(\d+): ([A-Z]\d+): (.+)', line.strip())
                if match:
                    file, line, column, code, message = match.groups()
                    severity = self._determine_pylint_severity(code)
                    category = self._determine_pylint_category(code)
                    
                    issues.append(Issue(
                        tool="pylint",
                        file=file,
                        line=int(line),
                        column=int(column),
                        code=code,
                        message=message,
                        severity=severity,
                        category=category
                    ))
        
        return issues
    
    def process_pyright_results(self) -> List[Issue]:
        """Processa resultados do pyright."""
        issues = []
        file_path = self.reports_dir / "pyright_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: arquivo:linha:coluna - severidade: mensagem
                match = re.match(r'^([^:]+):(\d+):(\d+) - (\w+): (.+)', line.strip())
                if match:
                    file, line, column, severity_str, message = match.groups()
                    severity = self._determine_pyright_severity(severity_str)
                    category = self._determine_pyright_category(message)
                    
                    issues.append(Issue(
                        tool="pyright",
                        file=file,
                        line=int(line),
                        column=int(column),
                        code=severity_str,
                        message=message,
                        severity=severity,
                        category=category
                    ))
        
        return issues
    
    def process_mypy_results(self) -> List[Issue]:
        """Processa resultados do mypy."""
        issues = []
        file_path = self.reports_dir / "mypy_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: arquivo:linha: erro: mensagem
                match = re.match(r'^([^:]+):(\d+): (error|note|warning): (.+)', line.strip())
                if match:
                    file, line, severity_str, message = match.groups()
                    severity = self._determine_mypy_severity(severity_str)
                    category = self._determine_mypy_category(message)
                    
                    issues.append(Issue(
                        tool="mypy",
                        file=file,
                        line=int(line),
                        column=0,
                        code=severity_str,
                        message=message,
                        severity=severity,
                        category=category
                    ))
        
        return issues
    
    def process_flake8_results(self) -> List[Issue]:
        """Processa resultados do flake8."""
        issues = []
        file_path = self.reports_dir / "flake8_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: arquivo:linha:coluna: código mensagem
                match = re.match(r'^([^:]+):(\d+):(\d+): ([A-Z]\d+) (.+)', line.strip())
                if match:
                    file, line, column, code, message = match.groups()
                    severity = self._determine_flake8_severity(code)
                    category = self._determine_flake8_category(code)
                    
                    issues.append(Issue(
                        tool="flake8",
                        file=file,
                        line=int(line),
                        column=int(column),
                        code=code,
                        message=message,
                        severity=severity,
                        category=category
                    ))
        
        return issues
    
    def process_pyflakes_results(self) -> List[Issue]:
        """Processa resultados do pyflakes."""
        issues = []
        file_path = self.reports_dir / "pyflakes_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: arquivo:linha: mensagem
                match = re.match(r'^([^:]+):(\d+): (.+)', line.strip())
                if match:
                    file, line, message = match.groups()
                    severity = self._determine_pyflakes_severity(message)
                    category = self._determine_pyflakes_category(message)
                    
                    issues.append(Issue(
                        tool="pyflakes",
                        file=file,
                        line=int(line),
                        column=0,
                        code="PYF",
                        message=message,
                        severity=severity,
                        category=category
                    ))
        
        return issues
    
    def process_radon_results(self) -> List[Issue]:
        """Processa resultados do radon."""
        issues = []
        file_path = self.reports_dir / "radon_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            current_file = None
            for line in f:
                # Verifica se é uma linha de arquivo
                file_match = re.match(r'^([^:]+)$', line.strip())
                if file_match:
                    current_file = file_match.group(1)
                    continue
                
                # Formato:    M 319:4 APIGateway.handle_request - C (16)
                match = re.match(r'^\s+[MF] (\d+):(\d+) ([^-]+) - ([A-Z]) \((\d+)\)', line.strip())
                if match and current_file:
                    line_num, column, function, complexity_letter, complexity_value = match.groups()
                    complexity = int(complexity_value)
                    severity = self._determine_radon_severity(complexity)
                    
                    issues.append(Issue(
                        tool="radon",
                        file=current_file,
                        line=int(line_num),
                        column=int(column),
                        code=f"CC{complexity_letter}",
                        message=f"Function '{function}' has cyclomatic complexity {complexity}",
                        severity=severity,
                        category="complexity"
                    ))
        
        return issues
    
    def process_bandit_results(self) -> List[Issue]:
        """Processa resultados do bandit."""
        issues = []
        file_path = self.reports_dir / "bandit_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            current_issue = {}
            for line in f:
                # Início de uma nova issue
                if line.startswith(">> Issue:"):
                    if current_issue:
                        severity = self._determine_bandit_severity(current_issue.get("severity", "Low"))
                        category = self._determine_bandit_category(current_issue.get("code", ""))
                        
                        issues.append(Issue(
                            tool="bandit",
                            file=current_issue.get("file", ""),
                            line=current_issue.get("line", 0),
                            column=0,
                            code=current_issue.get("code", ""),
                            message=current_issue.get("message", ""),
                            severity=severity,
                            category=category
                        ))
                    
                    # Extrai informações da nova issue
                    match = re.match(r'>> Issue: \[([^\]]+)\] (.+)', line.strip())
                    if match:
                        code, message = match.groups()
                        current_issue = {"code": code, "message": message}
                
                # Linha de severidade
                elif line.strip().startswith("Severity:"):
                    severity = line.split(":")[1].strip()
                    current_issue["severity"] = severity
                
                # Linha de localização
                elif line.strip().startswith("Location:"):
                    location = line.split(":")[1].strip()
                    match = re.match(r'([^:]+):(\d+):(\d+)', location)
                    if match:
                        file, line_num, column = match.groups()
                        current_issue["file"] = file
                        current_issue["line"] = int(line_num)
                        current_issue["column"] = int(column)
            
            # Adiciona a última issue se houver
            if current_issue:
                severity = self._determine_bandit_severity(current_issue.get("severity", "Low"))
                category = self._determine_bandit_category(current_issue.get("code", ""))
                
                issues.append(Issue(
                    tool="bandit",
                    file=current_issue.get("file", ""),
                    line=current_issue.get("line", 0),
                    column=0,
                    code=current_issue.get("code", ""),
                    message=current_issue.get("message", ""),
                    severity=severity,
                    category=category
                ))
        
        return issues
    
    def _determine_pylint_severity(self, code: str) -> Severity:
        """Determina a severidade de um código do pylint."""
        if code.startswith('E'):
            return Severity.HIGH
        elif code.startswith('F'):
            return Severity.CRITICAL
        elif code.startswith('W'):
            return Severity.MEDIUM
        elif code.startswith('R'):
            return Severity.MEDIUM
        elif code.startswith('C'):
            return Severity.LOW
        else:
            return Severity.INFO
    
    def _determine_pylint_category(self, code: str) -> str:
        """Determina a categoria de um código do pylint."""
        if code.startswith('E'):
            return "error"
        elif code.startswith('F'):
            return "fatal"
        elif code.startswith('W'):
            return "warning"
        elif code.startswith('R'):
            return "refactor"
        elif code.startswith('C'):
            return "convention"
        else:
            return "info"
    
    def _determine_pyright_severity(self, severity_str: str) -> Severity:
        """Determina a severidade de um código do pyright."""
        if severity_str == "error":
            return Severity.HIGH
        elif severity_str == "warning":
            return Severity.MEDIUM
        elif severity_str == "information":
            return Severity.LOW
        else:
            return Severity.INFO
    
    def _determine_pyright_category(self, message: str) -> str:
        """Determina a categoria de uma mensagem do pyright."""
        if "import" in message.lower():
            return "import"
        elif "type" in message.lower():
            return "type"
        elif "return" in message.lower():
            return "return"
        elif "parameter" in message.lower():
            return "parameter"
        else:
            return "general"
    
    def _determine_mypy_severity(self, severity_str: str) -> Severity:
        """Determina a severidade de um código do mypy."""
        if severity_str == "error":
            return Severity.HIGH
        elif severity_str == "warning":
            return Severity.MEDIUM
        elif severity_str == "note":
            return Severity.LOW
        else:
            return Severity.INFO
    
    def _determine_mypy_category(self, message: str) -> str:
        """Determina a categoria de uma mensagem do mypy."""
        if "type" in message.lower():
            return "type"
        elif "import" in message.lower():
            return "import"
        elif "return" in message.lower():
            return "return"
        elif "annotation" in message.lower():
            return "annotation"
        else:
            return "general"
    
    def _determine_flake8_severity(self, code: str) -> Severity:
        """Determina a severidade de um código do flake8."""
        if code.startswith('E'):
            return Severity.HIGH
        elif code.startswith('W'):
            return Severity.MEDIUM
        elif code.startswith('F'):
            return Severity.CRITICAL
        else:
            return Severity.LOW
    
    def _determine_flake8_category(self, code: str) -> str:
        """Determina a categoria de um código do flake8."""
        if code.startswith('E'):
            return "error"
        elif code.startswith('W'):
            return "warning"
        elif code.startswith('F'):
            return "fatal"
        else:
            return "convention"
    
    def _determine_pyflakes_severity(self, message: str) -> str:
        """Determina a severidade de uma mensagem do pyflakes."""
        if "imported but unused" in message:
            return Severity.LOW
        elif "undefined" in message.lower():
            return Severity.HIGH
        elif "redefined" in message.lower():
            return Severity.MEDIUM
        else:
            return Severity.MEDIUM
    
    def _determine_pyflakes_category(self, message: str) -> str:
        """Determina a categoria de uma mensagem do pyflakes."""
        if "import" in message.lower():
            return "import"
        elif "undefined" in message.lower():
            return "undefined"
        elif "redefined" in message.lower():
            return "redefined"
        else:
            return "general"
    
    def _determine_radon_severity(self, complexity: int) -> Severity:
        """Determina a severidade baseada na complexidade ciclomática."""
        if complexity >= 20:
            return Severity.CRITICAL
        elif complexity >= 15:
            return Severity.HIGH
        elif complexity >= 10:
            return Severity.MEDIUM
        elif complexity >= 5:
            return Severity.LOW
        else:
            return Severity.INFO
    
    def _determine_bandit_severity(self, severity_str: str) -> Severity:
        """Determina a severidade de um código do bandit."""
        if severity_str == "High":
            return Severity.CRITICAL
        elif severity_str == "Medium":
            return Severity.HIGH
        elif severity_str == "Low":
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    def _determine_bandit_category(self, code: str) -> str:
        """Determina a categoria de um código do bandit."""
        if code.startswith("B1"):
            return "hardcoded"
        elif code.startswith("B3"):
            return "crypto"
        elif code.startswith("B5"):
            return "weak"
        elif code.startswith("B6"):
            return "injection"
        elif code.startswith("B7"):
            return "exec"
        elif code.startswith("B9"):
            return "debug"
        elif code.startswith("B1"):
            return "assert"
        else:
            return "security"
    
    def consolidate_results(self) -> List[Issue]:
        """Consolida resultados de todas as ferramentas."""
        all_issues = []
        
        # Processa resultados de cada ferramenta
        all_issues.extend(self.process_pylint_results())
        all_issues.extend(self.process_pyright_results())
        all_issues.extend(self.process_mypy_results())
        all_issues.extend(self.process_flake8_results())
        all_issues.extend(self.process_pyflakes_results())
        all_issues.extend(self.process_radon_results())
        all_issues.extend(self.process_bandit_results())
        
        # Remove duplicatas (mesmo arquivo, linha e mensagem similar)
        unique_issues = []
        seen = set()
        
        for issue in all_issues:
            key = (issue.file, issue.line, issue.code, issue.message[:50])
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)
        
        # Ordena por severidade (mais crítica primeiro)
        unique_issues.sort(key=lambda x: (
            -self.severity_weights[x.severity],
            x.file,
            x.line
        ))
        
        return unique_issues
    
    def generate_report(self, issues: List[Issue], output_file: str = None) -> str:
        """Gera um relatório formatado das issues."""
        if not output_file:
            output_file = str(self.reports_dir / "consolidated_report.txt")
        
        report_lines = []
        report_lines.append("# RELATÓRIO CONSOLIDADO DE ANÁLISE DE CÓDIGO")
        report_lines.append(f"Total de Issues: {len(issues)}")
        report_lines.append("")
        
        # Agrupa por severidade
        by_severity = {}
        for issue in issues:
            if issue.severity not in by_severity:
                by_severity[issue.severity] = []
            by_severity[issue.severity].append(issue)
        
        # Exibe resumo por severidade
        report_lines.append("## RESUMO POR SEVERIDADE")
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            count = len(by_severity.get(severity, []))
            if count > 0:
                report_lines.append(f"- {severity.value.upper()}: {count}")
        report_lines.append("")
        
        # Agrupa por ferramenta
        by_tool = {}
        for issue in issues:
            if issue.tool not in by_tool:
                by_tool[issue.tool] = []
            by_tool[issue.tool].append(issue)
        
        # Exibe resumo por ferramenta
        report_lines.append("## RESUMO POR FERRAMENTA")
        for tool, tool_issues in by_tool.items():
            report_lines.append(f"- {tool}: {len(tool_issues)} issues")
        report_lines.append("")
        
        # Exibe as 20 issues mais críticas
        report_lines.append("## TOP 20 ISSUES MAIS CRÍTICAS")
        report_lines.append("")
        
        for i, issue in enumerate(issues[:20], 1):
            report_lines.append(f"### {i}. {issue.tool.upper()} - {issue.code}")
            report_lines.append(f"**Arquivo:** {issue.file}:{issue.line}")
            report_lines.append(f"**Severidade:** {issue.severity.value.upper()}")
            report_lines.append(f"**Categoria:** {issue.category}")
            report_lines.append(f"**Mensagem:** {issue.message}")
            report_lines.append("")
        
        # Escreve o relatório
        report_content = "\n".join(report_lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return report_content


if __name__ == "__main__":
    import os
    # Usa o caminho absoluto do diretório atual
    current_dir = os.path.dirname(os.path.abspath(__file__))
    processor = ResultProcessor(current_dir)
    issues = processor.consolidate_results()
    report = processor.generate_report(issues)
    print(f"Relatório gerado com {len(issues)} issues.")
    print(f"Arquivo salvo em: {os.path.join(current_dir, 'consolidated_report.txt')}")







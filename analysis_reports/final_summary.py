#!/usr/bin/env python3
"""
Script para gerar resumo final com estatísticas e recomendações.
"""

import os
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


class FinalSummaryGenerator:
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
        self.fixed_issues = set()
    
    def load_all_issues(self) -> List[Issue]:
        """Carrega todas as issues dos arquivos de resultados."""
        all_issues = []
        
        # Carrega issues do flake8
        all_issues.extend(self._load_flake8_issues())
        
        # Carrega issues do pylint
        all_issues.extend(self._load_pylint_issues())
        
        # Carrega issues do mypy
        all_issues.extend(self._load_mypy_issues())
        
        # Carrega issues do bandit
        all_issues.extend(self._load_bandit_issues())
        
        return all_issues
    
    def _load_flake8_issues(self) -> List[Issue]:
        """Carrega as issues do flake8."""
        issues = []
        file_path = self.reports_dir / "flake8_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: resync/api\auth.py:20:1: F401 'os' imported but unused
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
    
    def _load_pylint_issues(self) -> List[Issue]:
        """Carrega as issues do pylint."""
        issues = []
        file_path = self.reports_dir / "pylint_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: resync\api\admin.py:17:0: E0401: Unable to import 'resync.config.settings' (import-error)
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
    
    def _load_mypy_issues(self) -> List[Issue]:
        """Carrega as issues do mypy."""
        issues = []
        file_path = self.reports_dir / "mypy_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: resync\utils\exceptions.py:1131: error: Unexpected keyword argument "error_code" for "__init__" of "CacheError"
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
    
    def _load_bandit_issues(self) -> List[Issue]:
        """Carrega as issues do bandit."""
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
    
    def generate_final_summary(self, output_file: str = None) -> str:
        """Gera um relatório final com estatísticas e recomendações."""
        if not output_file:
            output_file = self.reports_dir / "final_summary_report.txt"
        
        # Carrega todas as issues
        all_issues = self.load_all_issues()
        
        # Estatísticas gerais
        total_issues = len(all_issues)
        
        # Agrupa por severidade
        by_severity = {}
        for issue in all_issues:
            if issue.severity not in by_severity:
                by_severity[issue.severity] = []
            by_severity[issue.severity].append(issue)
        
        # Agrupa por ferramenta
        by_tool = {}
        for issue in all_issues:
            if issue.tool not in by_tool:
                by_tool[issue.tool] = []
            by_tool[issue.tool].append(issue)
        
        # Agrupa por categoria
        by_category = {}
        for issue in all_issues:
            if issue.category not in by_category:
                by_category[issue.category] = []
            by_category[issue.category].append(issue)
        
        # Top 10 problemas mais comuns
        top_issues = {}
        for issue in all_issues:
            key = f"{issue.tool}:{issue.code}"
            if key not in top_issues:
                top_issues[key] = 0
            top_issues[key] += 1
        
        # Ordena os problemas mais comuns
        sorted_top_issues = sorted(top_issues.items(), key=lambda x: x[1], reverse=True)
        
        # Gera o relatório
        report_lines = []
        report_lines.append("# RELATÓRIO FINAL DE ANÁLISE DE CÓDIGO")
        report_lines.append("")
        
        # Estatísticas gerais
        report_lines.append("## ESTATÍSTICAS GERAIS")
        report_lines.append(f"- Total de Issues: {total_issues}")
        report_lines.append("")
        
        # Distribuição por severidade
        report_lines.append("## DISTRIBUIÇÃO POR SEVERIDADE")
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            count = len(by_severity.get(severity, []))
            if count > 0:
                report_lines.append(f"- {severity.value.upper()}: {count}")
        report_lines.append("")
        
        # Distribuição por ferramenta
        report_lines.append("## DISTRIBUIÇÃO POR FERRAMENTA")
        for tool, tool_issues in by_tool.items():
            report_lines.append(f"- {tool.upper()}: {len(tool_issues)}")
        report_lines.append("")
        
        # Top 10 problemas mais comuns
        report_lines.append("## TOP 10 PROBLEMAS MAIS COMUNS")
        for i, (key, count) in enumerate(sorted_top_issues[:10], 1):
            tool, code = key.split(":")
            report_lines.append(f"{i}. {tool.upper()} - {code}: {count} ocorrências")
        report_lines.append("")
        
        # Recomendações
        report_lines.append("## RECOMENDAÇÕES")
        report_lines.append("")
        
        # Recomendações por categoria
        report_lines.append("### Por Categoria")
        for category, category_issues in by_category.items():
            if len(category_issues) > 0:
                report_lines.append(f"#### {category.upper()}")
                
                # Analisa os problemas mais comuns nesta categoria
                category_top_issues = {}
                for issue in category_issues:
                    key = f"{issue.tool}:{issue.code}"
                    if key not in category_top_issues:
                        category_top_issues[key] = 0
                    category_top_issues[key] += 1
                
                # Ordena os problemas mais comuns nesta categoria
                sorted_category_top_issues = sorted(category_top_issues.items(), key=lambda x: x[1], reverse=True)
                
                # Gera recomendações específicas
                if category == "error":
                    report_lines.append("- Corrigir erros de sintaxe e importação que podem causar falhas em runtime.")
                elif category == "fatal":
                    report_lines.append("- Corrigir erros fatais que impedem a execução do código.")
                elif category == "warning":
                    report_lines.append("- Melhorar práticas de código e remover avisos desnecessários.")
                elif category == "refactor":
                    report_lines.append("- Refatorar código complexo ou duplicado para melhorar a maintainability.")
                elif category == "convention":
                    report_lines.append("- Seguir convenções de estilo e formatação para melhorar a legibilidade.")
                elif category == "type":
                    report_lines.append("- Adicionar anotações de tipo para melhorar a segurança e clareza do código.")
                elif category == "import":
                    report_lines.append("- Organizar importações e remover dependências desnecessárias.")
                elif category == "return":
                    report_lines.append("- Garantir que todas as funções tenham tipos de retorno explícitos.")
                elif category == "annotation":
                    report_lines.append("- Adicionar anotações de tipo detalhadas para parâmetros e variáveis.")
                elif category == "general":
                    report_lines.append("- Melhorar a estrutura geral do código e seguir boas práticas.")
                elif category == "security":
                    report_lines.append("- Implementar práticas de segurança robustas e corrigir vulnerabilidades.")
                elif category == "crypto":
                    report_lines.append("- Usar algoritmos de hash seguros e evitar práticas criptográficas inseguras.")
                elif category == "hardcoded":
                    report_lines.append("- Remover informações sensíveis hardcoded e usar configurações seguras.")
                elif category == "weak":
                    report_lines.append("- Substituir implementações fracas por alternativas mais robustas.")
                elif category == "injection":
                    report_lines.append("- Validar e sanitizar todas as entradas de usuário para prevenir injeção de código.")
                elif category == "exec":
                    report_lines.append("- Evitar execução de código dinâmico e usar alternativas mais seguras.")
                elif category == "debug":
                    report_lines.append("- Remover código de debug de produção e usar logging apropriado.")
        
        # Recomendações gerais
        report_lines.append("")
        report_lines.append("### Gerais")
        report_lines.append("- Configurar integração contínua das ferramentas de análise no pipeline de CI/CD.")
        report_lines.append("- Estabelecer limites de qualidade de código (ex: complexidade ciclomática, cobertura de testes).")
        report_lines.append("- Implementar code review automatizado para detectar problemas antes de chegarem à produção.")
        report_lines.append("- Documentar padrões de codificação e boas práticas para a equipe.")
        report_lines.append("- Realizar treinamento regular sobre boas práticas de desenvolvimento e segurança.")
        
        # Escreve o relatório
        report_content = "\n".join(report_lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return report_content


if __name__ == "__main__":
    import os
    # Usa o caminho absoluto do diretório atual
    current_dir = os.path.dirname(os.path.abspath(__file__))
    generator = FinalSummaryGenerator(current_dir)
    
    # Gera o relatório final
    report = generator.generate_final_summary()
    
    print(f"Relatório final gerado com {len(generator.load_all_issues())} issues.")
    print(f"Relatório salvo em: {os.path.join(current_dir, 'final_summary_report.txt')}")














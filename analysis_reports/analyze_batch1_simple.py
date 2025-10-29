#!/usr/bin/env python3
"""
Script simplificado para analisar detalhadamente os primeiros 20 erros mais críticos.
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


class SimpleBatchAnalyzer:
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
    
    def load_flake8_issues(self) -> List[Issue]:
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
    
    def load_pylint_issues(self) -> List[Issue]:
        """Carrega as issues do pylint."""
        issues = []
        file_path = self.reports_dir / "pylint_results.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Formato: resync\api\admin.py:17:0: E0401: Unable to import 'resync_new.config.settings' (import-error)
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
    
    def load_mypy_issues(self) -> List[Issue]:
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
    
    def load_bandit_issues(self) -> List[Issue]:
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
    
    def get_top_issues(self, all_issues: List[Issue], limit: int = 20) -> List[Issue]:
        """Obtém as issues mais críticas."""
        # Ordena por severidade (mais crítica primeiro)
        sorted_issues = sorted(all_issues, key=lambda x: (
            -self.severity_weights[x.severity],
            x.file,
            x.line
        ))
        
        return sorted_issues[:limit]
    
    def get_code_context(self, file_path: str, line_num: int, context_lines: int = 5) -> List[str]:
        """Obtém o contexto do código ao redor da linha com erro."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            start = max(0, line_num - context_lines - 1)
            end = min(len(lines), line_num + context_lines)
            
            context = []
            for i in range(start, end):
                marker = ">>> " if i == line_num - 1 else "    "
                context.append(f"{marker}{i+1:4d}: {lines[i].rstrip()}")
            
            return context
        except Exception as e:
            return [f"Erro ao ler o arquivo: {str(e)}"]
    
    def analyze_issue(self, issue: Issue) -> Dict[str, Any]:
        """Analisa uma issue em detalhes."""
        # Obtém o contexto do código
        file_path = os.path.join(os.path.dirname(self.reports_dir), issue.file)
        context = self.get_code_context(file_path, issue.line)
        
        # Análise da causa raiz
        root_cause = self._determine_root_cause(issue)
        
        # Proposta de correção
        correction = self._propose_correction(issue)
        
        # Impacto da correção
        impact = self._determine_impact(issue)
        
        # Verificação de falso positivo
        false_positive = self._check_false_positive(issue, context)
        
        return {
            "issue": issue,
            "context": context,
            "root_cause": root_cause,
            "correction": correction,
            "impact": impact,
            "false_positive": false_positive
        }
    
    def _determine_root_cause(self, issue: Issue) -> str:
        """Determina a causa raiz do problema."""
        if issue.tool == "flake8" and issue.code == "F401":
            return "Módulo importado mas não utilizado no código."
        elif issue.tool == "flake8" and issue.code == "F841":
            return "Variável local atribuída mas nunca utilizada."
        elif issue.tool == "pylint" and issue.code.startswith("E"):
            return "Erro de sintaxe ou semântica no código."
        elif issue.tool == "pylint" and issue.code.startswith("W"):
            return "Aviso sobre práticas de código que podem ser melhoradas."
        elif issue.tool == "mypy" and "type" in issue.message.lower():
            return "Incompatibilidade de tipos ou anotação de tipos ausente."
        elif issue.tool == "bandit":
            return "Vulnerabilidade de segurança ou prática insegura."
        elif issue.tool == "radon":
            return "Alta complexidade ciclomática que dificulta manutenção."
        else:
            return "Problema de qualidade de código detectado pela ferramenta."
    
    def _propose_correction(self, issue: Issue) -> str:
        """Propõe uma correção para a issue."""
        if issue.tool == "flake8" and issue.code == "F401":
            return f"Remover a importação não utilizada ou adicionar uma referência ao módulo importado."
        elif issue.tool == "flake8" and issue.code == "F841":
            return f"Remover a atribuição da variável não utilizada ou utilizar a variável em algum lugar."
        elif issue.tool == "pylint" and issue.code == "W1203":
            return "Usar formatação lazy em logging: logger.info('Mensagem %s', variavel) em vez de logger.info(f'Mensagem {variavel}')"
        elif issue.tool == "pylint" and issue.code == "W0613":
            return "Remover o parâmetro não utilizado ou adicionar um underscore ao nome: _parametro"
        elif issue.tool == "pylint" and issue.code == "E0401":
            return "Corrigir o caminho de importação ou verificar se o módulo existe."
        elif issue.tool == "mypy" and "return type" in issue.message.lower():
            return "Adicionar anotação de tipo de retorno: -> None ou -> TipoRetorno"
        elif issue.tool == "bandit" and issue.code == "B324":
            return "Usar um algoritmo de hash mais seguro como SHA-256 em vez de MD5."
        elif issue.tool == "bandit" and issue.code == "B311":
            return "Usar secrets.randbelow() em vez de random.randint() para fins criptográficos."
        else:
            return "Revisar o código de acordo com as recomendações da ferramenta."
    
    def _determine_impact(self, issue: Issue) -> str:
        """Determina o impacto da correção."""
        if issue.tool == "flake8" and issue.code == "F401":
            return "Melhora a clareza do código e remove dependências desnecessárias."
        elif issue.tool == "flake8" and issue.code == "F841":
            return "Remove código morto e melhora a legibilidade."
        elif issue.tool == "pylint" and issue.code == "W1203":
            return "Melhora a performance do logging em produção e evita formatação desnecessária."
        elif issue.tool == "pylint" and issue.code == "W0613":
            return "Melhora a clareza da interface da função."
        elif issue.tool == "pylint" and issue.code == "E0401":
            return "Corrige erros de importação que podem causar falhas em runtime."
        elif issue.tool == "mypy" and "type" in issue.message.lower():
            return "Melhora a segurança de tipos e facilita a detecção de erros."
        elif issue.tool == "bandit":
            return "Melhora a segurança do código e previne vulnerabilidades."
        elif issue.tool == "radon":
            return "Melhora a maintainability e facilita testes e debugging."
        else:
            return "Melhora a qualidade geral do código."
    
    def _check_false_positive(self, issue: Issue, context: List[str]) -> bool:
        """Verifica se a issue pode ser um falso positivo."""
        # Verifica se é uma importação usada em decorators ou annotations
        if issue.tool == "flake8" and issue.code == "F401":
            for line in context:
                if "@" in line and issue.message.split("'")[1] in line:
                    return True
                if ":" in line and "typing" in line and issue.message.split("'")[1] in line:
                    return True
        
        # Verifica se é uma variável usada em string formatting
        if issue.tool == "flake8" and issue.code == "F841":
            for line in context:
                if f"%{issue.message.split('\'')[1]}" in line or f"{issue.message.split('\'')[1]}:" in line:
                    return True
        
        return False
    
    def generate_detailed_report(self, issues: List[Issue], output_file: str = None) -> str:
        """Gera um relatório detalhado das issues analisadas."""
        if not output_file:
            output_file = self.reports_dir / "batch1_detailed_analysis.txt"
        
        report_lines = []
        report_lines.append("# ANÁLISE DETALHADA - LOTE 1 (PRIMEIROS 20 ERROS)")
        report_lines.append("")
        
        for i, issue in enumerate(issues, 1):
            analysis = self.analyze_issue(issue)
            
            report_lines.append(f"## {i}. {analysis['issue'].tool.upper()} - {analysis['issue'].code}")
            report_lines.append("")
            
            # Informações básicas
            report_lines.append("### Informações Básicas")
            report_lines.append(f"- **Arquivo:** {analysis['issue'].file}:{analysis['issue'].line}")
            report_lines.append(f"- **Severidade:** {analysis['issue'].severity.value.upper()}")
            report_lines.append(f"- **Categoria:** {analysis['issue'].category}")
            report_lines.append(f"- **Mensagem:** {analysis['issue'].message}")
            report_lines.append("")
            
            # Contexto do código
            report_lines.append("### Contexto do Código")
            report_lines.append("```python")
            for context_line in analysis['context']:
                report_lines.append(context_line)
            report_lines.append("```")
            report_lines.append("")
            
            # Análise da causa raiz
            report_lines.append("### Análise da Causa Raiz")
            report_lines.append(analysis['root_cause'])
            report_lines.append("")
            
            # Proposta de correção
            report_lines.append("### Proposta de Correção")
            report_lines.append(analysis['correction'])
            report_lines.append("")
            
            # Impacto da correção
            report_lines.append("### Impacto da Correção")
            report_lines.append(analysis['impact'])
            report_lines.append("")
            
            # Verificação de falso positivo
            if analysis['false_positive']:
                report_lines.append("### Possível Falso Positivo")
                report_lines.append("Esta issue pode ser um falso positivo. Verificar o contexto antes de aplicar a correção.")
                report_lines.append("")
            
            report_lines.append("---")
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
    analyzer = SimpleBatchAnalyzer(current_dir)
    
    # Carrega as issues de cada ferramenta
    all_issues = []
    all_issues.extend(analyzer.load_flake8_issues())
    all_issues.extend(analyzer.load_pylint_issues())
    all_issues.extend(analyzer.load_mypy_issues())
    all_issues.extend(analyzer.load_bandit_issues())
    
    # Obtém as 20 issues mais críticas
    top_issues = analyzer.get_top_issues(all_issues, 20)
    
    # Gera o relatório detalhado
    report = analyzer.generate_detailed_report(top_issues)
    
    print(f"Análise detalhada concluída para {len(top_issues)} issues.")
    print(f"Relatório salvo em: {os.path.join(current_dir, 'batch1_detailed_analysis.txt')}")



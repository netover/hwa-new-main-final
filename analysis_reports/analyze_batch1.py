#!/usr/bin/env python3
"""
Script para analisar detalhadamente os primeiros 20 erros mais críticos.
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


class BatchAnalyzer:
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
    
    def load_consolidated_issues(self) -> List[Issue]:
        """Carrega as issues consolidadas do relatório."""
        issues = []
        file_path = self.reports_dir / "consolidated_report.txt"
        
        if not file_path.exists():
            print(f"Arquivo {file_path} não encontrado.")
            return issues
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extrai as 20 issues mais críticas
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Procura por uma nova issue
            if line.startswith("### "):
                # Formato: ### 1. FLAKE8 - F401
                match = re.match(r'### (\d+)\. ([A-Z]+) - ([A-Z0-9]+)', line.strip())
                if match:
                    num, tool, code = match.groups()
                    current_issue = {"num": int(num), "tool": tool.lower(), "code": code}
                    
                    # Procura pelas informações da issue nas linhas seguintes
                    j = i + 1
                    while j < len(lines) and not lines[j].startswith("### "):
                        if lines[j].startswith("**Arquivo:**"):
                            # Formato: **Arquivo:** resync/api\auth.py:20
                            file_info = lines[j].split("**Arquivo:**")[1].strip()
                            file_parts = file_info.split(':')
                            current_issue["file"] = file_parts[0]
                            current_issue["line"] = int(file_parts[1])
                        
                        elif lines[j].startswith("**Severidade:**"):
                            # Formato: **Severidade:** CRITICAL
                            severity_str = lines[j].split("**Severidade:**")[1].strip()
                            current_issue["severity"] = Severity(severity_str.lower())
                        
                        elif lines[j].startswith("**Categoria:**"):
                            # Formato: **Categoria:** fatal
                            current_issue["category"] = lines[j].split("**Categoria:**")[1].strip()
                        
                        elif lines[j].startswith("**Mensagem:**"):
                            # Formato: **Mensagem:** 'os' imported but unused
                            current_issue["message"] = lines[j].split("**Mensagem:**")[1].strip()
                            
                            # Adiciona a issue completa à lista
                            if all(key in current_issue for key in ["num", "tool", "code", "file", "line", "severity", "category", "message"]):
                                issues.append(Issue(
                                    tool=current_issue["tool"],
                                    file=current_issue["file"],
                                    line=current_issue["line"],
                                    column=0,
                                    code=current_issue["code"],
                                    message=current_issue["message"],
                                    severity=current_issue["severity"],
                                    category=current_issue["category"]
                                ))
                                
                                # Para após as 20 issues
                                if len(issues) >= 20:
                                    return issues
                                break
                        
                        j += 1
                    
                    i = j - 1  # Ajusta o índice para continuar da onde parou
            
            i += 1
        
        return issues
    
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
                if f"%{issue.message.split("'")[1]}" in line or f"{issue.message.split("'")[1]}:" in line:
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
    analyzer = BatchAnalyzer(current_dir)
    
    # Carrega as issues consolidadas
    issues = analyzer.load_consolidated_issues()
    
    # Gera o relatório detalhado
    report = analyzer.generate_detailed_report(issues)
    
    print(f"Análise detalhada concluída para {len(issues)} issues.")
    print(f"Relatório salvo em: {os.path.join(current_dir, 'batch1_detailed_analysis.txt')}")

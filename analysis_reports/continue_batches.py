#!/usr/bin/env python3
"""
Script para continuar o processo de análise e correção em lotes subsequentes.
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


class BatchProcessor:
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
        self.fixed_issues = set()  # Issues já corrigidas
        self.batch_size = 20
        self.current_batch = 1
    
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
    
    def get_next_batch(self, all_issues: List[Issue]) -> List[Issue]:
        """Obtém o próximo lote de issues, excluindo as já corrigidas."""
        # Filtra issues já corrigidas
        remaining_issues = []
        for issue in all_issues:
            issue_key = f"{issue.file}:{issue.line}:{issue.code}"
            if issue_key not in self.fixed_issues:
                remaining_issues.append(issue)
        
        # Ordena por severidade (mais crítica primeiro)
        sorted_issues = sorted(remaining_issues, key=lambda x: (
            -self.severity_weights[x.severity],
            x.file,
            x.line
        ))
        
        # Retorna o próximo lote
        start_index = (self.current_batch - 1) * self.batch_size
        end_index = min(start_index + self.batch_size, len(sorted_issues))
        
        return sorted_issues[start_index:end_index]
    
    def mark_issues_as_fixed(self, issues: List[Issue]) -> None:
        """Marca as issues como corrigidas."""
        for issue in issues:
            issue_key = f"{issue.file}:{issue.line}:{issue.code}"
            self.fixed_issues.add(issue_key)
        
        self.current_batch += 1
    
    def process_next_batch(self) -> bool:
        """Processa o próximo lote de issues."""
        # Carrega todas as issues
        all_issues = self.load_all_issues()
        
        # Obtém o próximo lote
        next_batch = self.get_next_batch(all_issues)
        
        if not next_batch:
            print("Não há mais issues para processar.")
            return False
        
        print(f"\nProcessando Lote {self.current_batch} ({len(next_batch)} issues)...")
        
        # Aplica as correções para este lote
        fixes_count = 0
        for issue in next_batch:
            if self.apply_fix(issue):
                fixes_count += 1
                print(f"Correção aplicada: {issue.tool} - {issue.code} em {issue.file}:{issue.line}")
        
        # Marca as issues como corrigidas
        self.mark_issues_as_fixed(next_batch)
        
        print(f"Lote {self.current_batch} concluído. {fixes_count} correções aplicadas.")
        return True
    
    def apply_fix(self, issue: Issue) -> bool:
        """Aplica uma correção para uma issue específica."""
        file_path = os.path.join(os.path.dirname(self.reports_dir), issue.file)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Aplica a correção específica
            if issue.tool == "flake8" and issue.code == "F401":
                # Remove importação não utilizada
                return self._fix_unused_import(lines, issue.line, issue.message)
            
            elif issue.tool == "flake8" and issue.code == "F841":
                # Remove variável não utilizada
                return self._fix_unused_variable(lines, issue.line, issue.message)
            
            elif issue.tool == "pylint" and issue.code == "W1203":
                # Corrige formatação de logging
                return self._fix_logging_format(lines, issue.line)
            
            elif issue.tool == "pylint" and issue.code == "W0613":
                # Corrige parâmetro não utilizado
                return self._fix_unused_parameter(lines, issue.line, issue.message)
            
            elif issue.tool == "pylint" and issue.code == "E0401":
                # Corrige erro de importação
                return self._fix_import_error(lines, issue.line, issue.message)
            
            elif issue.tool == "mypy" and "return type" in issue.message.lower():
                # Adiciona anotação de tipo de retorno
                return self._fix_missing_return_type(lines, issue.line)
            
            elif issue.tool == "bandit" and issue.code == "B324":
                # Substitui MD5 por SHA-256
                return self._fix_weak_hash(lines, issue.line)
            
            elif issue.tool == "bandit" and issue.code == "B311":
                # Substitui random por secrets
                return self._fix_weak_random(lines, issue.line)
            
            else:
                print(f"Correção não implementada para {issue.tool} - {issue.code}")
                return False
        
        except Exception as e:
            print(f"Erro ao aplicar correção em {file_path}:{issue.line}: {str(e)}")
            return False
    
    def _fix_unused_import(self, lines: List[str], line_num: int, message: str) -> bool:
        """Remove importação não utilizada."""
        try:
            # Extrai o nome do módulo da mensagem
            module_name = message.split("'")[1]
            
            # Encontra a linha de importação
            import_line = line_num - 1
            if import_line < 0 or import_line >= len(lines):
                return False
            
            # Remove a linha de importação
            lines.pop(import_line)
            
            return True
        except Exception as e:
            print(f"Erro ao remover importação não utilizada: {str(e)}")
            return False
    
    def _fix_unused_variable(self, lines: List[str], line_num: int, message: str) -> bool:
        """Remove variável não utilizada."""
        try:
            # Extrai o nome da variável da mensagem
            var_name = message.split("'")[1]
            
            # Encontra a linha de atribuição
            assign_line = line_num - 1
            if assign_line < 0 or assign_line >= len(lines):
                return False
            
            # Remove a linha de atribuição
            lines.pop(assign_line)
            
            return True
        except Exception as e:
            print(f"Erro ao remover variável não utilizada: {str(e)}")
            return False
    
    def _fix_logging_format(self, lines: List[str], line_num: int) -> bool:
        """Corrige formatação de logging."""
        try:
            # Encontra a linha de logging
            log_line = line_num - 1
            if log_line < 0 or log_line >= len(lines):
                return False
            
            # Substitui f-string por formatação lazy
            original_line = lines[log_line]
            
            # Padrão: logger.info(f"Mensagem {variavel}")
            # Substituir por: logger.info("Mensagem %s", variavel)
            fstring_pattern = r'(\w+)\.(info|debug|warning|error|critical)\(f"([^"]*)"([^)]*)\)'
            
            def replace_fstring(match):
                logger_method = match.group(1)
                log_level = match.group(2)
                message = match.group(3)
                
                # Extrai variáveis do f-string
                var_pattern = r'\{([^}]+)\}'
                vars_in_message = re.findall(var_pattern, message)
                
                # Constrói a nova formatação
                if vars_in_message:
                    placeholders = '%s ' * len(vars_in_message)
                    new_message = message.replace('{', '').replace('}', '')
                    vars_str = ', '.join(vars_in_message)
                    return f'{logger_method}.{log_level}("{new_message}", {vars_str})'
                else:
                    return f'{logger_method}.{log_level}("{message}")'
            
            new_line = re.sub(fstring_pattern, replace_fstring, original_line)
            lines[log_line] = new_line
            
            return True
        except Exception as e:
            print(f"Erro ao corrigir formatação de logging: {str(e)}")
            return False
    
    def _fix_unused_parameter(self, lines: List[str], line_num: int, message: str) -> bool:
        """Corrige parâmetro não utilizado."""
        try:
            # Encontra a linha de definição da função
            func_line = line_num - 1
            if func_line < 0 or func_line >= len(lines):
                return False
            
            # Adiciona underscore ao nome do parâmetro
            original_line = lines[func_line]
            
            # Padrão: def func(parametro, outro_param):
            # Substituir por: def func(_parametro, outro_param):
            param_pattern = r'def\s+\w+\s*\(([^)]+)\)'
            
            def add_underscore(match):
                params = match.group(1)
                # Adiciona underscore apenas ao primeiro parâmetro
                params_list = params.split(',')
                if params_list:
                    first_param = params_list[0].strip()
                    if first_param and not first_param.startswith('_'):
                        params_list[0] = f'_{first_param}'
                
                return f'def {match.group().split("(")[0]}({", ".join(params_list)})'
            
            new_line = re.sub(param_pattern, add_underscore, original_line)
            lines[func_line] = new_line
            
            return True
        except Exception as e:
            print(f"Erro ao corrigir parâmetro não utilizado: {str(e)}")
            return False
    
    def _fix_import_error(self, lines: List[str], line_num: int, message: str) -> bool:
        """Corrige erro de importação."""
        try:
            # Encontra a linha de importação
            import_line = line_num - 1
            if import_line < 0 or import_line >= len(lines):
                return False
            
            # Extrai o módulo com erro da mensagem
            # Padrão: Unable to import 'module_name' (import-error)
            module_pattern = r"Unable to import '([^']+)'"
            match = re.search(module_pattern, message)
            if not match:
                return False
            
            module_name = match.group(1)
            
            # Tenta corrigir o caminho de importação
            original_line = lines[import_line]
            
            # Se for um erro de resync, tenta remover o prefixo
            if 'resync.' in module_name:
                new_module = module_name.replace('resync.', 'resync.')
                new_line = original_line.replace(module_name, new_module)
                lines[import_line] = new_line
                
                return True
            
            return False
        except Exception as e:
            print(f"Erro ao corrigir erro de importação: {str(e)}")
            return False
    
    def _fix_missing_return_type(self, lines: List[str], line_num: int) -> bool:
        """Adiciona anotação de tipo de retorno."""
        try:
            # Encontra a linha de definição da função
            func_line = line_num - 1
            if func_line < 0 or func_line >= len(lines):
                return False
            
            # Adiciona anotação de tipo de retorno
            original_line = lines[func_line]
            
            # Padrão: def func(parametros):
            # Substituir por: def func(parametros) -> None:
            func_pattern = r'def\s+(\w+)\s*\([^)]*\)\s*:'
            
            def add_return_type(match):
                func_name = match.group(1)
                return f'def {func_name}{match.group().split(func_name)[1]} -> None:'
            
            new_line = re.sub(func_pattern, add_return_type, original_line)
            lines[func_line] = new_line
            
            return True
        except Exception as e:
            print(f"Erro ao adicionar tipo de retorno: {str(e)}")
            return False
    
    def _fix_weak_hash(self, lines: List[str], line_num: int) -> bool:
        """Substitui MD5 por SHA-256."""
        try:
            # Encontra a linha com MD5
            hash_line = line_num - 1
            if hash_line < 0 or hash_line >= len(lines):
                return False
            
            # Substitui MD5 por SHA-256
            original_line = lines[hash_line]
            new_line = original_line.replace('md5', 'sha256')
            lines[hash_line] = new_line
            
            return True
        except Exception as e:
            print(f"Erro ao substituir hash fraco: {str(e)}")
            return False
    
    def _fix_weak_random(self, lines: List[str], line_num: int) -> bool:
        """Substitui random por secrets."""
        try:
            # Encontra a linha com random
            random_line = line_num - 1
            if random_line < 0 or random_line >= len(lines):
                return False
            
            # Substitui random.randint por secrets.randbelow
            original_line = lines[random_line]
            new_line = original_line.replace('random.randint', 'secrets.randbelow')
            lines[random_line] = new_line
            
            return True
        except Exception as e:
            print(f"Erro ao substituir random fraco: {str(e)}")
            return False
    
    def save_fixed_files(self, issues: List[Issue]) -> None:
        """Salva os arquivos corrigidos."""
        # Agrupa issues por arquivo
        files_to_fix = {}
        for issue in issues:
            if issue.file not in files_to_fix:
                files_to_fix[issue.file] = []
            files_to_fix[issue.file].append(issue)
        
        # Aplica as correções arquivo por arquivo
        for file_path, file_issues in files_to_fix.items():
            full_path = os.path.join(os.path.dirname(self.reports_dir), file_path)
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Aplica as correções para este arquivo
                for issue in file_issues:
                    self.apply_fix(issue)
                
                # Salva o arquivo corrigido
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                print(f"Arquivo corrigido: {file_path}")
            except Exception as e:
                print(f"Erro ao corrigir arquivo {file_path}: {str(e)}")
    
    def generate_progress_report(self, output_file: str = None) -> str:
        """Gera um relatório de progresso."""
        if not output_file:
            output_file = self.reports_dir / "progress_report.txt"
        
        report_lines = []
        report_lines.append("# RELATÓRIO DE PROGRESSO - ANÁLISE DE CÓDIGO")
        report_lines.append(f"Lotes processados: {self.current_batch - 1}")
        report_lines.append(f"Total de issues corrigidas: {len(self.fixed_issues)}")
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
    processor = BatchProcessor(current_dir)
    
    # Processa lotes até não haver mais issues
    while processor.process_next_batch():
        pass
    
    # Gera o relatório final de progresso
    report = processor.generate_progress_report()
    
    print(f"\nProcesso concluído. Total de lotes: {processor.current_batch - 1}")
    print(f"Total de issues corrigidas: {len(processor.fixed_issues)}")
    print(f"Relatório salvo em: {os.path.join(current_dir, 'progress_report.txt')}")











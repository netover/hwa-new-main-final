#!/usr/bin/env python3
"""
Resync Project Analyzer - Ferramenta para análise e otimização do projeto resync/

Este script identifica arquivos Python não utilizados, duplicados e com funcionalidades sobrepostas
no diretório resync/, fornecendo recomendações para limpeza e otimização do projeto.

Uso:
    python resync_analyzer.py [--options]

Opções:
    --all, -a           Executa todas as análises (padrão)
    --unused, -u        Analisa apenas arquivos não utilizados
    --duplicates, -d    Analisa apenas arquivos duplicados
    --legacy, -l        Analisa apenas arquivos legados e backups
    --cleanup, -c       Gera script de limpeza para arquivos seguros de remover
    --report, -r        Gera relatório detalhado em formato JSON
    --verbose, -v       Modo verboso com mais detalhes
    --help, -h          Mostra esta mensagem de ajuda
"""

import argparse
import ast
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

class ResyncAnalyzer:
    """Classe principal para análise do projeto resync/"""
    
    def __init__(self, base_dir: str = "resync", verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.verbose = verbose
        self.python_files = []
        self.dependency_graph = {}
        self.all_modules = set()
        self.imported_modules = set()
        self.unused_files = []
        self.duplicate_files = []
        self.legacy_files = []
        self.backup_files = []
        
        if not self.base_dir.exists():
            print(f"Erro: Diretório {base_dir} não encontrado!")
            sys.exit(1)
    
    def log(self, message: str) -> None:
        """Função de log condicional ao modo verboso"""
        if self.verbose:
            print(f"[LOG] {message}")
    
    def get_all_python_files(self) -> List[Path]:
        """Obtém todos os arquivos Python no diretório recursivamente"""
        self.log("Procurando por arquivos Python...")
        python_files = []
        
        for root, _, files in os.walk(self.base_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    python_files.append(file_path)
                    self.log(f"Encontrado: {file_path}")
        
        self.log(f"Total de {len(python_files)} arquivos Python encontrados")
        return python_files
    
    def extract_imports(self, file_path: Path) -> List[str]:
        """Extrai todos os imports resync de um arquivo Python"""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse do AST
            tree = ast.parse(content)
            
            # Extrai imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('resync.'):
                            imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith('resync.'):
                        imports.append(node.module)
        except Exception as e:
            if self.verbose:
                print(f"Erro ao analisar {file_path}: {e}")
        
        return imports
    
    def build_dependency_graph(self, python_files: List[Path]) -> Dict[Path, List[str]]:
        """Constrói um grafo de dependências mostrando quais arquivos importam quais módulos"""
        self.log("Construindo grafo de dependências...")
        dependency_graph = {}
        
        for file_path in python_files:
            imports = self.extract_imports(file_path)
            dependency_graph[file_path] = imports
            self.log(f"Analisando {file_path}: {len(imports)} imports encontrados")
        
        return dependency_graph
    
    def get_module_from_path(self, file_path: Path) -> str:
        """Converte um caminho de arquivo para um caminho de módulo"""
        relative_path = file_path.relative_to(self.base_dir)
        module_parts = list(relative_path.parts)
        
        # Remove extensão .py
        if module_parts[-1].endswith('.py'):
            module_parts[-1] = module_parts[-1][:-3]
        
        # Remove __init__ do caminho do módulo
        if module_parts[-1] == '__init__':
            module_parts = module_parts[:-1]
        
        return '.'.join(module_parts)
    
    def find_unused_files(self, python_files: List[Path], dependency_graph: Dict[Path, List[str]]) -> List[Tuple[Path, str, bool, bool]]:
        """Encontra arquivos que não são importados por nenhum outro arquivo"""
        self.log("Procurando por arquivos não utilizados...")
        
        # Cria um conjunto de todos os caminhos de módulo
        all_modules = set()
        for file_path in python_files:
            module_path = self.get_module_from_path(file_path)
            all_modules.add(module_path)
        
        # Cria um conjunto de módulos importados
        imported_modules = set()
        for imports in dependency_graph.values():
            for imp in imports:
                # Extrai o módulo base (resync.x.y.z -> resync.x.y)
                parts = imp.split('.')
                if len(parts) >= 2:
                    base_module = '.'.join(parts[:2])
                    imported_modules.add(base_module)
                    
                    # Adiciona também o caminho completo do módulo
                    imported_modules.add(imp)
        
        # Encontra arquivos que não são importados
        unused_files = []
        entry_points = {'main.py', 'app.py', '__main__.py', 'run.py', 'server.py'}
        
        for file_path in python_files:
            module_path = self.get_module_from_path(file_path)
            
            # Verifica se este módulo é importado
            is_imported = False
            for imported in imported_modules:
                if module_path.startswith(imported):
                    is_imported = True
                    break
            
            # Verifica se é um ponto de entrada
            is_entry_point = file_path.name in entry_points
            
            # Verifica se é um arquivo de teste
            is_test = 'test' in file_path.name.lower() or 'tests' in str(file_path).lower()
            
            # Verifica se é um arquivo de backup
            is_backup = file_path.suffix == '.bak'
            
            # Verifica se está em um diretório legacy
            is_legacy = 'legacy' in str(file_path).lower()
            
            if not is_imported and not is_entry_point and not is_test:
                unused_files.append((file_path, module_path, is_backup, is_legacy))
                self.log(f"Arquivo não utilizado: {file_path}")
        
        return unused_files
    
    def find_duplicate_files(self, python_files: List[Path]) -> List[Tuple[List[Path], str]]:
        """Encontra arquivos com nomes similares que podem ser duplicados"""
        self.log("Procurando por arquivos duplicados...")
        
        # Agrupa arquivos pelo nome base (sem caminho e extensão)
        name_groups = {}
        
        for file_path in python_files:
            base_name = file_path.stem
            if base_name not in name_groups:
                name_groups[base_name] = []
            name_groups[base_name].append(file_path)
        
        # Encontra grupos com mais de um arquivo
        duplicates = []
        for base_name, files in name_groups.items():
            if len(files) > 1:
                # Verifica se estão em diretórios diferentes
                dirs = set(str(f.parent.relative_to(self.base_dir)) for f in files)
                if len(dirs) > 1:
                    duplicates.append((files, base_name))
                    self.log(f"Arquivos duplicados encontrados para '{base_name}': {len(files)} arquivos")
        
        return duplicates
    
    def find_legacy_and_backup_files(self, python_files: List[Path]) -> Tuple[List[Path], List[Path]]:
        """Encontra arquivos legados e de backup"""
        self.log("Procurando por arquivos legados e de backup...")
        
        legacy_files = []
        backup_files = []
        
        for file_path in python_files:
            # Verifica se é um arquivo de backup
            if file_path.suffix == '.bak':
                backup_files.append(file_path)
                self.log(f"Arquivo de backup encontrado: {file_path}")
            
            # Verifica se está em um diretório legacy
            if 'legacy' in str(file_path).lower():
                legacy_files.append(file_path)
                self.log(f"Arquivo legado encontrado: {file_path}")
        
        return legacy_files, backup_files
    
    def analyze_functionality_overlap(self, duplicate_groups: List[Tuple[List[Path], str]]) -> Dict[str, List[Path]]:
        """Analisa sobreposição de funcionalidades em arquivos duplicados"""
        self.log("Analisando sobreposição de funcionalidades...")
        
        overlap_analysis = {}
        
        # Padrões para identificar tipos de arquivos
        patterns = {
            'health_service': r'health.*service',
            'auth': r'auth',
            'cache': r'cache',
            'config': r'config',
            'models': r'models?',
            'utils': r'utils?',
            'monitoring': r'monitor',
            'middleware': r'middleware',
            'exceptions': r'exception',
            'security': r'security'
        }
        
        for files, base_name in duplicate_groups:
            # Verifica se o nome base corresponde a algum padrão
            for pattern_name, pattern in patterns.items():
                if re.search(pattern, base_name, re.IGNORECASE):
                    if pattern_name not in overlap_analysis:
                        overlap_analysis[pattern_name] = []
                    overlap_analysis[pattern_name].extend(files)
                    break
        
        return overlap_analysis
    
    def generate_cleanup_script(self, safely_removable: List[Path], output_file: str = "cleanup_resync.py") -> None:
        """Gera um script de limpeza para arquivos seguros de remover"""
        self.log(f"Gerando script de limpeza: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('#!/usr/bin/env python3\n')
            f.write('"""\n')
            f.write('Script de limpeza para arquivos não utilizados no projeto resync/\n')
            f.write(f'Gerado em {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
            f.write('\n')
            f.write('AVISO: Execute este script apenas após revisar os arquivos listados abaixo!\n')
            f.write('"""\n\n')
            f.write('import os\n')
            f.write('import shutil\n')
            f.write('from pathlib import Path\n\n')
            f.write('def backup_file(file_path: Path) -> None:\n')
            f.write('    """Cria um backup do arquivo antes de remover"""\n')
            f.write('    backup_path = Path(f"{file_path}.backup")\n')
            f.write('    shutil.copy2(file_path, backup_path)\n')
            f.write('    print(f"Backup criado: {backup_path}")\n\n')
            f.write('def remove_file(file_path: Path) -> None:\n')
            f.write('    """Remove o arquivo após criar backup"""\n')
            f.write('    if file_path.exists():\n')
            f.write('        backup_file(file_path)\n')
            f.write('        file_path.unlink()\n')
            f.write('        print(f"Arquivo removido: {file_path}")\n')
            f.write('    else:\n')
            f.write('        print(f"Arquivo não encontrado: {file_path}")\n\n')
            f.write('def main():\n')
            f.write('    """Função principal"""\n')
            f.write('    print("Iniciando limpeza de arquivos não utilizados...\\n")\n\n')
            
            for file_path in safely_removable:
                f.write(f'    # {file_path}\n')
                f.write(f'    remove_file(Path("{file_path}"))\n\n')
            
            f.write('    print("\\nLimpeza concluída!")\n\n')
            f.write('if __name__ == "__main__":\n')
            f.write('    main()\n')
        
        print(f"Script de limpeza gerado: {output_file}")
    
    def generate_report(self, output_file: str = "resync_analysis_report.json") -> None:
        """Gera um relatório detalhado em formato JSON"""
        self.log(f"Gerando relatório detalhado: {output_file}")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_python_files": len(self.python_files),
                "unused_files": len(self.unused_files),
                "duplicate_groups": len(self.duplicate_files),
                "legacy_files": len(self.legacy_files),
                "backup_files": len(self.backup_files)
            },
            "unused_files": [
                {
                    "path": str(file_path),
                    "module": module_path,
                    "is_backup": is_backup,
                    "is_legacy": is_legacy
                }
                for file_path, module_path, is_backup, is_legacy in self.unused_files
            ],
            "duplicate_files": [
                {
                    "base_name": base_name,
                    "files": [str(f) for f in files]
                }
                for files, base_name in self.duplicate_files
            ],
            "legacy_files": [str(f) for f in self.legacy_files],
            "backup_files": [str(f) for f in self.backup_files],
            "functionality_overlap": {
                category: [str(f) for f in files] 
                for category, files in self.analyze_functionality_overlap(self.duplicate_files).items()
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Relatório gerado: {output_file}")
    
    def run_analysis(self, analysis_type: str = "all") -> None:
        """Executa a análise especificada"""
        print(f"Iniciando análise do projeto resync/...")
        print(f"Tipo de análise: {analysis_type}")
        print("-" * 50)
        
        # Obtém todos os arquivos Python
        self.python_files = self.get_all_python_files()
        
        # Constrói o grafo de dependências
        self.dependency_graph = self.build_dependency_graph(self.python_files)
        
        # Executa as análises solicitadas
        if analysis_type in ["all", "unused"]:
            self.unused_files = self.find_unused_files(self.python_files, self.dependency_graph)
            self.print_unused_files()
        
        if analysis_type in ["all", "duplicates"]:
            self.duplicate_files = self.find_duplicate_files(self.python_files)
            self.print_duplicate_files()
        
        if analysis_type in ["all", "legacy"]:
            self.legacy_files, self.backup_files = self.find_legacy_and_backup_files(self.python_files)
            self.print_legacy_files()
        
        # Gera resumo
        self.print_summary()
    
    def print_unused_files(self) -> None:
        """Imprime os arquivos não utilizados"""
        print("\n=== ARQUIVOS NÃO UTILIZADOS ===")
        print("Arquivos que não são importados por nenhum outro arquivo:")
        
        safely_removable = []
        for file_path, module_path, is_backup, is_legacy in self.unused_files:
            flags = []
            if is_backup:
                flags.append("BACKUP")
                safely_removable.append(file_path)
            if is_legacy:
                flags.append("LEGACY")
                safely_removable.append(file_path)
            
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"  {file_path} ({module_path}){flag_str}")
        
        if safely_removable:
            print(f"\nArquivos que podem ser removidos com segurança: {len(safely_removable)}")
            for file_path in safely_removable:
                print(f"  {file_path}")
    
    def print_duplicate_files(self) -> None:
        """Imprime os arquivos duplicados"""
        print("\n=== ARQUIVOS DUPLICADOS ===")
        print("Arquivos com nomes similares em diretórios diferentes:")
        
        for files, base_name in self.duplicate_files:
            print(f"\n{base_name}:")
            for file_path in files:
                print(f"  - {file_path}")
    
    def print_legacy_files(self) -> None:
        """Imprime os arquivos legados e de backup"""
        print("\n=== ARQUIVOS LEGADOS E DE BACKUP ===")
        
        if self.legacy_files:
            print(f"\nArquivos legados ({len(self.legacy_files)}):")
            for file_path in self.legacy_files:
                print(f"  - {file_path}")
        
        if self.backup_files:
            print(f"\nArquivos de backup ({len(self.backup_files)}):")
            for file_path in self.backup_files:
                print(f"  - {file_path}")
    
    def print_summary(self) -> None:
        """Imprime um resumo da análise"""
        print("\n=== RESUMO ===")
        print(f"Total de arquivos Python: {len(self.python_files)}")
        print(f"Arquivos não utilizados: {len(self.unused_files)}")
        print(f"Grupos de arquivos duplicados: {len(self.duplicate_files)}")
        print(f"Arquivos legados: {len(self.legacy_files)}")
        print(f"Arquivos de backup: {len(self.backup_files)}")
        
        # Análise de sobreposição de funcionalidades
        overlap_analysis = self.analyze_functionality_overlap(self.duplicate_files)
        if overlap_analysis:
            print("\n=== SOBREPOSIÇÃO DE FUNCIONALIDADES ===")
            for category, files in overlap_analysis.items():
                print(f"\n{category}:")
                for file_path in files:
                    print(f"  - {file_path}")


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description="Ferramenta para análise e otimização do projeto resync/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python resync_analyzer.py                    # Executa todas as análises
  python resync_analyzer.py --unused           # Analisa apenas arquivos não utilizados
  python resync_analyzer.py --duplicates       # Analisa apenas arquivos duplicados
  python resync_analyzer.py --legacy           # Analisa apenas arquivos legados
  python resync_analyzer.py --cleanup          # Gera script de limpeza
  python resync_analyzer.py --report           # Gera relatório em JSON
  python resync_analyzer.py -v --all           # Modo verboso com todas as análises
        """
    )
    
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        default=True,
        help="Executa todas as análises (padrão)"
    )
    
    parser.add_argument(
        "--unused", "-u",
        action="store_true",
        help="Analisa apenas arquivos não utilizados"
    )
    
    parser.add_argument(
        "--duplicates", "-d",
        action="store_true",
        help="Analisa apenas arquivos duplicados"
    )
    
    parser.add_argument(
        "--legacy", "-l",
        action="store_true",
        help="Analisa apenas arquivos legados e backups"
    )
    
    parser.add_argument(
        "--cleanup", "-c",
        action="store_true",
        help="Gera script de limpeza para arquivos seguros de remover"
    )
    
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="Gera relatório detalhado em formato JSON"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Modo verboso com mais detalhes"
    )
    
    args = parser.parse_args()
    
    # Determina o tipo de análise
    if args.unused:
        analysis_type = "unused"
    elif args.duplicates:
        analysis_type = "duplicates"
    elif args.legacy:
        analysis_type = "legacy"
    else:
        analysis_type = "all"
    
    # Cria o analisador e executa a análise
    analyzer = ResyncAnalyzer(verbose=args.verbose)
    analyzer.run_analysis(analysis_type)
    
    # Gera script de limpeza se solicitado
    if args.cleanup:
        safely_removable = []
        for file_path, module_path, is_backup, is_legacy in analyzer.unused_files:
            if is_backup or is_legacy:
                safely_removable.append(file_path)
        
        if safely_removable:
            analyzer.generate_cleanup_script(safely_removable)
        else:
            print("Nenhum arquivo seguro para remover encontrado.")
    
    # Gera relatório se solicitado
    if args.report:
        analyzer.generate_report()


if __name__ == "__main__":
    main()

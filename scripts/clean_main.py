"""Script para limpar duplicações no main.py"""

from __future__ import annotations


def clean_main_py() -> None:
    with open("resync/main.py", "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"Total de linhas ANTES: {len(lines)}")

    # Encontrar todas as linhas com "from resync.api.admin import admin_router"
    admin_import_lines = []
    mount_router_lines = []

    for i, line in enumerate(lines, 1):
        if "from resync.api.admin import admin_router" in line:
            admin_import_lines.append(i)
        if "# --- Mount Routers and Static Files ---" in line:
            mount_router_lines.append(i)

    print(f"\nImports duplicados do admin_router nas linhas: {admin_import_lines}")
    print(f"Seções de Mount Routers nas linhas: {mount_router_lines}")

    # A primeira ocorrência deve estar no topo (linhas 1-25)
    # Vamos manter apenas a primeira seção de imports e mount routers

    # Identificar seções a remover
    sections_to_remove = []

    # Seção duplicada entre 240-270 (aproximadamente)
    if len(admin_import_lines) > 1:
        for i in range(1, len(admin_import_lines)):
            start = admin_import_lines[i] - 1  # 0-indexed
            # Encontrar o fim da seção (próximo decorador ou função)
            end = start + 50  # Assumir que a seção tem no máximo 50 linhas
            for j in range(start, min(end, len(lines))):
                if (
                    lines[j].startswith("@")
                    or lines[j].startswith("def ")
                    or lines[j].startswith("class ")
                ):
                    end = j
                    break
            sections_to_remove.append((start, end))

    print(f"\nSeções a remover: {sections_to_remove}")

    # Criar novo arquivo sem as seções duplicadas
    clean_lines = []
    skip_until = -1

    for i, line in enumerate(lines):
        if i < skip_until:
            continue

        # Verificar se estamos em uma seção a remover
        in_remove_section = False
        for start, end in sections_to_remove:
            if start <= i < end:
                in_remove_section = True
                skip_until = end
                print(f"Pulando linhas {i+1} até {end+1}")
                break

        if not in_remove_section:
            clean_lines.append(line)

    print(f"\nTotal de linhas DEPOIS: {len(clean_lines)}")

    # Salvar arquivo limpo
    with open("resync/main_clean.py", "w", encoding="utf-8") as f:
        f.writelines(clean_lines)

    print("\nArquivo limpo salvo em: resync/main_clean.py")
    print("Revise o arquivo e depois substitua: mv resync/main_clean.py resync/main.py")


if __name__ == "__main__":
    clean_main_py()

"""
Script to fix duplicate function definitions in websocket_pool_manager.py
"""

from __future__ import annotations


def fix_websocket_pool_manager() -> None:
    file_path = "resync/core/websocket_pool_manager.py"

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find and remove duplicate lines
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a duplicate function definition
        if i < len(lines) - 1:
            next_line = lines[i + 1]
            # If current and next line are identical async def lines, skip current
            if (
                line.strip().startswith("async def _remove_connection")
                and next_line.strip().startswith("async def _remove_connection")
                and line == next_line
            ):
                print(f"Skipping duplicate line {i + 1}: {line.strip()}")
                i += 1
                continue

        fixed_lines.append(line)
        i += 1

    # Write back the fixed content
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(fixed_lines)

    print(f"Fixed {file_path}")
    print(f"Original lines: {len(lines)}")
    print(f"Fixed lines: {len(fixed_lines)}")
    print(f"Removed {len(lines) - len(fixed_lines)} duplicate lines")


if __name__ == "__main__":
    fix_websocket_pool_manager()

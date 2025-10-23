"""
Script to fix websocket_pool_manager.py by removing duplicate function blocks
"""

from __future__ import annotations


def fix_websocket_file() -> None:
    file_path = "resync/core/websocket_pool_manager.py"

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by the problematic function definition
    parts = content.split("    async def disconnect(self, client_id: str) -> None:")

    if len(parts) > 2:
        print(f"Found {len(parts) - 1} occurrences of 'async def disconnect'")
        # Keep only the first occurrence (parts[0]) and the first function (parts[1])
        # Skip all other duplicates
        fixed_content = (
            parts[0]
            + "    async def disconnect(self, client_id: str) -> None:"
            + parts[1]
        )

        # Find where the first function block ends (look for the next method definition at same indentation)
        # We need to find the end of _remove_connection method
        lines = parts[1].split("\n")
        func_end = 0
        in_function = False
        indent_count = 0

        for i, line in enumerate(lines):
            if "_remove_connection" in line and "async def" in line:
                in_function = True
                indent_count = len(line) - len(line.lstrip())
            elif (
                in_function
                and line.strip()
                and not line.startswith(" " * (indent_count + 1))
            ):
                # Found a line with same or less indentation, function ended
                func_end = i
                break

        if func_end > 0:
            # Reconstruct with first function only
            first_block_lines = lines[:func_end]
            remaining_content = "\n".join(lines[func_end:])

            # Find where the rest of the class continues (skip duplicates)
            # Look for next method that's not _remove_connection or disconnect
            remaining_lines = remaining_content.split("\n")
            next_method_idx = 0
            for i, line in enumerate(remaining_lines):
                if line.strip().startswith("async def") or line.strip().startswith(
                    "def"
                ):
                    if "_remove_connection" not in line and "disconnect" not in line:
                        next_method_idx = i
                        break

            if next_method_idx > 0:
                fixed_content = (
                    parts[0]
                    + "    async def disconnect(self, client_id: str) -> None:"
                    + "\n".join(first_block_lines)
                    + "\n"
                    + "\n".join(remaining_lines[next_method_idx:])
                )
            else:
                fixed_content = (
                    parts[0]
                    + "    async def disconnect(self, client_id: str) -> None:"
                    + "\n".join(first_block_lines)
                )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(fixed_content)

        print(f"Fixed! Removed {len(parts) - 2} duplicate blocks")
    else:
        print("No duplicates found or file structure unexpected")


if __name__ == "__main__":
    fix_websocket_file()

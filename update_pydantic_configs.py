#!/usr/bin/env python3
"""
Script to automate updating Pydantic Config classes to model_config.

This script finds all Pydantic Config classes and replaces them with model_config.
"""

import os
import re
from pathlib import Path


def update_config_classes(file_path):
    """Update Config classes in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file already has ConfigDict import
        has_config_dict = 'from pydantic import ConfigDict' in content or 'from pydantic import.*ConfigDict' in content
        
        # Pattern to find class Config blocks
        config_pattern = r'class Config:\s*\n(.*?)(?=^\S|\Z)'
        
        matches = re.finditer(config_pattern, content, re.MULTILINE | re.DOTALL)
        
        if not matches:
            return False
        
        new_content = content
        
        for match in matches:
            config_content = match.group(1)
            
            # Remove class Config and replace with model_config
            config_lines = config_content.strip().split('\n')
            config_dict_content = '\n'.join([line for line in config_lines if line.strip()])
            
            # Convert to model_config format
            model_config_line = f'model_config = ConfigDict(\n{config_dict_content}\n)'
            
            # Replace the entire class Config block
            old_block = f'class Config:\n{config_content}'
            new_block = model_config_line
            
            new_content = new_content.replace(old_block, new_block)
        
        # Add ConfigDict import if needed
        if not has_config_dict and 'ConfigDict' in new_content:
            new_content = new_content.replace(
                'from pydantic import BaseModel',
                'from pydantic import BaseModel, ConfigDict'
            )
        
        # Write updated content back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to update all Python files in the resync directory."""
    resync_dir = Path('resync')
    
    updated_files = []
    
    for root, dirs, files in os.walk(resync_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                if update_config_classes(file_path):
                    updated_files.append(file_path)
    
    print(f"Updated {len(updated_files)} files:")
    for file in updated_files:
        print(f"  - {file}")


if __name__ == "__main__":
    main()

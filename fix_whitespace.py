#!/usr/bin/env python3
"""Auto-fix trailing whitespace in Python files"""
import os
import re

def fix_whitespace(filepath):
    """Remove trailing whitespace from file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove trailing whitespace from each line
        fixed_content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
        
        if content != fixed_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    fixed_count = 0
    for root, dirs, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_whitespace(filepath):
                    fixed_count += 1
                    print(f"Fixed: {filepath}")
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == '__main__':
    main()

import os
import re
from pathlib import Path

def main():
    repo_root = Path(r"c:\WIP\REVIT_MCP")
    docs_dir = repo_root / "docs" / "BIM_MCP"
    
    # 1. Update counts in HTML files
    html_files = list(docs_dir.rglob("*.html"))
    print(f"Found {len(html_files)} HTML files in {docs_dir}")
    
    patterns = [
        (re.compile(r'(Domain Knowledge.{0,40}（)44(\s*個)'), r'\g<1>45\g<2>'),
        (re.compile(r'44(\+?\s*個?\s*Domain\b)'), r'45\g<1>'),
        (re.compile(r'44(\s*個\s*SOP)'), r'45\g<1>'),
        (re.compile(r'44(\s*個\s*domain/\*\.md)'), r'45\g<1>'),
        (re.compile(r'44(\s*個\s*<code>domain)'), r'45\g<1>'),
    ]
    
    replaced_count = 0
    for hf in html_files:
        content = hf.read_text(encoding="utf-8")
        original = content
        for pat, repl in patterns:
            content = pat.sub(repl, content)
        
        if content != original:
            hf.write_text(content, encoding="utf-8")
            print(f"Updated: {hf.relative_to(repo_root)}")
            replaced_count += 1
            
    print(f"Successfully updated {replaced_count} files.")

if __name__ == "__main__":
    main()

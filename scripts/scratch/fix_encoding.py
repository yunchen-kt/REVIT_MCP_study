import os
from pathlib import Path

def main():
    repo_root = Path(r"c:\WIP\REVIT_MCP")
    script_path = repo_root / "scripts" / "install-addon.ps1"
    
    # Read the file
    content = script_path.read_text(encoding="utf-8")
    
    # Write it back as UTF-8 with BOM (utf-8-sig)
    script_path.write_text(content, encoding="utf-8-sig")
    print("Successfully converted scripts/install-addon.ps1 to UTF-8 with BOM.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Save files from a developer-subagent reply framed as =====FILE: path===== ... =====END FILE=====.
Usage: extract_files.py REPLY.txt   (writes relative to the current directory; refuses .env* and paths outside it)"""
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
pat = re.compile(r"^=====FILE: (.+?)=====\n(.*?)\n=====END FILE=====$", re.S | re.M)
n = 0
for m in pat.finditer(text):
    rel = Path(m.group(1).strip())
    if rel.is_absolute() or ".." in rel.parts or rel.name.startswith(".env"):
        sys.exit(f"refusing {rel}")
    rel.parent.mkdir(parents=True, exist_ok=True)
    rel.write_text(m.group(2) + "\n", encoding="utf-8")
    print("wrote", rel, len(m.group(2).splitlines()), "lines"); n += 1
print(n, "files")

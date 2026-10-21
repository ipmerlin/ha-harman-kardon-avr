"""Check the exact staged public payload for credential-shaped material."""

import re
import subprocess

patterns = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r'''(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*["'][^"'\n]{8,}["']'''),
]
paths = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"]).split(b"\0")
count = 0
for encoded in paths:
    if not encoded:
        continue
    path = encoded.decode("utf-8")
    if path.endswith(".png"):
        continue
    content = subprocess.check_output(["git", "show", f":{path}"]).decode("utf-8")
    for pattern in patterns:
        if pattern.search(content):
            raise SystemExit(f"Potential credential found in {path}; publication stopped")
    count += 1
print(f"No credential patterns found in {count} staged text files")

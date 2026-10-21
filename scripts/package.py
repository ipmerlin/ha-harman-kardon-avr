"""Build a clean manual-install archive, without dependencies or user data."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/hk_avr"
version = json.loads((COMPONENT / "manifest.json").read_text())["version"]
output = ROOT / "dist" / f"hk_avr-{version}.zip"
output.parent.mkdir(exist_ok=True)
files = [p for p in COMPONENT.rglob("*")
         if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
files += [ROOT / filename for filename in (
    "README.md", "LICENSE", "CHANGELOG.md", "VALIDATION.md", "hacs.json")]
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, path.relative_to(ROOT).as_posix())
digest = hashlib.sha256(output.read_bytes()).hexdigest()
output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
print(f"{output.name}: {len(files)} files, SHA256 {digest}")

"""Check the delivered ZIP against source, its checksum and its file allowlist."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/hk_avr"
manifest = json.loads((COMPONENT / "manifest.json").read_text())
path = ROOT / "dist" / f"hk_avr-{manifest['version']}.zip"
expected = path.with_suffix(".zip.sha256").read_text().split()[0]
assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    names = archive.namelist()
    assert len(names) == len(set(names))
    for name in names:
        assert ".." not in Path(name).parts
        assert name.startswith("custom_components/hk_avr/") or name in (
            "README.md", "LICENSE", "CHANGELOG.md", "VALIDATION.md", "NETWORK_PROTOCOL.md", "hacs.json")
        assert "__pycache__" not in name and not name.endswith(".pyc")
        assert archive.read(name) == (ROOT / name).read_bytes()
    assert "custom_components/hk_avr/brand/icon.png" in names
    assert "custom_components/hk_avr/translations/ru.json" in names
print(f"ZIP verified: {len(names)} source-matched files, SHA256 verified")

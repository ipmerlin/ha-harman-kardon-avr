"""Run offline checks without Home Assistant or third-party dependencies."""

import ast
import json
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
COMPONENT = ROOT / "custom_components/hk_avr"

for path in (list(COMPONENT.rglob("*.py")) + list((ROOT / "scripts").glob("*.py"))
             + list((ROOT / "tests").rglob("*.py"))):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
for path in COMPONENT.rglob("*.json"):
    json.loads(path.read_text(encoding="utf-8"))
manifest = json.loads((COMPONENT / "manifest.json").read_text())
assert manifest["domain"] == COMPONENT.name
assert manifest["config_flow"] is True
assert manifest["requirements"] == []
for field in ("name", "version", "codeowners", "documentation", "issue_tracker"):
    assert manifest[field], field
hacs = json.loads((ROOT / "hacs.json").read_text())
assert hacs["homeassistant"] == "2025.12.0"
assert len(list((ROOT / "custom_components").iterdir())) == 1
for lang in ("en", "ru"):
    translated = json.loads((COMPONENT / f"translations/{lang}.json").read_text(encoding="utf-8"))
    assert set(translated["config"]["step"]) == {
        "user", "reconfigure", "offline", "learn_confirm", "learn_progress", "learn_done", "learn_failed",
    }
    assert "Broadlink" not in json.dumps(translated["config"])
    assert "learn_power_on" in translated["config"]["progress"]
    constants = runpy.run_path(str(COMPONENT / "const.py"))
    assert set(translated["entity"]["button"]) == set(constants["NETWORK_BUTTONS"])
assert json.loads((COMPONENT / "strings.json").read_text()) == json.loads(
    (COMPONENT / "translations/en.json").read_text())
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests/offline"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)

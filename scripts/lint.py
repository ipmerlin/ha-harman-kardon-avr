"""Run a project-local Ruff install without modifying global Python."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".test-deps"))
sys.argv = ["ruff", "check", "custom_components", "tests", "scripts", *sys.argv[1:]]
runpy.run_module("ruff", run_name="__main__")

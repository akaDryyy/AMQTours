from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


PACKAGE_IMPORTS = {
    "trueskill": "trueskill",
    "beautifulsoup4": "bs4",
    "mpmath": "mpmath",
    "python-dateutil": "dateutil",
    "lxml": "lxml",
    "curl-cffi": "curl_cffi",
    "ortools": "ortools",
    "pandas": "pandas",
    "gspread": "gspread",
    "numpy": "numpy",
}


def ensure_dependencies(requirements_path: str | Path) -> None:
    requirements_path = Path(requirements_path)
    if not requirements_path.exists():
        return
    missing = [
        package
        for package, module in PACKAGE_IMPORTS.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_path)])

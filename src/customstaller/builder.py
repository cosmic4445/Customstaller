"""``customstaller build``: turn a project into a single standalone installer program."""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

from .config import CustomstallerError, Project

RUNNER = '''\
import sys
from pathlib import Path

from customstaller.runtime import run_installer

# When frozen, the project files are unpacked next to the program under "project".
base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
mode = "none" if "--no-open" in sys.argv else "auto"
raise SystemExit(run_installer(base / "project", mode=mode))
'''

# Things a project may ship, copied into "project/" inside the bundle.
_DATA = ["customstaller.toml", "tabs", "payload", "assets",
         "LICENSE", "LICENSE.txt", "LICENSE.md", "license.txt"]


def _imports_in(path: Path) -> set[str]:
    """Top-level module names a tab file imports, so PyInstaller bundles them."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def build(project: Project, *, onefile: bool = True, console: bool = False) -> Path:
    if importlib.util.find_spec("PyInstaller") is None:
        raise CustomstallerError(
            "Building needs PyInstaller. Install it with: pip install \"customstaller[build]\""
        )
    root = project.root
    work = root / "build" / "customstaller"
    work.mkdir(parents=True, exist_ok=True)
    runner = work / "run_installer.py"
    runner.write_text(RUNNER, encoding="utf-8")

    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", project.app["name"]).strip("-") or "installer"
    exe_name = f"{safe}-setup"

    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile" if onefile else "--onedir",
        "--name", exe_name,
        "--distpath", str(root / "dist"),
        "--workpath", str(work / "work"),
        "--specpath", str(work),
    ]
    if not console:
        cmd.append("--windowed")
    for item in _DATA:
        src = root / item
        if src.exists():
            dest = "project" if src.is_file() else f"project/{item}"
            cmd += ["--add-data", f"{src}{os.pathsep}{dest}"]
    icon = str(project.app.get("icon") or "").strip()
    if icon and (root / icon).is_file():
        cmd += ["--icon", str(root / icon)]

    hidden: set[str] = set(project.data["build"].get("hidden_imports", []))
    for slug in project.order:
        hidden |= _imports_in(root / "tabs" / f"{slug}.py")
    hidden.discard("customstaller")
    hidden.discard("__future__")
    for name in sorted(hidden):
        cmd += ["--hidden-import", name]
    if importlib.util.find_spec("webview") is not None:
        cmd += ["--hidden-import", "webview"]

    cmd.append(str(runner))
    result = subprocess.run(cmd, cwd=root)
    if result.returncode != 0:
        raise CustomstallerError("PyInstaller failed. The output above says why.")

    suffix = ".exe" if os.name == "nt" else ""
    out = root / "dist" / (exe_name + suffix)
    if not out.exists() and not onefile:
        out = root / "dist" / exe_name
    return out

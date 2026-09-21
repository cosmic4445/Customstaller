"""Project config: reading, writing and defaults for ``customstaller.toml``."""

from __future__ import annotations

import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

CONFIG_NAME = "customstaller.toml"


class CustomstallerError(Exception):
    """A problem the user can fix. The CLI prints these without a traceback."""


DEFAULTS: dict[str, Any] = {
    "app": {
        "name": "My App",
        "version": "1.0.0",
        "publisher": "",
        "install_dir": "",  # empty = a sensible per-user folder
        "logo": "",  # file inside assets/, e.g. "logo.png"
        "icon": "",  # .ico used for the built executable, relative to the project
        "window_width": 960,
        "window_height": 640,
    },
    "style": {
        "theme": "ocean",
        "corners": "rounded",  # sharp | rounded | pill
        "accent": "",  # empty = use the theme's accent
        "layout": "sidebar",  # sidebar | top
        "animations": True,
        "font": "system",  # system | mono | serif | rounded
        "branding": True,  # small "Powered by Customstaller" in the rail
    },
    "tabs": {"order": []},
    "build": {"hidden_imports": []},
}


def deep_merge(base: dict, override: dict) -> dict:
    """Return ``base`` updated with ``override``, merging nested tables."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


# --------------------------------------------------------------------------- #
# Minimal TOML writer (the stdlib only reads TOML). Handles what our config
# uses: strings, bools, numbers, lists of scalars and nested tables.
# --------------------------------------------------------------------------- #

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _key(k: str) -> str:
    return k if _BARE_KEY.match(k) else json.dumps(k, ensure_ascii=False)


def _value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_value(i) for i in v) + "]"
    raise TypeError(f"Can't write {type(v).__name__} to TOML")


def dumps(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def emit(table: dict[str, Any], path: list[str]) -> None:
        scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
        subtables = {k: v for k, v in table.items() if isinstance(v, dict)}
        if path and (scalars or not subtables):
            lines.append("[" + ".".join(path) + "]")
        for k, v in scalars.items():
            lines.append(f"{_key(k)} = {_value(v)}")
        if scalars or (path and not subtables):
            lines.append("")
        for k, v in subtables.items():
            emit(v, path + [_key(k)])

    emit(data, [])
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Project
# --------------------------------------------------------------------------- #


@dataclass
class Project:
    root: Path
    data: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULTS))

    @property
    def config_path(self) -> Path:
        return self.root / CONFIG_NAME

    @property
    def tabs_dir(self) -> Path:
        return self.root / "tabs"

    @property
    def app(self) -> dict[str, Any]:
        return self.data["app"]

    @property
    def style(self) -> dict[str, Any]:
        return self.data["style"]

    @property
    def order(self) -> list[str]:
        return self.data["tabs"]["order"]

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(dumps(self.data), encoding="utf-8")

    @classmethod
    def load(cls, root: Path) -> "Project":
        path = Path(root) / CONFIG_NAME
        if not path.is_file():
            raise CustomstallerError(
                f"No {CONFIG_NAME} in {root}. Run `customstaller init` first."
            )
        try:
            with open(path, "rb") as fh:
                raw = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise CustomstallerError(f"{CONFIG_NAME} isn't valid TOML: {exc}") from exc
        return cls(root=Path(root), data=deep_merge(DEFAULTS, raw))


def find_project(start: Path | None = None) -> Project | None:
    """Walk up from ``start`` (default: cwd) looking for ``customstaller.toml``."""
    here = Path(start or Path.cwd()).resolve()
    for folder in [here, *here.parents]:
        if (folder / CONFIG_NAME).is_file():
            return Project.load(folder)
    return None


def require_project(start: Path | None = None) -> Project:
    project = find_project(start)
    if project is None:
        raise CustomstallerError(
            f"No {CONFIG_NAME} found here or in a parent folder. "
            "Run `customstaller init` in your project first."
        )
    return project

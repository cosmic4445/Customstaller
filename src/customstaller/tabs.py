"""Creating, ordering and loading the tabs of a project."""

from __future__ import annotations

import importlib.util
import keyword
import re
import sys
from pathlib import Path

from .config import CustomstallerError, Project
from .core import Tab
from .templates import PREMADE_SOURCES, render_custom

# The four premade tabs, in the order they normally appear.
PREMADE = ["home", "license", "console", "finish"]
LABELS = {"home": "Home", "license": "License", "console": "Console", "finish": "Finish"}


def slugify(name: str) -> str:
    """'My Cool Tab!' -> 'my_cool_tab'. Always a valid Python module name."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not slug:
        return ""
    if slug[0].isdigit():
        slug = "tab_" + slug
    if keyword.iskeyword(slug):
        slug += "_tab"
    return slug


def class_name(slug: str) -> str:
    return "".join(part.capitalize() for part in slug.split("_") if part) or "CustomTab"


def humanize(slug: str) -> str:
    return LABELS.get(slug) or slug.replace("_", " ").strip().title()


def tab_path(project: Project, slug: str) -> Path:
    return project.tabs_dir / f"{slug}.py"


def _write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def add_premade(project: Project, slug: str) -> Path:
    """Add Home/License/Console/Finish. An existing file is kept, never overwritten."""
    if slug not in PREMADE:
        raise CustomstallerError(f"'{slug}' isn't a premade tab. Choose from: {', '.join(PREMADE)}.")
    if slug in project.order:
        raise CustomstallerError(f"The {LABELS[slug]} tab is already in your installer.")
    path = tab_path(project, slug)
    if not path.exists():
        _write_new(path, PREMADE_SOURCES[slug])
    order = project.order
    if slug == "finish":
        order.append(slug)
    elif slug == "home":
        order.insert(0, slug)
    else:
        mine = PREMADE.index(slug)
        earlier = [i for i, s in enumerate(order) if s in PREMADE and PREMADE.index(s) < mine]
        order.insert(max(earlier) + 1 if earlier else 0, slug)
    project.save()
    return path


def create_tab(project: Project, name: str) -> tuple[str, Path]:
    """Make a new tab from the empty template and add it to the installer.

    It goes just before Console (pages that gather choices usually come before the
    install runs), or before Finish if there's no Console. Reorder from the menu.
    """
    title = name.strip()
    slug = slugify(title)
    if not slug:
        raise CustomstallerError("Give the tab a name that has at least one letter or number.")
    if slug in PREMADE:
        raise CustomstallerError(
            f"'{title}' is one of the premade tabs. Pick it from the menu, or choose another name."
        )
    if slug in project.order:
        raise CustomstallerError(f"There's already a tab called '{slug}'. Pick another name.")
    path = tab_path(project, slug)
    if path.exists():
        raise CustomstallerError(f"{path.relative_to(project.root)} already exists. Pick another name.")
    _write_new(path, render_custom(title, slug, class_name(slug)))
    order = project.order
    anchor = next((a for a in ("console", "finish") if a in order), None)
    order.insert(order.index(anchor), slug) if anchor else order.append(slug)
    project.save()
    return slug, path


def remove_tab(project: Project, slug: str) -> None:
    """Take a tab out of the installer. The file stays on disk."""
    if slug not in project.order:
        raise CustomstallerError(f"There's no tab called '{slug}' in the installer.")
    project.order.remove(slug)
    project.save()


def move_tab(project: Project, slug: str, delta: int) -> None:
    order = project.order
    if slug not in order:
        raise CustomstallerError(f"There's no tab called '{slug}' in the installer.")
    i = order.index(slug)
    j = max(0, min(len(order) - 1, i + delta))
    order.insert(j, order.pop(i))
    project.save()


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


class TabError(CustomstallerError):
    pass


def load_tab_class(path: Path) -> type[Tab]:
    """Import a tab file and return the Tab subclass it defines."""
    module_name = f"_customstaller_tab_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise TabError(f"Can't load {path.name}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        sys.modules.pop(module_name, None)
        raise TabError(f"tabs/{path.name} has an error: {type(exc).__name__}: {exc}") from exc
    found = [
        obj for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, Tab) and obj is not Tab
        and obj.__module__ == module_name
    ]
    if not found:
        raise TabError(f"tabs/{path.name} doesn't define a Tab. Add `class MyTab(Tab): ...`.")
    return found[0]


def load_tabs(project: Project) -> list[tuple[str, Tab]]:
    """Instances of every tab in the installer, in order."""
    tabs: list[tuple[str, Tab]] = []
    for slug in project.order:
        path = tab_path(project, slug)
        if not path.is_file():
            raise TabError(
                f"The installer lists '{slug}' but tabs/{slug}.py is missing. "
                f"Restore the file or run `customstaller tab remove {slug}`."
            )
        tabs.append((slug, load_tab_class(path)()))
    return tabs

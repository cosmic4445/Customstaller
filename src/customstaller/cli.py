"""The ``customstaller`` command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import __version__
from .config import CONFIG_NAME, CustomstallerError, Project, require_project
from .themes import CORNERS, THEMES, is_color, normalize_theme, swatch, theme_choices
from .tabs import (
    LABELS, PREMADE, add_premade, create_tab, humanize, move_tab, remove_tab, tab_path,
)

console = Console(highlight=False)
errors = Console(stderr=True, highlight=False)

CORNER_BLURBS = {
    "sharp": "square corners",
    "rounded": "softly rounded",
    "pill": "fully rounded buttons and fields",
}
LAYOUTS = {"sidebar": "steps down the left side", "top": "steps across the top"}


class Cancelled(Exception):
    """The user backed out of a prompt (Ctrl+C or Esc)."""


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _ask(question: Any) -> Any:
    answer = question.ask()
    if answer is None:
        raise Cancelled
    return answer


# --------------------------------------------------------------------------- #
# Style questions (used by `init` and `theme`)
# --------------------------------------------------------------------------- #


def _prompt_style(current: dict[str, Any]) -> dict[str, Any]:
    import questionary

    theme = _ask(questionary.select(
        "Theme",
        choices=[
            questionary.Choice(
                title=[(f"fg:{swatch(name)}", "●  "), ("", label), ("fg:#888888", f"  {blurb}")],
                value=name,
            )
            for name, label, blurb in theme_choices()
        ],
        default=normalize_theme(current.get("theme")),
    ))
    corners = _ask(questionary.select(
        "Corners",
        choices=[
            questionary.Choice(title=[("", name.capitalize()), ("fg:#888888", f"  {blurb}")], value=name)
            for name, blurb in CORNER_BLURBS.items()
        ],
        default=current.get("corners"),
    ))
    accent = _ask(questionary.text(
        "Accent color (a hex like #ff6600, or leave empty to use the theme's)",
        default=current.get("accent", ""),
        validate=lambda v: v.strip() == "" or is_color(v.strip()) or "Use a hex color such as #3d95ff",
    )).strip()
    layout = _ask(questionary.select(
        "Layout",
        choices=[
            questionary.Choice(title=[("", name.capitalize()), ("fg:#888888", f"  {blurb}")], value=name)
            for name, blurb in LAYOUTS.items()
        ],
        default=current.get("layout"),
    ))
    animations = _ask(questionary.confirm("Animations?", default=bool(current.get("animations", True))))
    return {"theme": theme, "corners": corners, "accent": accent, "layout": layout, "animations": animations}


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #

PAYLOAD_README = (
    "Put the files your app installs in this folder.\n"
    "Everything here is copied to the install location by the Console tab.\n"
)


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.dir or ".").resolve()
    if (root / CONFIG_NAME).exists() and not args.force:
        raise CustomstallerError(
            f"{CONFIG_NAME} already exists here. Use --force to start over "
            "(your tab files are kept), or run `customstaller theme` to change the look."
        )
    project = Project(root=root)
    project.order.clear()
    project.app["name"] = args.name or root.name.replace("-", " ").replace("_", " ").title() or "My App"
    project.app["version"] = args.app_version or project.app["version"]
    style = project.style
    for key in ("theme", "corners", "layout", "accent"):
        value = getattr(args, key)
        if value is not None:
            style[key] = value
    if args.no_animations:
        style["animations"] = False

    if _interactive() and not args.yes:
        import questionary

        console.print(f"[bold]Setting up Customstaller in[/] {escape(str(root))}\n")
        project.app["name"] = _ask(questionary.text("App name", default=project.app["name"])).strip() or project.app["name"]
        project.app["version"] = _ask(questionary.text("Version", default=project.app["version"])).strip() or project.app["version"]
        style.update(_prompt_style(style))

    root.mkdir(parents=True, exist_ok=True)
    for slug in PREMADE:
        add_premade(project, slug)
    for folder, readme in (("payload", PAYLOAD_README), ("assets", None)):
        (root / folder).mkdir(exist_ok=True)
        if readme and not (root / folder / "README.txt").exists():
            (root / folder / "README.txt").write_text(readme, encoding="utf-8")
    project.save()

    console.print(f"\n[green]✓[/] Created [bold]{CONFIG_NAME}[/] and {len(PREMADE)} tabs in tabs/")
    console.print(
        "\nNext:\n"
        "  [bold]customstaller run[/]     preview your installer\n"
        "  [bold]customstaller tab[/]     add or manage tabs\n"
        "  [bold]customstaller build[/]   make the standalone installer\n"
    )
    return 0


# --------------------------------------------------------------------------- #
# theme
# --------------------------------------------------------------------------- #


def cmd_theme(args: argparse.Namespace) -> int:
    project = require_project()
    style = project.style
    given = {k: getattr(args, k) for k in ("theme", "corners", "layout", "accent") if getattr(args, k) is not None}
    if args.no_animations:
        given["animations"] = False
    if given:
        style.update(given)
    elif _interactive():
        style.update(_prompt_style(style))
    else:
        raise CustomstallerError("Pass --theme, --corners, --layout or --accent (or run this in a terminal to be asked).")
    project.save()
    console.print(f"[green]✓[/] Saved. Theme: [bold]{THEMES[normalize_theme(style['theme'])]['label']}[/], corners: {style['corners']}, layout: {style['layout']}")
    return 0


# --------------------------------------------------------------------------- #
# tab
# --------------------------------------------------------------------------- #


def _print_tabs(project: Project) -> None:
    if not project.order:
        console.print("[dim]No tabs yet.[/]")
        return
    table = Table(box=None, pad_edge=False, header_style="dim")
    table.add_column("#", justify="right")
    table.add_column("Tab")
    table.add_column("File", style="dim")
    for i, slug in enumerate(project.order, 1):
        table.add_row(str(i), humanize(slug), str(tab_path(project, slug).relative_to(project.root)))
    console.print(table)


def _created_message(path: Path, project: Project) -> None:
    console.print(f"[green]✓[/] Created [bold]{escape(str(path.relative_to(project.root)))}[/]. Edit it to build the page.")


def _manage_menu(root: Path, slug: str) -> None:
    import questionary

    choice = _ask(questionary.select(
        f"{humanize(slug)}",
        choices=[
            questionary.Choice("Move earlier", "up"),
            questionary.Choice("Move later", "down"),
            questionary.Choice("Remove from installer (keeps the file)", "remove"),
            questionary.Choice("Back", "back"),
        ],
    ))
    project = Project.load(root)
    if choice == "up":
        move_tab(project, slug, -1)
    elif choice == "down":
        move_tab(project, slug, +1)
    elif choice == "remove":
        remove_tab(project, slug)
        console.print(f"[green]✓[/] Removed {humanize(slug)} from the installer.")


def _new_tab_menu(root: Path) -> None:
    """The "New" menu: name the tab, then Add it."""
    import questionary

    name = ""
    while True:
        choice = _ask(questionary.select(
            "New tab",
            choices=[
                questionary.Choice(
                    title=[("", "Name your tab"), ("fg:#888888", f"  {name or '(not set)'}")], value="name",
                ),
                questionary.Choice("Add", "add"),
                questionary.Choice("Back", "back"),
            ],
            default="add" if name else "name",
            qmark="◆",
        ))
        if choice == "back":
            return
        if choice == "name":
            name = _ask(questionary.text(
                "Name your tab", default=name,
                validate=lambda v: bool(v.strip()) or "Give the tab a name.",
            )).strip()
            continue
        if not name:
            errors.print("[red]Name your tab first.[/]")
            continue
        project = Project.load(root)
        try:
            _slug, path = create_tab(project, name)
        except CustomstallerError as exc:
            errors.print(f"[red]{escape(str(exc))}[/]")
            continue
        _created_message(path, project)
        return


def tab_menu(root: Path) -> None:
    """The interactive menu: pick a premade tab, manage one, or make a new one."""
    import questionary

    while True:
        project = Project.load(root)
        order = project.order
        console.print(
            "\n[dim]Installer order:[/] " + (" → ".join(humanize(s) for s in order) or "(empty)")
        )
        choices: list[Any] = []
        for slug in PREMADE:
            on = slug in order
            choices.append(questionary.Choice(
                title=[
                    ("fg:#3ddc84" if on else "fg:#888888", "✓ " if on else "+ "),
                    ("", LABELS[slug]),
                    ("fg:#888888", "  in your installer" if on else "  add"),
                ],
                value=("premade", slug),
            ))
        choices.append(questionary.Choice(title=[("bold", "+ New")], value=("new", None)))
        custom = [s for s in order if s not in PREMADE]
        if custom:
            choices.append(questionary.Separator("  your tabs"))
            for slug in custom:
                choices.append(questionary.Choice(
                    title=[("fg:#3ddc84", "✓ "), ("", humanize(slug))], value=("manage", slug),
                ))
        choices.append(questionary.Separator("  ────────────"))
        choices.append(questionary.Choice(title="Done", value=("done", None)))

        kind, slug = _ask(questionary.select("Tabs", choices=choices, qmark="◆"))
        try:
            if kind == "done":
                return
            if kind == "premade" and slug not in order:
                path = add_premade(project, slug)
                console.print(f"[green]✓[/] Added {LABELS[slug]}: [bold]{escape(str(path.relative_to(root)))}[/]")
            elif kind in ("premade", "manage"):
                _manage_menu(root, slug)
            elif kind == "new":
                _new_tab_menu(root)
        except CustomstallerError as exc:
            errors.print(f"[red]{escape(str(exc))}[/]")


def cmd_tab(args: argparse.Namespace) -> int:
    project = require_project()
    sub = args.tab_cmd
    if sub is None:
        if not _interactive():
            _print_tabs(project)
            console.print("\n[dim]Run this in a terminal for the menu, or use: tab new NAME | tab add NAME | tab remove NAME[/]")
            return 0
        tab_menu(project.root)
    elif sub == "list":
        _print_tabs(project)
    elif sub == "new":
        _slug, path = create_tab(project, " ".join(args.name))
        _created_message(path, project)
    elif sub == "add":
        path = add_premade(project, args.which)
        console.print(f"[green]✓[/] Added {LABELS[args.which]}: [bold]{escape(str(path.relative_to(project.root)))}[/]")
    elif sub == "remove":
        remove_tab(project, args.name)
        console.print(f"[green]✓[/] Removed {escape(args.name)} from the installer (its file is kept).")
    elif sub == "move":
        move_tab(project, args.name, -1 if args.direction == "up" else 1)
        console.print(f"[green]✓[/] Moved {escape(args.name)} {args.direction}.")
    return 0


# --------------------------------------------------------------------------- #
# run / build
# --------------------------------------------------------------------------- #


def cmd_run(args: argparse.Namespace) -> int:
    from .runtime import run_installer

    project = require_project()
    mode = "browser" if args.browser else "window" if args.window else "none" if args.no_open else "auto"
    return run_installer(project.root, mode=mode)


def cmd_build(args: argparse.Namespace) -> int:
    from .builder import build

    project = require_project()
    out = build(project, onefile=not args.onedir, console=args.console)
    console.print(f"\n[green]✓[/] Built [bold]{escape(str(out))}[/]")
    console.print("[dim]PyInstaller builds for the system it runs on. Build on Windows to get a Windows .exe.[/]")
    return 0


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="customstaller",
        description="Vibrant, themeable installers you customize one tab at a time.",
    )
    p.add_argument("--version", action="version", version=f"customstaller {__version__}")
    p.add_argument("--tabs", action="store_true", help="open the tab menu (same as `tab`)")
    p.add_argument("--options", action="store_true", help="open the Options menu (same as `options`)")
    sub = p.add_subparsers(dest="command", metavar="command")

    def style_flags(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--theme", type=normalize_theme, choices=list(THEMES))
        sp.add_argument("--corners", choices=list(CORNERS))
        sp.add_argument("--layout", choices=list(LAYOUTS))
        sp.add_argument("--accent", metavar="#HEX", help="override the theme's accent color")
        sp.add_argument("--no-animations", action="store_true")

    s = sub.add_parser("init", help="set up Customstaller in this folder")
    s.add_argument("--dir", help="folder to set up (default: current folder)")
    s.add_argument("--name", help="app name")
    s.add_argument("--app-version", metavar="VERSION", help="app version")
    s.add_argument("--yes", "-y", action="store_true", help="don't ask questions; use defaults and flags")
    s.add_argument("--force", action="store_true", help="replace an existing customstaller.toml")
    style_flags(s)
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("options", aliases=["theme"], help="change the theme, corners and other style options")
    style_flags(s)
    s.set_defaults(func=cmd_theme)

    s = sub.add_parser("tab", help="open the tab menu (add premade tabs, create new ones)")
    s.set_defaults(func=cmd_tab, tab_cmd=None)
    ts = s.add_subparsers(dest="tab_cmd", metavar="action")
    ts.add_parser("list", help="show the tabs in order")
    t = ts.add_parser("new", help="create a new tab from the empty template")
    t.add_argument("name", nargs="+")
    t = ts.add_parser("add", help="add a premade tab")
    t.add_argument("which", choices=PREMADE)
    t = ts.add_parser("remove", help="take a tab out of the installer (keeps its file)")
    t.add_argument("name")
    t = ts.add_parser("move", help="move a tab earlier or later")
    t.add_argument("name")
    t.add_argument("direction", choices=["up", "down"])

    s = sub.add_parser("run", help="preview the installer")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--browser", action="store_true", help="open in your browser")
    g.add_argument("--window", action="store_true", help="require a desktop window (needs pywebview)")
    g.add_argument("--no-open", action="store_true", help="just print the address")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("build", help="package the installer into one executable")
    s.add_argument("--onedir", action="store_true", help="a folder instead of a single file")
    s.add_argument("--console", action="store_true", help="keep a console window (for debugging)")
    s.set_defaults(func=cmd_build)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None and args.tabs:
        func, args.tab_cmd = cmd_tab, None
    elif func is None and args.options:
        func = cmd_theme
        args.theme = args.corners = args.layout = args.accent = None
        args.no_animations = False
    if func is None:
        parser.print_help()
        return 0
    try:
        return int(func(args) or 0)
    except CustomstallerError as exc:
        errors.print(f"[red]error:[/] {escape(str(exc))}")
        return 1
    except (Cancelled, KeyboardInterrupt):
        errors.print("[dim]Cancelled.[/]")
        return 130

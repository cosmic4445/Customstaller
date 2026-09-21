"""Themes are small sets of color tokens. The UI is styled entirely from them."""

from __future__ import annotations

import re
from typing import Any

# Token meanings:
#   bg          window background
#   surface     panels, inputs, the sidebar
#   surface_alt hover / selected states, code chips
#   text, muted body text and secondary text
#   accent      buttons, active step, links, focus rings
#   accent2     the far end of the progress bar
#   accent_text text drawn on top of `accent`
#   border, success, danger
#   console     background of the install log (defaults to a fitting shade per theme)
TOKEN_NAMES = [
    "bg", "surface", "surface_alt", "text", "muted",
    "accent", "accent2", "accent_text", "border", "success", "danger", "console",
]

# The log window sits a step away from the page background: deeper on dark themes,
# plain white on light ones. Custom themes default to their own `surface` color.
_CONSOLE = {
    "black": "#000000", "white": "#ffffff", "ocean": "#020e1b", "flames": "#0c0303",
    "forest": "#030d07", "sunset": "#12081b", "neon": "#040008", "midnight": "#05080f",
    "sakura": "#ffffff", "contrast": "#000000",
}

THEMES: dict[str, dict[str, Any]] = {
    "black": {
        "label": "Black",
        "blurb": "black and grey",
        "tokens": dict(
            bg="#000000", surface="#131313", surface_alt="#1f1f1f", text="#f2f2f2",
            muted="#9a9a9a", accent="#d6d6d6", accent2="#6e6e6e", accent_text="#000000",
            border="#2b2b2b", success="#5fd68a", danger="#ff6b6b",
        ),
    },
    "white": {
        "label": "White",
        "blurb": "white and grey",
        "tokens": dict(
            bg="#f1f1f1", surface="#ffffff", surface_alt="#e6e6e6", text="#161616",
            muted="#666666", accent="#3a3a3a", accent2="#a8a8a8", accent_text="#ffffff",
            border="#d4d4d4", success="#1a8f4a", danger="#c62828",
        ),
    },
    "ocean": {
        "label": "Ocean",
        "blurb": "blue and deep blue",
        "tokens": dict(
            bg="#04182c", surface="#0a2947", surface_alt="#103a63", text="#e8f2ff",
            muted="#8db0d8", accent="#3d95ff", accent2="#1746b8", accent_text="#03101f",
            border="#174a7c", success="#4be0a0", danger="#ff7a7a",
        ),
    },
    "flames": {
        "label": "Flames",
        "blurb": "red and dark red",
        "tokens": dict(
            bg="#190505", surface="#2c0c0c", surface_alt="#421414", text="#fff0ec",
            muted="#d99f95", accent="#f04a2a", accent2="#a11414", accent_text="#1a0402",
            border="#5c1c1c", success="#7be08a", danger="#ffb4a8",
        ),
    },
    "forest": {
        "label": "Forest",
        "blurb": "green and deep green",
        "tokens": dict(
            bg="#06150c", surface="#0c2416", surface_alt="#143523", text="#e8f7ec",
            muted="#8fc3a0", accent="#3fd98f", accent2="#12703f", accent_text="#03130a",
            border="#1b4a2f", success="#7be08a", danger="#ff8a80",
        ),
    },
    "sunset": {
        "label": "Sunset",
        "blurb": "orange into purple",
        "tokens": dict(
            bg="#1a0f26", surface="#2a1739", surface_alt="#3b2050", text="#fff2ee",
            muted="#d3a6c6", accent="#ff9248", accent2="#b02fd0", accent_text="#1e0b00",
            border="#4d2a67", success="#7be08a", danger="#ff8a80",
        ),
    },
    "neon": {
        "label": "Neon",
        "blurb": "pink and cyan on dark",
        "tokens": dict(
            bg="#07000e", surface="#12001f", surface_alt="#1f0537", text="#f6ecff",
            muted="#b592dc", accent="#ff2bd6", accent2="#18dcf5", accent_text="#12001f",
            border="#40106b", success="#3dffb0", danger="#ff6b8b",
        ),
    },
    "midnight": {
        "label": "Midnight",
        "blurb": "navy and soft white",
        "tokens": dict(
            bg="#090d1a", surface="#111830", surface_alt="#1a2444", text="#eef1ff",
            muted="#97a3cb", accent="#8e97ff", accent2="#4b52d9", accent_text="#08091a",
            border="#242f57", success="#6ee7b7", danger="#ff8fa0",
        ),
    },
    "sakura": {
        "label": "Sakura",
        "blurb": "soft pinks",
        "tokens": dict(
            bg="#fff3f7", surface="#ffffff", surface_alt="#ffe3ec", text="#3a1b28",
            muted="#93677a", accent="#d9407a", accent2="#f7a3c2", accent_text="#ffffff",
            border="#f3cbd9", success="#1f9d63", danger="#c62850",
        ),
    },
    "contrast": {
        "label": "High contrast",
        "blurb": "for accessibility",
        "tokens": dict(
            bg="#000000", surface="#000000", surface_alt="#1a1a1a", text="#ffffff",
            muted="#e6e6e6", accent="#ffe600", accent2="#00e5ff", accent_text="#000000",
            border="#ffffff", success="#00ff66", danger="#ff5c5c",
        ),
    },
    "custom": {
        "label": "Custom",
        "blurb": "your own colors, set under [theme.custom]",
        "tokens": {},  # filled from the [theme.custom] table, gaps come from Black
    },
}

DEFAULT_THEME = "ocean"

# Old names that still work in existing config files and on the command line.
THEME_ALIASES = {"volcano": "flames"}


def normalize_theme(name: object) -> str:
    """Lower-case a theme name and map old names (volcano) to current ones (flames)."""
    n = str(name or "").strip().lower()
    return THEME_ALIASES.get(n, n)

# card radius, control (input/step) radius, button radius
CORNERS: dict[str, tuple[str, str, str]] = {
    "sharp": ("0px", "0px", "0px"),
    "rounded": ("16px", "10px", "10px"),
    "pill": ("28px", "999px", "999px"),
}

FONTS: dict[str, str] = {
    "system": 'system-ui, -apple-system, "Segoe UI Variable Text", "Segoe UI", Roboto, "Helvetica Neue", sans-serif',
    "mono": 'ui-monospace, "Cascadia Code", "SF Mono", Consolas, Menlo, monospace',
    "serif": 'Charter, "Iowan Old Style", "Palatino Linotype", Georgia, serif',
    "rounded": '"Nunito", "SF Pro Rounded", "Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif',
}
MONO_STACK = FONTS["mono"]

_COLOR = re.compile(
    r"^(#[0-9a-fA-F]{3,8}|(?:rgb|hsl)a?\(\s*[0-9.,%/\s-]+\))$"
)


def is_color(value: Any) -> bool:
    """True for #hex, rgb()/rgba() and hsl()/hsla() strings. Anything else is ignored."""
    return isinstance(value, str) and bool(_COLOR.match(value.strip()))


def theme_choices() -> list[tuple[str, str, str]]:
    """(name, label, blurb) for every theme, in display order."""
    return [(name, t["label"], t["blurb"]) for name, t in THEMES.items()]


def swatch(name: str) -> str:
    """A representative color for a theme (used for previews in the terminal)."""
    tokens = THEMES[name]["tokens"] or THEMES["black"]["tokens"]
    return tokens["accent"]


def resolve_tokens(theme: str, accent: str = "", custom: dict[str, Any] | None = None) -> dict[str, str]:
    """Final color tokens for a theme, after applying the accent override and custom colors."""
    name = normalize_theme(theme)
    if name not in THEMES:
        name = DEFAULT_THEME
    tokens = dict(THEMES["black"]["tokens"])
    tokens.update(THEMES[name]["tokens"])
    tokens["console"] = _CONSOLE.get(name, "")
    if name == "custom":
        for key, value in (custom or {}).items():
            k = key.replace("-", "_")
            if k in TOKEN_NAMES and is_color(value):
                tokens[k] = value.strip()
    if not tokens["console"]:
        tokens["console"] = tokens["surface"]
    if is_color(accent):
        tokens["accent"] = accent.strip()
    return tokens


def css_variables(style: dict[str, Any], custom: dict[str, Any] | None = None) -> str:
    """The ``:root { ... }`` block that carries every design decision from the config."""
    tokens = resolve_tokens(style.get("theme", DEFAULT_THEME), style.get("accent", ""), custom)
    card, control, button = CORNERS.get(style.get("corners", "rounded"), CORNERS["rounded"])
    font = FONTS.get(style.get("font", "system"), FONTS["system"])
    animated = bool(style.get("animations", True))
    parts = [f"--{k.replace('_', '-')}:{v}" for k, v in tokens.items()]
    parts += [
        f"--r-card:{card}",
        f"--r-control:{control}",
        f"--r-button:{button}",
        f"--font:{font}",
        f"--mono:{MONO_STACK}",
        f"--t-fast:{'.15s' if animated else '0s'}",
        f"--t-page:{'.32s' if animated else '0s'}",
    ]
    return ":root{" + ";".join(parts) + "}"

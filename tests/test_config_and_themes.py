from customstaller.config import Project, dumps, deep_merge, DEFAULTS
from customstaller.themes import THEMES, css_variables, is_color, resolve_tokens, TOKEN_NAMES


def test_toml_roundtrip(tmp_path):
    p = Project(root=tmp_path)
    p.app["name"] = 'Quote "Me" \\ and unicode é'
    p.order.extend(["home", "finish"])
    p.data["theme"] = {"custom": {"bg": "#101010", "accent": "#ff8800"}}
    p.save()
    loaded = Project.load(tmp_path)
    assert loaded.app["name"] == 'Quote "Me" \\ and unicode é'
    assert loaded.order == ["home", "finish"]
    assert loaded.data["theme"]["custom"]["accent"] == "#ff8800"


def test_missing_keys_fall_back_to_defaults(tmp_path):
    (tmp_path / "customstaller.toml").write_text('[app]\nname = "X"\n')
    p = Project.load(tmp_path)
    assert p.app["name"] == "X"
    assert p.style["theme"] == DEFAULTS["style"]["theme"]


def test_every_theme_has_all_tokens():
    for name, theme in THEMES.items():
        tokens = resolve_tokens(name)
        assert set(TOKEN_NAMES) <= set(tokens), name
        assert all(is_color(v) for v in tokens.values()), name


def test_requested_themes_exist():
    for name in ("black", "white", "ocean", "flames"):
        assert name in THEMES


def test_accent_override_and_custom_theme():
    assert resolve_tokens("ocean", accent="#123456")["accent"] == "#123456"
    assert resolve_tokens("ocean", accent="red; }")["accent"] == THEMES["ocean"]["tokens"]["accent"]
    custom = resolve_tokens("custom", custom={"bg": "#010203", "evil": "#fff", "text": "url(x)"})
    assert custom["bg"] == "#010203"
    assert custom["text"] == THEMES["black"]["tokens"]["text"]  # invalid color ignored


def test_corner_and_animation_variables():
    css = css_variables({"theme": "black", "corners": "sharp", "animations": False})
    assert "--r-button:0px" in css and "--t-page:0s" in css
    css = css_variables({"theme": "black", "corners": "pill", "animations": True})
    assert "--r-button:999px" in css and "--t-page:.32s" in css


def test_volcano_is_still_accepted_as_flames():
    from customstaller.themes import normalize_theme
    assert normalize_theme("Volcano") == "flames"
    assert resolve_tokens("volcano") == resolve_tokens("flames")
    assert THEMES["flames"]["label"] == "Flames"

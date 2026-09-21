import json
import shutil
import time
from pathlib import Path

import pytest

from customstaller.cli import main
from customstaller.config import Project
from customstaller.runtime import InstallerApp
from customstaller.themes import resolve_tokens
from customstaller.ui import render_shell

from test_runtime import Client

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "hello-installer"


def _wait_done(client):
    for _ in range(100):
        log = json.loads(client.call("GET", "/api/log?since=0")[1])
        if not log["running"]:
            return log
        time.sleep(0.05)
    raise AssertionError("install never finished")


@pytest.fixture
def example(tmp_path):
    dest = tmp_path / "example"
    shutil.copytree(EXAMPLE, dest)
    app = InstallerApp(Project.load(dest))
    app.ctx.state["install_dir"] = str(tmp_path / "out")
    app.serve_in_background()
    yield app, Client(app), tmp_path / "out"
    app.stop()


def test_example_installs_docs_when_ticked(example):
    app, c, out = example
    assert app.ids == ["home", "license", "components", "console", "finish"]
    c.post("/api/set", {"id": "license", "key": "accepted", "value": True})
    c.post("/api/enter", {"id": "components", "from": "license"})
    assert "bytes in total" in c.post("/api/call", {"id": "components", "method": "size", "args": []})[1]["result"]
    c.post("/api/run", {"id": "console"})
    log = _wait_done(c)
    assert log["finished"] and log["progress"] == 1.0
    assert (out / "hello.txt").exists() and (out / "manual.txt").exists()


def test_example_skips_docs_when_unticked(example):
    app, c, out = example
    c.post("/api/set", {"id": "components", "key": "docs", "value": False})
    c.post("/api/run", {"id": "console"})
    assert _wait_done(c)["finished"]
    assert (out / "hello.txt").exists() and not (out / "manual.txt").exists()


def test_shell_survives_hostile_app_names(tmp_path):
    p = Project(root=tmp_path)
    p.app["name"] = '</script><img src=x onerror=alert(1)> "quoted"'
    html = render_shell(app=p.app, style=p.style, custom_theme={}, tabs=[{"id": "a", "title": "</script>x", "icon": ""}],
                        token="tok", project_root=tmp_path)
    assert "<img src=x" not in html
    assert html.count("</script>") == 1  # only the real closing tag
    assert "\\u003c/script\\u003ex" in html


def test_custom_theme_console_defaults_to_surface():
    t = resolve_tokens("custom", custom={"surface": "#eeeeee"})
    assert t["console"] == "#eeeeee"
    t = resolve_tokens("custom", custom={"surface": "#eeeeee", "console": "#101010"})
    assert t["console"] == "#101010"
    assert resolve_tokens("white")["console"] == "#ffffff"


def test_cli_init_refuses_to_clobber_and_force_keeps_tabs(project_dir, capsys):
    assert main(["init", "--yes"]) == 1
    (project_dir / "tabs" / "home.py").write_text("# my edits\n")
    assert main(["init", "--yes", "--force", "--theme", "neon"]) == 0
    assert (project_dir / "tabs" / "home.py").read_text() == "# my edits\n"
    assert Project.load(project_dir).style["theme"] == "neon"


def test_cli_theme_command_updates_config(project_dir):
    assert main(["theme", "--theme", "volcano", "--corners", "pill", "--layout", "top", "--accent", "#ff8800", "--no-animations"]) == 0
    s = Project.load(project_dir).style
    assert (s["theme"], s["corners"], s["layout"], s["accent"], s["animations"]) == ("flames", "pill", "top", "#ff8800", False)


def test_cli_without_a_project_gives_a_helpful_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["tab", "list"]) == 1
    assert "customstaller init" in capsys.readouterr().err


def test_cli_tab_subcommands(project_dir):
    assert main(["tab", "new", "Pick", "Components"]) == 0
    assert Project.load(project_dir).order[2] == "pick_components"
    assert main(["tab", "remove", "license"]) == 0
    assert main(["tab", "add", "license"]) == 0
    assert main(["tab", "move", "finish", "up"]) == 0
    assert main(["tab", "remove", "nope"]) == 1


def test_cusinstal_flags_and_options_alias(project_dir, capsys):
    assert main(["--tabs"]) == 0                      # not a terminal here: prints the list
    assert "Home" in capsys.readouterr().out
    assert main(["options", "--theme", "sakura"]) == 0
    assert Project.load(project_dir).style["theme"] == "sakura"
    assert main(["theme", "--theme", "black"]) == 0   # old name still works
    assert Project.load(project_dir).style["theme"] == "black"

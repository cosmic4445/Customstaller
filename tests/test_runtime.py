import json
import time
import urllib.error
import urllib.request

import pytest

from customstaller.config import Project
from customstaller.runtime import InstallerApp


class Client:
    def __init__(self, app):
        self.app = app
        self.base = f"http://127.0.0.1:{app.port}"

    def call(self, method, path, body=None, token=True, host=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-CS-Token"] = self.app.token
        if host:
            headers["Host"] = host
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def post(self, path, body=None, **kw):
        status, raw = self.call("POST", path, body or {}, **kw)
        return status, json.loads(raw)


@pytest.fixture
def app(project_dir):
    a = InstallerApp(Project.load(project_dir))
    a.ctx.state["install_dir"] = str(project_dir / "installed")
    a.serve_in_background()
    yield a
    a.stop()


@pytest.fixture
def client(app):
    return Client(app)


def test_shell_needs_the_token_and_contains_the_theme(app, client):
    status, _ = client.call("GET", "/")
    assert status == 403
    status, body = client.call("GET", f"/?t={app.token}")
    html = body.decode()
    assert status == 200
    assert "--accent:#3d95ff" in html  # ocean
    assert "Test App" in html
    assert '"id": "home"' in html or '"id":"home"' in html


def test_api_rejects_missing_token_and_bad_host(client):
    assert client.post("/api/can", {"id": "home"}, token=False)[0] == 403
    assert client.post("/api/can", {"id": "home"}, host="evil.example:80")[0] == 403
    status, _ = client.call("GET", "/api/log?since=0", token=False)
    assert status == 403


def test_home_renders_and_escapes(app, client):
    app.ctx.app.name = '<script>alert(1)</script>'
    status, res = client.post("/api/enter", {"id": "home"})
    assert status == 200
    assert "<script>" not in res["html"]
    assert "&lt;script&gt;" in res["html"]


def test_license_gate(client):
    status, res = client.post("/api/enter", {"id": "license", "from": "home"})
    assert res["canContinue"] is False
    assert "Example license text" in res["html"]
    # cannot skip past it
    assert client.post("/api/enter", {"id": "console", "from": "license"})[1] == {"denied": True}
    # tick the box
    assert client.post("/api/set", {"id": "license", "key": "accepted", "value": True})[1]["canContinue"] is True
    res = client.post("/api/enter", {"id": "console", "from": "license"})[1]
    assert res["canContinue"] is False and 'id="cs-log"' in res["html"]


def test_full_install_flow(app, client, project_dir):
    client.post("/api/set", {"id": "home", "key": "install_dir", "value": str(project_dir / "out")})
    client.post("/api/set", {"id": "license", "key": "accepted", "value": True})
    client.post("/api/enter", {"id": "console", "from": "license"})
    assert client.post("/api/run", {"id": "console"})[1]["started"] is True
    for _ in range(100):
        status, raw = client.call("GET", "/api/log?since=0")
        log = json.loads(raw)
        if log["finished"] or log["error"]:
            break
        time.sleep(0.05)
    assert log["finished"] and not log["error"], log
    assert log["progress"] == 1.0
    assert (project_dir / "out" / "app.txt").read_text() == "hello"
    assert (project_dir / "out" / "bin" / "tool.txt").read_text() == "tool"
    assert any("Installing to" in line for line in log["lines"])
    assert client.post("/api/can", {"id": "console"})[1]["canContinue"] is True
    fin = client.post("/api/enter", {"id": "finish", "from": "console"})[1]
    assert "Test App is installed" in fin["html"]
    # incremental log reading
    tail = json.loads(client.call("GET", f"/api/log?since={log['next']}")[1])
    assert tail["lines"] == []


def test_failed_run_reports_error_and_can_retry(app, client, project_dir):
    (project_dir / "tabs" / "console.py").write_text(
        "from customstaller import Tab\n"
        "class C(Tab):\n"
        "    title='Install'\n"
        "    def render(self, ctx): return self.console_view(ctx)\n"
        "    def run(self, ctx):\n"
        "        if not ctx.state.get('ok'): raise RuntimeError('disk is full')\n"
        "        ctx.log('fine')\n"
        "    def can_continue(self, ctx): return ctx.finished\n"
    )
    app2 = InstallerApp(Project.load(project_dir))
    app2.serve_in_background()
    try:
        c = Client(app2)
        c.post("/api/run", {"id": "console"})
        for _ in range(100):
            log = json.loads(c.call("GET", "/api/log?since=0")[1])
            if not log["running"]:
                break
            time.sleep(0.05)
        assert log["error"] == "disk is full" and not log["finished"]
        assert c.post("/api/can", {"id": "console"})[1]["canContinue"] is False
        c.post("/api/set", {"id": "console", "key": "ok", "value": True})
        c.post("/api/run", {"id": "console"})
        for _ in range(100):
            log = json.loads(c.call("GET", "/api/log?since=0")[1])
            if not log["running"]:
                break
            time.sleep(0.05)
        assert log["finished"] and log["error"] is None and log["lines"] == ["fine"]
    finally:
        app2.stop()


def test_actions_are_whitelisted(app, client, project_dir):
    (project_dir / "tabs" / "home.py").write_text(
        "from customstaller import Tab, action\n"
        "class H(Tab):\n"
        "    title='Home'\n"
        "    @action\n"
        "    def hi(self, ctx, who): return f'hi {who}'\n"
        "    def secret(self, ctx): return 'nope'\n"
    )
    app2 = InstallerApp(Project.load(project_dir))
    app2.serve_in_background()
    try:
        c = Client(app2)
        assert c.post("/api/call", {"id": "home", "method": "hi", "args": ["Ada"]})[1] == {"result": "hi Ada"}
        assert "error" in c.post("/api/call", {"id": "home", "method": "secret", "args": []})[1]
        assert "error" in c.post("/api/call", {"id": "home", "method": "render", "args": []})[1]
    finally:
        app2.stop()


def test_a_crashing_render_does_not_crash_setup(project_dir):
    (project_dir / "tabs" / "home.py").write_text(
        "from customstaller import Tab\n"
        "class H(Tab):\n"
        "    title='Home'\n"
        "    def render(self, ctx): raise KeyError('oops')\n"
    )
    app = InstallerApp(Project.load(project_dir))
    app.serve_in_background()
    try:
        res = Client(app).post("/api/enter", {"id": "home"})[1]
        assert "This page has an error" in res["html"] and "oops" in res["html"]
    finally:
        app.stop()


def test_assets_are_served_only_from_assets_dir(app, client, project_dir):
    (project_dir / "assets").mkdir(exist_ok=True)
    (project_dir / "assets" / "logo.png").write_bytes(b"\x89PNG fake")
    assert client.call("GET", "/assets/logo.png")[0] == 200
    assert client.call("GET", "/assets/../customstaller.toml")[0] == 404
    assert client.call("GET", "/assets/%2e%2e/customstaller.toml")[0] == 404
    assert client.call("GET", "/assets/missing.png")[0] == 404


def test_unknown_tab_is_a_400_not_a_crash(client):
    status, body = client.post("/api/enter", {"id": "nope"})
    assert status == 400
    assert client.post("/api/close", {})[1] == {"ok": True}

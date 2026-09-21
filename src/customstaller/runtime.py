"""Runs an installer: a small local server plus a window (or browser) that shows it.

The server only listens on 127.0.0.1, checks the Host header (blocks DNS rebinding)
and requires a random per-session token on every API call (blocks other web pages
from driving the installer).
"""

from __future__ import annotations

import json
import mimetypes
import secrets
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from .config import CustomstallerError, Project
from .core import Context, Tab
from .tabs import load_tabs
from .ui import render_shell

IDLE_SHUTDOWN_SECONDS = 120  # browser mode: exit if the page stops pinging


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


class InstallerApp:
    """One installer session: the tabs, the shared Context and the HTTP server."""

    def __init__(self, project: Project):
        self.project = project
        self.ctx = Context(project.root, project.data)
        self.tabs: list[tuple[str, Tab]] = load_tabs(project)
        if not self.tabs:
            raise CustomstallerError(
                "This installer has no tabs yet. Run `customstaller tab` to add some."
            )
        self.by_id = dict(self.tabs)
        self.ids = [slug for slug, _ in self.tabs]
        self.token = secrets.token_urlsafe(24)
        self.closed = threading.Event()
        self.close_hooks: list[Callable[[], None]] = []
        self.last_ping: float | None = None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(self))
        self.port = self.httpd.server_address[1]

    # -- addresses --------------------------------------------------------- #

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"

    def allowed_hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    # -- pages ------------------------------------------------------------- #

    def shell(self) -> str:
        custom = self.project.data.get("theme", {}).get("custom", {})
        tabs = [{"id": slug, "title": str(t.title), "icon": str(t.icon or "")} for slug, t in self.tabs]
        return render_shell(
            app=self.project.app, style=self.project.style, custom_theme=custom,
            tabs=tabs, token=self.token, project_root=self.project.root,
        )

    def _tab(self, tid: Any) -> Tab:
        if tid not in self.by_id:
            raise KeyError(f"Unknown tab: {tid!r}")
        return self.by_id[tid]

    def _safely(self, fn: Callable[[], Any], what: str, default: Any = None) -> Any:
        try:
            return fn()
        except Exception:  # noqa: BLE001 - a broken tab must not crash setup
            print(f"[customstaller] {what} failed:", file=sys.stderr)
            traceback.print_exc()
            return default

    def _render(self, tid: str) -> str:
        tab = self._tab(tid)
        try:
            return str(tab.render(self.ctx))
        except Exception as exc:  # noqa: BLE001
            print(f"[customstaller] render of '{tid}' failed:", file=sys.stderr)
            traceback.print_exc()
            msg = self.ctx.esc(f"{type(exc).__name__}: {exc}")
            return f'<div class="error"><b>This page has an error.</b><br>{msg}</div>'

    def _can(self, tid: str) -> bool:
        tab = self._tab(tid)
        return bool(self._safely(lambda: tab.can_continue(self.ctx), f"can_continue of '{tid}'", False))

    # -- API --------------------------------------------------------------- #

    def api_enter(self, body: dict) -> dict:
        tid, frm = body.get("id"), body.get("from")
        tab = self._tab(tid)
        if frm in self.by_id and frm != tid:
            if self.ids.index(tid) > self.ids.index(frm) and not self._can(frm):
                return {"denied": True}
            self._safely(lambda: self.by_id[frm].on_leave(self.ctx), f"on_leave of '{frm}'")
        self._safely(lambda: tab.on_enter(self.ctx), f"on_enter of '{tid}'")
        return {
            "html": self._render(tid),
            "canContinue": self._can(tid),
            "autoRun": bool(tab.has_run and tab.auto_run and not self.ctx.started),
        }

    def api_render(self, body: dict) -> dict:
        tid = body.get("id")
        return {"html": self._render(tid), "canContinue": self._can(tid)}

    def api_can(self, body: dict) -> dict:
        return {"canContinue": self._can(body.get("id"))}

    def api_set(self, body: dict) -> dict:
        key = body.get("key")
        if not isinstance(key, str) or not key or len(key) > 200:
            raise ValueError("key must be a short string")
        self.ctx.state[key] = body.get("value")
        return {"canContinue": self._can(body.get("id"))}

    def api_run(self, body: dict) -> dict:
        tab = self._tab(body.get("id"))
        if not tab.has_run:
            return {"started": False}
        return {"started": self.ctx._begin(lambda: tab.run(self.ctx))}

    def api_call(self, body: dict) -> dict:
        tab = self._tab(body.get("id"))
        name = str(body.get("method", ""))
        fn = getattr(tab, name, None)
        if not callable(fn) or not getattr(fn, "_cs_action", False):
            return {"error": f"'{name}' isn't an action. Add @action above it in the tab file."}
        args = body.get("args")
        try:
            return {"result": _jsonable(fn(self.ctx, *(args if isinstance(args, list) else [])))}
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return {"error": str(exc) or type(exc).__name__}

    def api_close(self, _body: dict) -> dict:
        self.closed.set()
        for hook in self.close_hooks:
            threading.Timer(0.3, hook).start()
        return {"ok": True}

    def api_ping(self, _body: dict) -> dict:
        self.last_ping = time.monotonic()
        return {"ok": True}

    def idle_too_long(self) -> bool:
        if self.last_ping is None or self.ctx.running:
            return False
        return time.monotonic() - self.last_ping > IDLE_SHUTDOWN_SECONDS

    POST_ROUTES = {
        "/api/enter": "api_enter", "/api/render": "api_render", "/api/can": "api_can",
        "/api/set": "api_set", "/api/run": "api_run", "/api/call": "api_call",
        "/api/close": "api_close", "/api/ping": "api_ping",
    }

    # -- serving ----------------------------------------------------------- #

    def serve_in_background(self) -> threading.Thread:
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _make_handler(app: InstallerApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "Customstaller"
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args: Any) -> None:  # keep the terminal quiet
            pass

        # -- helpers -- #
        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj: Any, status: int = 200) -> None:
            self._send(status, json.dumps(obj).encode(), "application/json")

        def _guard(self) -> bool:
            """Host and token checks. Sends the error itself and returns False on failure."""
            if self.headers.get("Host", "") not in app.allowed_hosts():
                self._json({"error": "bad host"}, 403)
                return False
            return True

        def _token_ok(self) -> bool:
            if not secrets.compare_digest(self.headers.get("X-CS-Token", ""), app.token):
                self._json({"error": "bad token"}, 403)
                return False
            return True

        # -- routes -- #
        def do_GET(self) -> None:  # noqa: N802
            if not self._guard():
                return
            url = urlparse(self.path)
            if url.path == "/":
                token = parse_qs(url.query).get("t", [""])[0]
                if not secrets.compare_digest(token, app.token):
                    self._send(403, b"Open the link that Customstaller printed.", "text/plain")
                    return
                self._send(200, app.shell().encode(), "text/html; charset=utf-8")
            elif url.path.startswith("/assets/"):
                self._asset(unquote(url.path[len("/assets/"):]))
            elif url.path == "/api/log":
                if not self._token_ok():
                    return
                since = parse_qs(url.query).get("since", ["0"])[0]
                self._json(app.ctx.snapshot(int(since) if since.isdigit() else 0))
            else:
                self._send(404, b"Not found", "text/plain")

        def _asset(self, rel: str) -> None:
            root = (app.project.root / "assets").resolve()
            target = (root / rel).resolve()
            if root not in target.parents or not target.is_file():
                self._send(404, b"Not found", "text/plain")
                return
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), ctype)

        def do_POST(self) -> None:  # noqa: N802
            if not self._guard() or not self._token_ok():
                return
            route = app.POST_ROUTES.get(urlparse(self.path).path)
            if route is None:
                self._send(404, b"Not found", "text/plain")
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 1_000_000:
                    self._json({"error": "request too large"}, 413)
                    return
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("body must be an object")
            except (ValueError, json.JSONDecodeError):
                self._json({"error": "bad request"}, 400)
                return
            try:
                self._json(getattr(app, route)(body))
            except (KeyError, ValueError) as exc:
                self._json({"error": str(exc)}, 400)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                self._json({"error": "internal error"}, 500)

    return Handler


# --------------------------------------------------------------------------- #
# Launching
# --------------------------------------------------------------------------- #


def _try_window(app: InstallerApp) -> bool:
    """Open a real desktop window with pywebview. False if it isn't available."""
    try:
        import webview  # type: ignore[import-not-found]
    except ImportError:
        return False
    a = app.project.app
    try:
        window = webview.create_window(
            f"{a['name']} Setup", app.url,
            width=int(a.get("window_width", 960)), height=int(a.get("window_height", 640)),
            min_size=(640, 460),
        )
        app.close_hooks.append(window.destroy)
        webview.start()
        return True
    except Exception:  # noqa: BLE001 - e.g. no GUI backend: fall back to the browser
        traceback.print_exc()
        return False


def run_installer(root: Path | str, mode: str = "auto") -> int:
    """Run the installer for the project in ``root``.

    mode: ``auto`` (window if pywebview is installed, else browser), ``window``,
    ``browser``, or ``none`` (start the server and print the URL; used for testing).
    """
    app = InstallerApp(Project.load(Path(root)))
    app.serve_in_background()
    try:
        if mode in ("auto", "window") and _try_window(app):
            return 0
        if mode == "window":
            raise CustomstallerError(
                "A desktop window needs pywebview. Install it with: pip install \"customstaller[window]\""
            )
        print(f"Setup is running at {app.url}", flush=True)
        if mode != "none":
            webbrowser.open(app.url)
        while not app.closed.wait(1.0):
            if app.idle_too_long():
                break
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
    return 0

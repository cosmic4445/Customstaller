"""The public API that tab files build on: ``Tab``, ``action`` and ``Context``."""

from __future__ import annotations

import html
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable


def action(fn: Callable) -> Callable:
    """Mark a Tab method as callable from the page with ``cs.call("method", ...)``."""
    fn._cs_action = True  # type: ignore[attr-defined]
    return fn


class Tab:
    """One page of the installer. Subclass it in a file under ``tabs/``.

    Every hook is optional. ``render`` returns the page's HTML.
    """

    title = "Untitled"
    icon = ""  # optional emoji shown in the step list instead of the step number
    auto_run = False  # True: call `run` as soon as this tab is opened

    def render(self, ctx: "Context") -> str:
        """Return the HTML for this page. Called every time the tab is shown."""
        return ""

    def can_continue(self, ctx: "Context") -> bool:
        """Return False to keep the Next button disabled (e.g. until a box is ticked)."""
        return True

    def on_enter(self, ctx: "Context") -> None:
        """Called when the user arrives on this tab."""

    def on_leave(self, ctx: "Context") -> None:
        """Called when the user leaves this tab."""

    def run(self, ctx: "Context") -> None:
        """Long-running work (the actual install). Runs on a background thread.

        Use ``ctx.log(...)`` and ``ctx.progress(0..1)`` to report back. Raise an
        exception to fail; the user sees the message and can retry.
        """

    # -- helpers ---------------------------------------------------------- #

    @property
    def has_run(self) -> bool:
        return type(self).run is not Tab.run

    def console_view(self, ctx: "Context", button: str = "Install") -> str:
        """Ready-made log window, progress bar and button wired to ``run``."""
        return f"""
        <h1>{ctx.esc(self.title)}</h1>
        <div class="console" id="cs-log" role="log" aria-live="polite"></div>
        <div class="progress" aria-hidden="true"><div id="cs-bar"></div></div>
        <div class="row">
          <span id="cs-status" class="muted" role="status">Ready.</span>
          <span class="spacer"></span>
          <button class="btn primary" id="cs-run" data-label="{ctx.esc(button)}"
                  onclick="cs.run()">{ctx.esc(button)}</button>
        </div>
        """


def _default_install_dir(name: str) -> Path:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip() or "App"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Programs" / safe
    if sys.platform == "darwin":
        return Path.home() / "Applications" / safe
    return Path.home() / ".local" / "share" / safe


class Context:
    """Shared state for one installer session. Passed as ``ctx`` to every hook."""

    def __init__(self, project_root: Path, config: dict[str, Any]):
        self.project_dir = Path(project_root)
        self.config = config
        app = config["app"]
        self.app = SimpleNamespace(
            name=app["name"], version=app["version"], publisher=app.get("publisher", "")
        )
        self.state: dict[str, Any] = {}
        configured = str(app.get("install_dir") or "").strip()
        self.state["install_dir"] = configured or str(_default_install_dir(app["name"]))

        self._lock = threading.Lock()
        self._lines: list[str] = []
        self._progress = 0.0
        self.running = False
        self.finished = False
        self.started = False
        self.error: str | None = None

    # -- paths ------------------------------------------------------------ #

    @property
    def install_dir(self) -> Path:
        raw = str(self.state.get("install_dir") or "")
        return Path(os.path.expandvars(os.path.expanduser(raw)))

    def read_text(self, *names: str) -> str:
        """Text of the first file that exists in the project folder, else ''."""
        for name in names:
            path = self.project_dir / name
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace")
        return ""

    def asset_url(self, name: str) -> str:
        """URL for a file in ``assets/``, for use in ``<img src=...>``."""
        return "/assets/" + name.lstrip("/")

    # -- html ------------------------------------------------------------- #

    @staticmethod
    def esc(value: Any) -> str:
        """HTML-escape a value. Use it for anything you put inside markup."""
        return html.escape(str(value), quote=True)

    # -- reporting from `run` ---------------------------------------------- #

    def log(self, line: str = "") -> None:
        with self._lock:
            self._lines.append(str(line))

    def progress(self, fraction: float) -> None:
        with self._lock:
            self._progress = max(0.0, min(1.0, float(fraction)))

    def snapshot(self, since: int = 0) -> dict[str, Any]:
        with self._lock:
            since = max(0, min(since, len(self._lines)))
            return {
                "lines": self._lines[since:],
                "next": len(self._lines),
                "progress": self._progress,
                "running": self.running,
                "finished": self.finished,
                "error": self.error,
            }

    # -- helpers for real installs ---------------------------------------- #

    def copy_payload(self, subdir: str = "payload", progress_range: tuple[float, float] = (0.0, 1.0)) -> int:
        """Copy everything in ``payload/`` into the install folder, logging as it goes.

        ``subdir`` can point at a folder inside the project (e.g. ``"payload/docs"``) and
        ``progress_range`` is the slice of the progress bar this call fills, so several
        calls in a row can share one bar.
        """
        lo, hi = progress_range
        src_root = self.project_dir / subdir
        files = sorted(p for p in src_root.rglob("*") if p.is_file()) if src_root.is_dir() else []
        if not files:
            self.log(f"Nothing in {subdir}/ yet. Put the files your app installs there.")
            return 0
        target = self.install_dir
        self.log(f"Installing to {target}")
        for i, src in enumerate(files, 1):
            rel = src.relative_to(src_root)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            self.log(f"  {rel}")
            self.progress(lo + (hi - lo) * i / len(files))
        return len(files)

    def run_command(
        self,
        args: str | Iterable[str],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> int:
        """Run a command and stream its output into the console."""
        as_shell = isinstance(args, str)
        shown = args if as_shell else " ".join(shlex.quote(str(a)) for a in args)
        self.log(f"$ {shown}")
        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            args if as_shell else [str(a) for a in args],
            cwd=cwd, env=env, shell=as_shell,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", bufsize=1, **kwargs,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            self.log(line.rstrip())
        code = proc.wait()
        if check and code != 0:
            raise RuntimeError(f"Command exited with code {code}: {shown}")
        return code

    # -- background runs (used by the runtime) ------------------------------ #

    def _begin(self, work: Callable[[], None]) -> bool:
        with self._lock:
            if self.running:
                return False
            self._lines.clear()
            self._progress = 0.0
            self.running, self.finished, self.started, self.error = True, False, True, None

        def target() -> None:
            try:
                work()
            except Exception as exc:  # noqa: BLE001 - shown to the user
                traceback.print_exc()
                with self._lock:
                    self.error = str(exc) or type(exc).__name__
                    self._lines.append(f"Error: {self.error}")
                    self.running = False
            else:
                with self._lock:
                    self._progress = 1.0
                    self.finished = True
                    self.running = False

        threading.Thread(target=target, daemon=True).start()
        return True

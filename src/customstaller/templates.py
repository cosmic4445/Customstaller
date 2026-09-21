"""Source text for the tab files that ``customstaller tab`` creates."""

from __future__ import annotations

HOME = '''\
"""Home: the first page people see."""
from customstaller import Tab


class Home(Tab):
    title = "Home"

    def render(self, ctx):
        by = f" by {ctx.esc(ctx.app.publisher)}" if ctx.app.publisher else ""
        return f"""
        <h1>Install {ctx.esc(ctx.app.name)}</h1>
        <p class="lead">Version {ctx.esc(ctx.app.version)}{by}</p>
        <p>Choose where to install it, then select Next.</p>
        <label class="field">
          <span>Install location</span>
          <input type="text" value="{ctx.esc(ctx.install_dir)}"
                 oninput="cs.set('install_dir', this.value)">
        </label>
        """
'''

LICENSE = '''\
"""License: shows your LICENSE file and asks people to accept it."""
from customstaller import Tab

NAMES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "license.txt")


class License(Tab):
    title = "License"

    def render(self, ctx):
        text = ctx.read_text(*NAMES)
        if not text:
            return """
            <h1>License</h1>
            <p class="lead">There are no license terms to review.</p>
            """
        checked = "checked" if ctx.state.get("accepted") else ""
        return f"""
        <h1>License agreement</h1>
        <p class="lead">Read the terms below to continue.</p>
        <pre class="scroll">{ctx.esc(text)}</pre>
        <label class="check">
          <input type="checkbox" {checked}
                 onchange="cs.set('accepted', this.checked)">
          <span>I accept the license terms</span>
        </label>
        """

    def can_continue(self, ctx):
        # Next stays disabled until the box is ticked (or there is nothing to accept).
        return bool(ctx.state.get("accepted")) or not ctx.read_text(*NAMES)
'''

CONSOLE = '''\
"""Console: runs the install and shows live output."""
from customstaller import Tab


class Console(Tab):
    title = "Install"        # what people see in the step list; rename freely
    auto_run = False         # True = start installing as soon as this page opens

    def render(self, ctx):
        return self.console_view(ctx, button="Install")

    def run(self, ctx):
        # Runs on a background thread when the user selects Install.
        # Copy everything in payload/ to the install location:
        ctx.copy_payload()

        # Add your own steps here. For example:
        #   ctx.run_command(["python", "-m", "pip", "install", "requests"])
        #   ctx.log("Creating shortcuts...")
        #   ctx.progress(0.9)          # 0.0 to 1.0

        ctx.log("Done.")

    def can_continue(self, ctx):
        return ctx.finished      # Next unlocks once the install has finished
'''

FINISH = '''\
"""Finish: the last page."""
from customstaller import Tab


class Finish(Tab):
    title = "Finish"

    def render(self, ctx):
        return f"""
        <h1>{ctx.esc(ctx.app.name)} is installed</h1>
        <p class="lead">Installed to <code>{ctx.esc(ctx.install_dir)}</code></p>
        <p>Select Close to exit setup.</p>
        """
'''

CUSTOM = '''\
"""New tab: __SLUG__."""
from customstaller import Tab, action


class __CLASS__(Tab):
    title = __TITLE__

    def render(self, ctx):
        return f"""
        <h1>{ctx.esc(self.title)}</h1>
        <p class="lead">This is a new tab. Edit tabs/__SLUG__.py to change what it shows.</p>
        """

    # ---- Optional hooks. Delete what you don't need. -------------------------
    #
    # def can_continue(self, ctx):    # return False to keep Next disabled
    #     return True
    #
    # def on_enter(self, ctx): ...    # the user arrived on this tab
    # def on_leave(self, ctx): ...    # the user left this tab
    # def run(self, ctx): ...         # background work; report with ctx.log() / ctx.progress()
    #
    # Let a button on the page call Python:
    #   <button class="btn" onclick="cs.call('greet', 'Ada')">Greet</button>
    #
    # @action
    # def greet(self, ctx, who):
    #     ctx.state["greeted"] = who
    #     return f"Hello, {who}!"
'''

PREMADE_SOURCES = {
    "home": HOME,
    "license": LICENSE,
    "console": CONSOLE,
    "finish": FINISH,
}


def render_custom(title: str, slug: str, class_name: str) -> str:
    """The empty template, filled in for a new tab."""
    return (
        CUSTOM.replace("__CLASS__", class_name)
        .replace("__SLUG__", slug)
        .replace("__TITLE__", repr(title))
    )

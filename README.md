# Customstaller

Vibrant, themeable installers you customize one tab at a time.

Developers drop Customstaller into their project, pick a theme, and edit a few small
Python files. No installer framework to learn, no UI to build.

```
pip install customstaller
customstaller init      # asks for a theme, corners, layout... and sets up your project
customstaller run       # preview the installer
cusinstal --tabs        # add tabs, or make your own (same as `customstaller tab`)
customstaller build     # package it into one executable
```

`cusinstal` is a short alias for `customstaller`, so `cusinstal --tabs` and
`cusinstal --options` work everywhere `customstaller tab` and `customstaller options` do.

> **Where do the Options questions appear?** `pip` can't ask questions while it installs
> (installs are non-interactive), so the Options come up the first time you run
> `customstaller init`. Change them any time with `cusinstal --options`.

## The `tab` menu

`cusinstal --tabs` (or `customstaller tab`) opens a small menu in your terminal:

```
◆ Tabs
 » ✓ Home     in your installer
   ✓ License  in your installer
   ✓ Console  in your installer
   ✓ Finish   in your installer
   + New
     ────────────
   Done
```

* Pick a **premade** tab (Home, License, Console, Finish) to add it. Pick one that's
  already there to move it earlier or later, or remove it from the installer.
* Pick **+ New** to open the New menu. Choose **Name your tab**, type a name, then choose
  **Add**. Customstaller creates `tabs/<name>.py` from an empty template and adds the tab
  to your installer, just before Console. Premade tabs get their files created the same way.

Everything the menu does is also available without a menu, for scripts:
`customstaller tab list | new NAME | add home | remove NAME | move NAME up`.

## Your project

```
my-project/
├── customstaller.toml     # app name, version, theme, tab order
├── LICENSE                # shown by the License tab
├── payload/               # files your app installs
├── assets/                # logo and other images
└── tabs/
    ├── home.py
    ├── license.py
    ├── console.py
    └── finish.py
```

There is a finished example in [`examples/hello-installer`](examples/hello-installer)
with a custom "Components" tab. Run it with:

```
cd examples/hello-installer
customstaller run
```

(It installs into `./hello-app-installed`, so nothing touches your system.)

## Writing a tab

A tab is a Python class. Every hook is optional.

```python
from customstaller import Tab, action

class Options(Tab):
    title = "Options"

    def render(self, ctx):                    # the page, as HTML
        return f"""
        <h1>Options</h1>
        <label class="check">
          <input type="checkbox" onchange="cs.set('shortcut', this.checked)">
          <span>Create a desktop shortcut</span>
        </label>
        """

    def can_continue(self, ctx):              # False keeps Next disabled
        return True

    def on_enter(self, ctx): ...              # user arrived
    def on_leave(self, ctx): ...              # user left
    def run(self, ctx): ...                   # background work (see Console)

    @action                                   # callable from the page: cs.call("hello", "Ada")
    def hello(self, ctx, who):
        return f"Hello, {who}!"
```

**In the page**, `cs.set(key, value)` stores a value in `ctx.state`, `cs.call(name, ...args)`
runs an `@action` method, `cs.run()` starts `run`, and `cs.refresh()` re-renders.

**On `ctx`**: `ctx.app` (name, version, publisher), `ctx.state` (a dict shared by all
tabs), `ctx.install_dir`, `ctx.esc(text)` (HTML-escape anything you put in markup),
`ctx.read_text("LICENSE")`, `ctx.log(line)`, `ctx.progress(0..1)`,
`ctx.copy_payload()`, `ctx.run_command([...])` (streams output into the console).

**Ready-made styles** for your HTML: `h1`, `h2`, `.lead`, `.muted`, `code`, `.card`,
`.cols`, `.row`, `.field` + `input[type=text]`, `.check`, `pre.scroll`, `.btn`,
`.btn.primary`, `.badge`, `.error`.

## Style

Set at `init`, changed with `cusinstal --options` or by editing `customstaller.toml`:

```toml
[style]
theme = "ocean"        # see below
corners = "rounded"    # sharp | rounded | pill
accent = ""            # e.g. "#ff6600" overrides the theme's accent
layout = "sidebar"     # sidebar | top
animations = true
font = "system"        # system | mono | serif | rounded
branding = true        # the small "Powered by Customstaller"
```

**Themes:** `black` (black and grey), `white` (white and grey), `ocean` (blue and deep
blue), `flames` (red and dark red; older configs that say `volcano` still work), `forest`, `sunset`, `neon`, `midnight`, `sakura`,
`contrast` (high contrast, for accessibility), and `custom`:

```toml
[style]
theme = "custom"

[theme.custom]         # any you leave out fall back to the Black theme
bg = "#fdf6e3"
surface = "#fffaf0"
text = "#3b3428"
accent = "#b5541c"
accent_text = "#ffffff"
# also: surface_alt, muted, accent2, border, success, danger, console
```

Put a logo in `assets/` and set `[app] logo = "logo.png"`.

## Building the installer

```
pip install "customstaller[build]"      # adds PyInstaller
customstaller build                     # -> dist/<App>-setup(.exe)
```

The result is a single file that doesn't need Python on the user's machine. **Build on
the operating system you're targeting**: PyInstaller can't cross-compile, so build on
Windows to get a Windows `.exe`. Modules your tab files import are detected and bundled;
list anything unusual under `[build] hidden_imports`.

For a real desktop window instead of your browser, add the window extra before building:

```
pip install "customstaller[window]"     # adds pywebview
```

Without it, the installer opens in the default browser and exits when you close it.

## How it works

Your tabs render HTML. Customstaller serves it from a small local server bound to
`127.0.0.1` and shows it in a window (pywebview) or the browser. The server checks the
`Host` header and requires a random per-session token on every request, so other web
pages can't drive the installer. Tab code only runs `@action` methods that you marked.

## Not in version 0.1

Customstaller is an installer *framework*, not a replacement for Windows Installer (MSI)
itself. Things it does not do yet: registry entries, Start menu/desktop shortcuts and
"Apps & features" uninstall entries, an uninstaller, admin elevation, code signing, and
auto-update. You can script registry and shortcut steps yourself from a tab's `run`
(for example with `ctx.run_command`), but there are no built-in helpers for them yet.

## Development

```
pip install -e ".[dev]"
pytest
```

MIT licensed.

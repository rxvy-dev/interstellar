"""Gtk.Application: single instance, command line, CSS, theme preview, session, quake window."""
import argparse, os, shlex, shutil, subprocess, sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gtk, Gdk, Gio, GLib

from . import APP_ID, NAME, VERSION, themes, liquid
from .chrome import build_css, PREFS_CSS
from .settings import Settings

LayerShell = None
try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell  # noqa
except (ValueError, ImportError):
    LayerShell = None


def parse_args(argv):
    p = argparse.ArgumentParser(prog="interstellar", add_help=True,
                                description="Interstellar Terminal — a terminal that's out of this world.")
    p.add_argument("-e", "--command", nargs=argparse.REMAINDER, help="run a command instead of the shell")
    p.add_argument("-d", "--working-directory", help="start in this folder")
    p.add_argument("-p", "--profile", help="profile to use")
    p.add_argument("-t", "--title", help="tab title")
    p.add_argument("--tab", action="store_true", help="open a tab in the existing window instead of a new window")
    p.add_argument("--quake", action="store_true", help="toggle the drop-down (quake) terminal")
    p.add_argument("--no-restore", action="store_true", help="don't restore the last session")
    p.add_argument("--preferences", action="store_true", help="open preferences")
    p.add_argument("--theme", help="use this theme (and remember it)")
    p.add_argument("--list-themes", action="store_true")
    p.add_argument("--import-theme", metavar="FILE", help="import a kitty / Alacritty / base16 theme")
    p.add_argument("--version", action="store_true")
    return p.parse_args(argv)


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        GLib.set_application_name(NAME)
        self.s = Settings()
        self.s.listeners.append(self.on_setting)
        self.windows_ = []
        self.quake_win = None
        self.prefs = None
        self._preview = None
        self.css = None
        self.restored = False

    # ------------------------------------------------------------------ theme / css
    def theme_name(self):
        return self._preview or self.s["theme"]

    def apply_css(self):
        th = themes.get(self.theme_name())
        style = liquid.effective_style(self.s["ui_style"], th)
        css = build_css(th, style, float(self.s["opacity"]), self.s["custom_css"],
                        glass={"radius": self.s["glass_radius"], "shadow": self.s["glass_shadow"]})
        css += f"\nvte-terminal {{ padding: {int(self.s['padding'])}px; }}\n"
        css += f"\n@define-color accent_color {th['accent']};\n" + PREFS_CSS
        if self.css is None:
            self.css = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css,
                                                      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        try:
            self.css.load_from_string(css)
        except AttributeError:  # GTK < 4.12
            self.css.load_from_data(css, -1)
        dark = themes.luminance(th["bg"]) < 0.5
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", dark)

    def preview_theme(self, name):
        if name == self._preview:
            return
        self._preview = name
        self.apply_css()
        for w in self.all_windows():
            w.apply_settings("theme")

    def on_setting(self, key):
        if key in ("theme", "ui_style", "opacity", "custom_css", "padding", "glass_radius", "glass_shadow", "*"):
            self.apply_css()
        for w in self.all_windows():
            w.apply_settings(key)
        if self.prefs and key == "*":
            self.prefs.reload()

    def all_windows(self):
        return [w for w in self.windows_ if w is not None] + ([self.quake_win] if self.quake_win else [])

    # ------------------------------------------------------------------ lifecycle
    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.apply_css()
        icons = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "icons")
        if os.path.isdir(icons):
            Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(os.path.normpath(icons))
        a = Gio.SimpleAction.new("focus-tab", GLib.VariantType.new("s"))
        a.connect("activate", self._focus_tab)
        self.add_action(a)
        for name, fn in (("new-window", lambda: self.new_window()), ("preferences", lambda: self.show_prefs()),
                         ("quit", self.quit_all)):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda *_a, f=fn: f())
            self.add_action(act)
        GLib.timeout_add_seconds(20, self._autosave)

    def do_command_line(self, cmdline):
        argv = cmdline.get_arguments()[1:]
        try:
            a = parse_args(argv)
        except SystemExit:
            return 1
        cwd = a.working_directory or cmdline.get_cwd()
        if a.version:
            cmdline.print_literal(f"{NAME} {VERSION}\n")
            return 0
        if a.list_themes:
            cmdline.print_literal("\n".join(("✦ " if t.get("space") else "  ") + t["name"] for t in themes.all_themes()) + "\n")
            return 0
        if a.import_theme:
            try:
                t = themes.import_file(os.path.join(cmdline.get_cwd() or "", a.import_theme))
                themes.save_custom(t)
                cmdline.print_literal(f"Imported theme “{t['name']}”. Use it with: interstellar --theme \"{t['name']}\"\n")
                return 0
            except (OSError, ValueError) as e:
                cmdline.printerr_literal(f"interstellar: {e}\n")
                return 1
        if a.theme:
            names = {t["name"].lower(): t["name"] for t in themes.all_themes()}
            if a.theme.lower() in names:
                self.s["theme"] = names[a.theme.lower()]
            else:
                cmdline.printerr_literal(f"interstellar: no theme called “{a.theme}” (see --list-themes)\n")
        if a.quake:
            self.toggle_quake()
            return 0
        if a.preferences:
            self.show_prefs()
            return 0
        profile = self.s.profile(a.profile) if a.profile else None
        argv_cmd = None
        if a.command:
            argv_cmd = a.command if len(a.command) > 1 else shlex.split(a.command[0])
        live = [w for w in self.windows_ if w.get_visible()]
        if a.tab and live:
            w = live[-1]
            w.new_tab(profile=profile, cwd=cwd, argv=argv_cmd, title=a.title)
            w.present()
            return 0
        restore = None
        if (not live and not self.restored and not a.no_restore and not argv_cmd and not a.working_directory
                and self.s["restore_session"] and self.s["session"]):
            restore = self.s["session"]
        self.restored = True
        if restore:
            for ws in restore:
                w = self.new_window(restore=ws.get("tabs") or None)
                cur = ws.get("current", 0)
                if 0 <= cur < len(w.tabs):
                    w.select_tab(w.tabs[cur])
            return 0
        w = self.new_window(cwd=cwd, argv=argv_cmd, profile=profile)
        if a.title and w.tabs:
            w.tabs[0].title = a.title
            w._refresh_tab(w.tabs[0])
        return 0

    def do_activate(self):
        if not self.windows_:
            self.new_window()
        else:
            self.windows_[-1].present()

    def new_window(self, cwd=None, argv=None, restore=None, profile=None):
        from .window import Window
        w = Window(self, restore=restore, cwd=cwd, argv=argv, profile=profile)
        self.windows_.append(w)
        w.present()
        return w

    def window_closing(self, w):
        if w is self.quake_win:
            self.quake_win = None
            return
        others = [x for x in self.windows_ if x is not w]
        if others:
            self.save_session(others)
        else:
            self.save_session([w])
        if w in self.windows_:
            self.windows_.remove(w)

    def save_session(self, wins=None):
        wins = self.windows_ if wins is None else wins
        if not self.s["restore_session"]:
            if self.s["session"]:
                self.s.set_quiet("session", [])
            return
        self.s.set_quiet("session", [w.state() for w in wins if w.tabs])

    def _autosave(self):
        if self.windows_:
            self.save_session()
        return True

    def quit_all(self):
        self.save_session()
        for w in list(self.all_windows()):
            w._really_close = True
            w.close()

    def _focus_tab(self, action, v):
        tid = v.get_string()
        for w in self.all_windows():
            for t in w.tabs:
                if t.id == tid:
                    w.select_tab(t)
                    w.present()
                    return

    def show_prefs(self, parent=None, page=None):
        from .prefs import Prefs
        if self.prefs is None:
            self.prefs = Prefs(self)
            self.prefs.connect("close-request", self._prefs_closed)
        if parent:
            self.prefs.set_transient_for(parent)
        if page:
            self.prefs.show_page(page)
        self.prefs.present()

    def _prefs_closed(self, *_):
        self.prefs = None
        return False

    # ------------------------------------------------------------------ quake (drop-down) window
    def toggle_quake(self):
        from .window import Window
        if self.quake_win is None:
            w = Window(self, quake=True)
            self.quake_win = w
            self._place_quake(w)
            w.present()
            return
        w = self.quake_win
        if w.get_visible() and w.is_active():
            w.set_visible(False)
        else:
            w.set_visible(True)
            w.present()
            self._place_quake(w)

    def _place_quake(self, w):
        disp = Gdk.Display.get_default()
        mons = disp.get_monitors()
        mon = mons.get_item(0) if mons.get_n_items() else None
        geo = mon.get_geometry() if mon else None
        height = int((geo.height if geo else 800) * float(self.s["quake_height"]))
        width = geo.width if geo else 1200
        if LayerShell is not None and LayerShell.is_supported():
            if not LayerShell.is_layer_window(w):
                LayerShell.init_for_window(w)
                LayerShell.set_layer(w, LayerShell.Layer.TOP)
                for edge in (LayerShell.Edge.TOP, LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT):
                    LayerShell.set_anchor(w, edge, True)
                LayerShell.set_keyboard_mode(w, LayerShell.KeyboardMode.ON_DEMAND)
                LayerShell.set_namespace(w, "interstellar-quake")
            w.set_default_size(width, height)
            return
        w.set_default_size(width, height)
        # X11: move to the top edge and keep above, best effort with xdotool / wmctrl
        def place():
            try:
                gi.require_version("GdkX11", "4.0")
                from gi.repository import GdkX11
                surf = w.get_surface()
                if not isinstance(surf, GdkX11.X11Surface):
                    return False
                xid = str(surf.get_xid())
                x0, y0 = (geo.x, geo.y) if geo else (0, 0)
                if shutil.which("xdotool"):
                    subprocess.Popen(["xdotool", "windowmove", xid, str(x0), str(y0),
                                      "windowsize", xid, str(width), str(height)])
                if shutil.which("wmctrl"):
                    subprocess.Popen(["wmctrl", "-i", "-r", xid, "-b", "add,above,skip_taskbar,skip_pager"])
            except (ValueError, ImportError, OSError):
                pass
            return False
        GLib.timeout_add(80, place)


def main(argv=None):
    app = App()
    return app.run(argv if argv is not None else sys.argv)

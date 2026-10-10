"""One terminal pane: a VTE terminal on a transparent background, its scrollbar, the search bar,
the "process exited" banner, link handling, safe paste, activity / finished-command tracking."""
import os, re, shlex, time, pwd, unicodedata

from gi.repository import Gtk, Gdk, Gio, GLib, Pango, Vte

from . import themes, icons

PCRE2_CASELESS = 0x00000008
PCRE2_MULTILINE = 0x00000400

URL_RE = r"(?:(?:https?|ftp|file|ssh|git)://|www\.|mailto:)[^\s<>\"'`()\[\]{}]*[^\s<>\"'`()\[\]{}.,;:!?]"
FILELINE_RE = r"(?:~|\.{1,2})?/?(?:[\w.@+-]+/)*[\w@+-][\w.@+-]*\.[A-Za-z0-9]{1,10}:\d+(?::\d+)?"
PATH_RE = r"(?<![\w/])(?:~|\.{1,2})?/(?:[\w.@+-]+/)*[\w.@+-]+/?"

CURSOR = {"block": Vte.CursorShape.BLOCK, "ibeam": Vte.CursorShape.IBEAM, "underline": Vte.CursorShape.UNDERLINE}
BLINK = {"system": Vte.CursorBlinkMode.SYSTEM, "on": Vte.CursorBlinkMode.ON, "off": Vte.CursorBlinkMode.OFF}


def rgba(h, alpha=1.0):
    c = Gdk.RGBA()
    c.parse(h)
    c.alpha = alpha
    return c


def user_shell():
    sh = os.environ.get("SHELL")
    if not sh:
        try:
            sh = pwd.getpwuid(os.getuid()).pw_shell
        except KeyError:
            sh = None
    return sh if sh and os.path.exists(sh) else "/bin/sh"


_FAMILIES = None
FALLBACK_FONTS = ["JetBrains Mono", "Fira Code", "Cascadia Code", "Iosevka", "Hack", "Source Code Pro",
                  "Ubuntu Mono", "DejaVu Sans Mono", "Noto Sans Mono", "Liberation Mono", "Monospace"]


def monospace_families():
    global _FAMILIES
    if _FAMILIES is None:
        try:
            from gi.repository import PangoCairo
            fams = PangoCairo.FontMap.get_default().list_families()
            _FAMILIES = {f.get_name().lower(): f.is_monospace() for f in fams}
        except Exception:
            _FAMILIES = {}
    return _FAMILIES


def resolve_font(spec):
    """Pango description for `spec`, swapping a missing family for the first installed monospace one."""
    fd = Pango.FontDescription.from_string(spec or "Monospace 12")
    fams = monospace_families()
    fam = (fd.get_family() or "").lower()
    if fams and fam not in fams and fam not in ("monospace", "mono"):
        for f in FALLBACK_FONTS:
            if f.lower() in fams or f == "Monospace":
                fd.set_family(f)
                break
    if fd.get_size() <= 0:
        fd.set_size(12 * Pango.SCALE)
    return fd


def cell_width(ch):
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


class Pane(Gtk.Overlay):
    def __init__(self, win, profile=None, cwd=None, argv=None, title=None):
        super().__init__()
        self.win = win
        self.s = win.s
        self.profile_name = (profile or {}).get("name") or self.s["default_profile"]
        self.profile = profile or self.s.profile(self.profile_name)
        self.add_css_class("istl-pane")
        self.custom_title = title or ""
        self.term_title = ""
        self.proc_name = ""
        self.cwd = cwd or self.profile.get("cwd") or os.path.expanduser("~")
        if self.cwd.startswith("~"):
            self.cwd = os.path.expanduser(self.cwd)
        if not os.path.isdir(self.cwd):
            self.cwd = os.path.expanduser("~")
        self.child_pid = -1
        self.born = time.monotonic()
        self.exited = False
        self.busy_since = None
        self.busy_name = ""
        self.font_scale = 1.0
        self.prompt_rows = []
        self.ctx_link = None
        self.argv_override = argv

        self.term = t = Vte.Terminal()
        t.set_hexpand(True)
        t.set_vexpand(True)
        t.set_clear_background(False)
        t.set_allow_hyperlink(True)
        t.set_mouse_autohide(True)
        # (scroll_unit_is_pixels stays off: row maths for quick select / prompt jumps needs line units)
        for name, val in (("set_enable_sixel", True), ("set_enable_fallback_scrolling", True)):
            if hasattr(t, name):
                try:
                    getattr(t, name)(val)
                except Exception:
                    pass
        self.sb = Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL, adjustment=t.get_vadjustment())
        self.sb.add_css_class("istl")
        box = Gtk.Box()
        box.append(t)
        box.append(self.sb)
        self.set_child(box)

        self.tags = {}
        for kind, pat in (("url", URL_RE), ("fileline", FILELINE_RE), ("path", PATH_RE)):
            try:
                rx = Vte.Regex.new_for_match(pat, -1, PCRE2_MULTILINE)
                tag = t.match_add_regex(rx, 0)
                t.match_set_cursor_name(tag, "pointer")
                self.tags[tag] = kind
            except GLib.Error as e:
                print("interstellar: bad link regex", kind, e)

        self._build_search()
        self.banner = None

        t.connect("window-title-changed", self._on_title)
        t.connect("current-directory-uri-changed", self._on_cwd_uri)
        t.connect("child-exited", self._on_exit)
        t.connect("bell", self._on_bell)
        t.connect("contents-changed", self._on_contents)
        t.connect("selection-changed", self._on_selection)
        t.connect("commit", self._on_commit)
        t.connect("hyperlink-hover-uri-changed", self._on_hover_link)

        fc = Gtk.EventControllerFocus()
        fc.connect("enter", lambda *_: self.win.on_pane_focus(self))
        t.add_controller(fc)

        click = Gtk.GestureClick(button=0)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_click)
        t.add_controller(click)

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        t.add_controller(drop)

        self.apply_settings()
        self.spawn()

    # ------------------------------------------------------------------ appearance
    def theme(self):
        name = self.profile.get("theme") or self.win.app.theme_name()
        return themes.get(name)

    def own_background(self):
        """True when this pane uses a different theme from the window, so it paints its own bg."""
        return bool(self.profile.get("theme")) and self.profile.get("theme") != self.win.app.theme_name()

    def apply_settings(self):
        t, s, th = self.term, self.s, self.theme()
        own = self.own_background()
        bg_alpha = float(s["opacity"]) if own else 0.0
        t.set_clear_background(own)
        pal = [rgba(c) for c in th["palette"]]
        t.set_colors(rgba(th["fg"]), rgba(th["bg"], bg_alpha), pal)
        t.set_color_cursor(rgba(s["cursor_color"] or th["cursor"]))
        t.set_color_cursor_foreground(rgba(th["bg"]))
        t.set_color_highlight(rgba(th["selection"]))
        t.set_color_highlight_foreground(None)
        t.set_color_bold(None)
        t.set_bold_is_bright(bool(s["bold_is_bright"]))
        font = self.profile.get("font") or s["font"]
        t.set_font(resolve_font(font))
        t.set_font_scale(self.font_scale)
        t.set_cell_height_scale(max(1.0, float(s["line_height"])))
        t.set_cell_width_scale(max(1.0, float(s["letter_spacing"])))
        t.set_cursor_shape(CURSOR.get(s["cursor_shape"], Vte.CursorShape.BLOCK))
        t.set_cursor_blink_mode(BLINK.get(s["cursor_blink"], Vte.CursorBlinkMode.SYSTEM))
        sb = int(s["scrollback"])
        t.set_scrollback_lines(sb if sb >= 0 else -1)
        t.set_scroll_on_output(bool(s["scroll_on_output"]))
        t.set_scroll_on_keystroke(True)
        t.set_audible_bell(s["bell"] == "audible")
        t.set_word_char_exceptions(s["word_chars"] or "-,./?%&#:_=+@~")
        self.sb.set_visible(sb != 0)
        if self.own_background():
            self.add_css_class("own-bg")
        else:
            self.remove_css_class("own-bg")

    def zoom(self, delta):
        self.font_scale = 1.0 if delta == 0 else max(0.4, min(4.0, self.font_scale + delta))
        self.term.set_font_scale(self.font_scale)

    # ------------------------------------------------------------------ process
    def build_argv(self):
        if self.argv_override:
            return list(self.argv_override)
        cmd = (self.profile.get("command") or "").strip()
        if cmd:
            try:
                return shlex.split(cmd)
            except ValueError:
                return [user_shell(), "-c", cmd]
        return [user_shell()]

    def build_env(self):
        env = dict(os.environ)
        for k in ("VTE_VERSION", "TERM_PROGRAM_VERSION", "COLUMNS", "LINES", "DESKTOP_STARTUP_ID"):
            env.pop(k, None)
        from . import VERSION
        env.update({"TERM": "xterm-256color", "COLORTERM": "truecolor", "TERM_PROGRAM": "Interstellar",
                    "TERM_PROGRAM_VERSION": VERSION, "INTERSTELLAR": "1"})
        for k, v in (self.profile.get("env") or {}).items():
            env[str(k)] = str(v)
        return [f"{k}={v}" for k, v in env.items()]

    def spawn(self):
        self.exited = False
        argv = self.build_argv()
        try:
            self.term.spawn_async(Vte.PtyFlags.DEFAULT, self.cwd, argv, self.build_env(),
                                  GLib.SpawnFlags.SEARCH_PATH, None, None, -1, None, self._spawned, None)
        except Exception as e:  # very old bindings
            self.term.feed(f"\r\n\x1b[31mInterstellar could not start {argv[0]}: {e}\x1b[0m\r\n".encode())

    def _spawned(self, term, pid, error, *_):
        if error is not None or pid < 0:
            msg = error.message if error else "unknown error"
            term.feed(f"\r\n\x1b[1;31m  ✖  could not start “{' '.join(self.build_argv())}”\x1b[0m\r\n"
                      f"     {msg}\r\n\r\n     Fix the command in Preferences → Profiles.\r\n".encode())
            return
        self.child_pid = pid

    def fg_pgrp(self):
        pty = self.term.get_pty()
        if pty is None:
            return -1
        try:
            return os.tcgetpgrp(pty.get_fd())
        except OSError:
            return -1

    def poll(self):
        """Called once a second: refresh cwd + foreground process; detect finished long commands."""
        if self.exited or self.child_pid < 0:
            return
        fg = self.fg_pgrp()
        pid = fg if fg > 0 else self.child_pid
        try:
            self.cwd = os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            pass
        name = ""
        try:
            with open(f"/proc/{pid}/comm") as f:
                name = f.read().strip()
        except OSError:
            pass
        changed = name != self.proc_name
        self.proc_name = name
        running = fg > 0 and fg != self.child_pid
        if running and self.busy_since is None:
            self.busy_since, self.busy_name = time.monotonic(), name
        elif not running and self.busy_since is not None:
            took = time.monotonic() - self.busy_since
            self.busy_since = None
            if took >= 8:
                self.win.on_command_finished(self, self.busy_name, took)
        if changed:
            self.win.on_pane_title(self)

    def running_command(self):
        fg = self.fg_pgrp()
        return fg > 0 and fg != self.child_pid and not self.exited

    def title(self):
        if self.custom_title:
            return self.custom_title
        if self.running_command() and self.proc_name:
            return self.proc_name
        if self.term_title:
            return self.term_title
        home = os.path.expanduser("~")
        c = self.cwd
        return "~" + c[len(home):] if c.startswith(home) else (c or self.proc_name or "shell")

    # ------------------------------------------------------------------ signals
    def _on_title(self, t):
        try:
            self.term_title = t.get_window_title() or ""
        except Exception:
            self.term_title = ""
        self.win.on_pane_title(self)

    def _on_cwd_uri(self, t):
        uri = t.get_current_directory_uri()
        if uri:
            try:
                self.cwd = GLib.filename_from_uri(uri)[0]
            except GLib.Error:
                pass

    def _on_exit(self, t, status):
        self.exited = True
        code = os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else status >> 8
        if code == 0 or self.argv_override is None and code in (130,):
            GLib.idle_add(self._close_later)
            return
        self.show_banner(f"Process exited with code {code}")

    def _close_later(self):
        self.win.close_pane(self, force=True)
        return False

    def show_banner(self, text):
        if self.banner:
            self.remove_overlay(self.banner)
        b = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=18)
        b.add_css_class("istl-banner")
        b.append(Gtk.Label(label=text))
        rb = Gtk.Button(label="Restart")
        rb.connect("clicked", lambda *_: self.restart())
        cb = Gtk.Button(label="Close")
        cb.connect("clicked", lambda *_: self.win.close_pane(self, force=True))
        b.append(rb)
        b.append(cb)
        self.banner = b
        self.add_overlay(b)

    def restart(self):
        if self.banner:
            self.remove_overlay(self.banner)
            self.banner = None
        self.term.reset(True, True)
        self.spawn()
        self.term.grab_focus()

    def _on_bell(self, t):
        if self.s["bell"] == "visual":
            self.add_css_class("flash")
            GLib.timeout_add(140, lambda: (self.remove_css_class("flash"), False)[1])
        self.win.on_pane_activity(self, "bell")

    def _on_contents(self, t):
        if time.monotonic() - self.born > 2.0:
            self.win.on_pane_activity(self, "output")

    def _on_selection(self, t):
        if self.s["copy_on_select"] and t.get_has_selection():
            t.copy_clipboard_format(Vte.Format.TEXT)

    def _on_commit(self, t, text, size):
        if "\r" in text:
            try:
                col, row = t.get_cursor_position()
                if not self.prompt_rows or self.prompt_rows[-1] != row:
                    self.prompt_rows.append(row)
                    del self.prompt_rows[:-500]
            except Exception:
                pass
        self.win.on_pane_commit(self, text)

    def _on_hover_link(self, t, uri, bbox):
        self.win.show_status(uri or "")

    # ------------------------------------------------------------------ links
    def link_at(self, x, y):
        t = self.term
        try:
            uri = t.check_hyperlink_at(x, y)
        except Exception:
            uri = None
        if uri:
            return ("url", uri)
        m, tag = t.check_match_at(x, y)
        if m:
            return (self.tags.get(tag, "url"), m)
        return None

    def _on_click(self, g, n, x, y):
        btn = g.get_current_button()
        if btn == 3:
            self.term.grab_focus()
            self.ctx_link = self.link_at(x, y)
            self.win.update_context_menu(self)
            return
        if btn != 1 or n != 1:
            return
        state = g.get_current_event_state()
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if self.s["link_click"] == "ctrl" and not ctrl:
            return
        link = self.link_at(x, y)
        if link:
            g.set_state(Gtk.EventSequenceState.CLAIMED)
            self.open_link(link)

    def resolve_path(self, text):
        path, line, col = text, None, None
        m = re.match(r"^(.*?):(\d+)(?::(\d+))?$", text)
        if m:
            path, line, col = m.group(1), int(m.group(2)), m.group(3) and int(m.group(3))
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.join(self.cwd, path)
        return os.path.normpath(path), line, col

    def open_link(self, link):
        kind, text = link
        if kind == "url":
            if text.startswith("www."):
                text = "https://" + text
            if text.startswith("file://"):
                try:
                    return self.open_file(GLib.filename_from_uri(text)[0], None)
                except GLib.Error:
                    pass
            Gtk.UriLauncher.new(text).launch(self.win, None, None, None)
            return
        path, line, col = self.resolve_path(text)
        if not os.path.exists(path):
            self.win.toast(f"Not found: {path}")
            return
        self.open_file(path, line)

    def open_file(self, path, line):
        if os.path.isdir(path):
            Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self.win, None, None, None)
            return
        cmd = self.s["editor_command"].strip()
        if cmd:
            line_s = str(line or 1)
            argv = [a.replace("{file}", path).replace("{line}", line_s) for a in shlex.split(cmd)]
            if "{file}" not in cmd:
                argv.append(path)
            try:
                Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
            except GLib.Error as e:
                self.win.toast(f"Editor failed: {e.message}")
            return
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if editor:
            argv = shlex.split(editor) + ([f"+{line}"] if line else []) + [path]
            self.win.new_tab(cwd=os.path.dirname(path), argv=argv, title=os.path.basename(path))
            return
        Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self.win, None, None, None)

    # ------------------------------------------------------------------ clipboard
    def copy(self):
        if self.term.get_has_selection():
            self.term.copy_clipboard_format(Vte.Format.TEXT)
            return True
        return False

    def paste(self):
        cb = self.get_clipboard()
        cb.read_text_async(None, self._got_paste)

    def _got_paste(self, cb, res):
        try:
            text = cb.read_text_finish(res)
        except GLib.Error:
            text = None
        if text:
            self.paste_text(text)

    def paste_text(self, text):
        lines = text.rstrip("\n").count("\n") + 1
        risky = lines > 1 or re.search(r"\b(sudo|rm\s+-rf|mkfs|dd\s+if=|curl[^|]*\|\s*(ba)?sh)\b", text)
        if self.s["safe_paste"] and risky and not self.running_command():
            self.win.confirm_paste(self, text, lines)
        else:
            self.term.paste_text(text)

    def _on_drop(self, target, value, x, y):
        files = value.get_files() if hasattr(value, "get_files") else []
        paths = [shlex.quote(f.get_path()) for f in files if f.get_path()]
        if paths:
            self.term.paste_text(" ".join(paths) + " ")
            self.term.grab_focus()
            return True
        return False

    # ------------------------------------------------------------------ text helpers
    def visible_rows(self):
        """[(screen_row, text)] for the rows on screen, soft-wrapped lines split into their rows."""
        t = self.term
        cols = max(1, t.get_column_count())
        nrows = t.get_row_count()
        if hasattr(t, "get_text_format"):
            txt = t.get_text_format(Vte.Format.TEXT) or ""
            out = []
            for line in txt.split("\n"):
                row, width = "", 0
                for ch in line:
                    w = cell_width(ch)
                    if width + w > cols:
                        out.append(row)
                        row, width = "", 0
                    row += ch
                    width += w
                out.append(row)
                if len(out) >= nrows:
                    break
            return list(enumerate(out[:nrows])), 0
        top = int(round(t.get_vadjustment().get_value()))
        out = []
        for r in range(top, top + nrows):
            txt, _ = t.get_text_range_format(Vte.Format.TEXT, r, 0, r, cols)
            out.append((r - top, (txt or "").rstrip("\n")))
        return out, 0

    def all_text(self):
        t = self.term
        adj = t.get_vadjustment()
        txt, _ = t.get_text_range_format(Vte.Format.TEXT, int(adj.get_lower()), 0,
                                         int(adj.get_upper()), t.get_column_count())
        return txt or ""

    def jump_prompt(self, direction):
        adj = self.term.get_vadjustment()
        cur = adj.get_value()
        rows = [r for r in self.prompt_rows if r >= adj.get_lower()]
        if direction < 0:
            cand = [r for r in rows if r < cur - 0.5]
            if cand:
                adj.set_value(cand[-1])
        else:
            cand = [r for r in rows if r > cur + 0.5]
            adj.set_value(cand[0] if cand else adj.get_upper() - adj.get_page_size())

    def clear(self):
        self.term.reset(False, True)
        self.term.feed_child(b"\x0c")

    # ------------------------------------------------------------------ search
    def _build_search(self):
        rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                           halign=Gtk.Align.FILL, valign=Gtk.Align.START, margin_top=8, margin_end=18, margin_start=8)
        box = Gtk.Box(spacing=2, halign=Gtk.Align.END)
        box.add_css_class("istl-float")
        self.s_entry = Gtk.SearchEntry(placeholder_text="Find", width_chars=14, max_width_chars=24)
        self.s_case = Gtk.ToggleButton(label="Aa", tooltip_text="Match case")
        self.s_regex = Gtk.ToggleButton(label=".*", tooltip_text="Regular expression")
        self.s_count = Gtk.Label(css_classes=["dim"], ellipsize=3, max_width_chars=10)
        prev = icons.button("up", "Previous (Shift+Enter)")
        nxt = icons.button("down", "Next (Enter)")
        close = icons.button("close", "Close (Esc)", 14)
        for w in (self.s_entry, self.s_case, self.s_regex, self.s_count, prev, nxt, close):
            box.append(w)
        rev.set_child(box)
        self.search_rev = rev
        self.add_overlay(rev)
        self.s_entry.connect("search-changed", lambda *_: self._search_update())
        self.s_case.connect("toggled", lambda *_: self._search_update())
        self.s_regex.connect("toggled", lambda *_: self._search_update())
        self.s_entry.connect("activate", lambda *_: self.search_step(1))
        self.s_entry.connect("stop-search", lambda *_: self.hide_search())
        prev.connect("clicked", lambda *_: self.search_step(-1))
        nxt.connect("clicked", lambda *_: self.search_step(1))
        close.connect("clicked", lambda *_: self.hide_search())
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", self._search_key)
        self.s_entry.add_controller(kc)

    def _search_key(self, c, keyval, code, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and state & Gdk.ModifierType.SHIFT_MASK:
            self.search_step(-1)
            return True
        if keyval == Gdk.KEY_Escape:
            self.hide_search()
            return True
        return False

    def show_search(self):
        self.search_rev.set_reveal_child(True)
        if self.term.get_has_selection():
            sel = self.term.get_text_selected_full(Vte.Format.TEXT)[0] if hasattr(self.term, "get_text_selected_full") else ""
            if sel and "\n" not in sel:
                self.s_entry.set_text(sel)
        self.s_entry.grab_focus()
        self.s_entry.select_region(0, -1)

    def hide_search(self):
        self.search_rev.set_reveal_child(False)
        self.term.search_set_regex(None, 0)
        self.term.unselect_all()
        self.term.grab_focus()

    def _search_update(self):
        text = self.s_entry.get_text()
        if not text:
            self.term.search_set_regex(None, 0)
            self.s_count.set_text("")
            return
        pat = text if self.s_regex.get_active() else re.escape(text)
        flags = PCRE2_MULTILINE | (0 if self.s_case.get_active() else PCRE2_CASELESS)
        try:
            rx = Vte.Regex.new_for_search(pat, -1, flags)
        except GLib.Error:
            self.s_count.set_text("bad regex")
            return
        self.term.search_set_regex(rx, 0)
        self.term.search_set_wrap_around(True)
        try:
            flags_py = 0 if self.s_case.get_active() else re.I
            n = len(re.findall(text if self.s_regex.get_active() else re.escape(text), self.all_text(), flags_py))
            self.s_count.set_text(f"{n} found" if n else "no results")
        except re.error:
            self.s_count.set_text("")
        self.term.unselect_all()
        self.term.search_find_previous()

    def search_step(self, d):
        if d > 0:
            self.term.search_find_next()
        else:
            self.term.search_find_previous()

    # ------------------------------------------------------------------ session
    def state(self):
        return {"cwd": self.cwd, "profile": self.profile_name, "title": self.custom_title}

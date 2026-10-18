"""Preferences: every option has a GUI control and applies live to all open windows.

Pages: Themes (gallery, hover to preview) · Theme Studio (edit / import / export) · Text & Cursor ·
Space & Window (starfield, background image, opacity, UI style) · Liquid Glass (blur, refraction, light…) · Tabs · Behaviour · Profiles · Keys · Advanced
"""
import copy, json, math, os, random

import cairo
from gi.repository import Gtk, Gdk, Gio, GLib, Pango

from . import themes, keys, icons, liquid, NAME, VERSION
from .chrome import _rgb
from .pane import FALLBACK_FONTS
from .settings import CFG_DIR, CFG_FILE, DEFAULTS

PAGES = [
    ("themes", "Themes", "planet"),
    ("studio", "Theme Studio", "brush"),
    ("text", "Text & Cursor", "prompt"),
    ("space", "Space & Window", "sparkle"),
    ("glass", "Liquid Glass", "glass"),
    ("tabs", "Tabs", "tab"),
    ("behaviour", "Behaviour", "bolt"),
    ("profiles", "Profiles", "profile"),
    ("keys", "Keyboard", "keyboard"),
    ("advanced", "Advanced", "code"),
]


def rgb(h):
    return [c / 255 for c in _rgb(h)]


def draw_theme_preview(cr, w, h, th, radius=10, stars=True):
    """A miniature terminal in the theme's colours."""
    cr.save()
    cr.new_sub_path()
    r = radius
    cr.arc(w - r, r, r, -math.pi / 2, 0); cr.arc(w - r, h - r, r, 0, math.pi / 2)
    cr.arc(r, h - r, r, math.pi / 2, math.pi); cr.arc(r, r, r, math.pi, 1.5 * math.pi)
    cr.close_path()
    cr.clip()
    if th.get("liquid"):
        _draw_glass_tile(cr, w, h, th, r)
    else:
        cr.set_source_rgb(*rgb(th["bg"]))
        cr.paint()
    if stars and th.get("space"):
        rnd = random.Random(th["name"])
        ar = rgb(th["accent"])
        g = cairo.RadialGradient(w * 0.85, h * 0.1, 0, w * 0.85, h * 0.1, w * 0.7)
        g.add_color_stop_rgba(0, *ar, 0.18)
        g.add_color_stop_rgba(1, *ar, 0)
        cr.set_source(g)
        cr.paint()
        for _ in range(26):
            cr.set_source_rgba(1, 1, 1, rnd.uniform(0.2, 0.8))
            cr.arc(rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(0.4, 1.1), 0, math.tau)
            cr.fill()
    pal = th["palette"]
    # bar
    cr.set_source_rgba(*rgb(th["fg"]), 0.06)
    cr.rectangle(0, 0, w, 14)
    cr.fill()
    for i, c in enumerate((pal[1], pal[3], pal[2])):
        cr.set_source_rgb(*rgb(c))
        cr.arc(10 + i * 9, 7, 2.6, 0, math.tau)
        cr.fill()
    lines = [
        [(pal[2], 18), (th["fg"], 6), (pal[4], 22), (th["fg"], 30)],
        [(pal[4], 14), (pal[4], 12), (th["fg"], 20), (pal[5], 16)],
        [(pal[1], 10), (th["fg"], 36), (pal[3], 18)],
        [(pal[6], 24), (pal[2], 12), (th["fg"], 26)],
        [(pal[2], 18), (th["fg"], 6), (th["cursor"], 6)],
    ]
    y = 22
    lh = max(8, (h - 26) / 6)
    for line in lines:
        x = 10
        for col, ln in line:
            ln = ln * w / 170
            cr.set_source_rgb(*rgb(col))
            cr.rectangle(x, y, ln, lh * 0.42)
            cr.fill()
            x += ln + 4
        y += lh
    # palette strip
    sw = (w - 20) / 8
    for i in range(8):
        cr.set_source_rgb(*rgb(pal[i + 8]))
        cr.rectangle(10 + i * sw, h - 10, sw, 4)
        cr.fill()
    cr.restore()


def _draw_glass_tile(cr, w, h, th, r):
    """Liquid themes: a glass pane over a colourful backdrop."""
    pal = th["palette"]
    dark = themes.luminance(th["bg"]) < 0.5
    cr.set_source_rgb(*[c * (0.55 if dark else 1.0) for c in rgb(th["bg"])])
    cr.paint()
    for x, y, rad, col in ((0.15, 0.2, 0.7, th["accent"]), (0.9, 0.25, 0.6, pal[5]), (0.6, 1.0, 0.7, pal[6])):
        g = cairo.RadialGradient(x * w, y * h, 0, x * w, y * h, rad * w)
        g.add_color_stop_rgba(0, *rgb(col), 0.75 if dark else 0.4)
        g.add_color_stop_rgba(1, *rgb(col), 0)
        cr.set_source(g)
        cr.paint()
    inset = 3
    cr.new_sub_path()
    rr = max(r - inset, 2)
    x0, y0, x1, y1 = inset, inset, w - inset, h - inset
    cr.arc(x1 - rr, y0 + rr, rr, -math.pi / 2, 0); cr.arc(x1 - rr, y1 - rr, rr, 0, math.pi / 2)
    cr.arc(x0 + rr, y1 - rr, rr, math.pi / 2, math.pi); cr.arc(x0 + rr, y0 + rr, rr, math.pi, 1.5 * math.pi)
    cr.close_path()
    cr.set_source_rgba(*rgb(th["bg"]), 0.42)
    cr.fill_preserve()
    g = cairo.LinearGradient(0, 0, w, h)
    g.add_color_stop_rgba(0, 1, 1, 1, 0.75)
    g.add_color_stop_rgba(0.5, 1, 1, 1, 0.12)
    g.add_color_stop_rgba(1, 1, 1, 1, 0.45)
    cr.set_source(g)
    cr.set_line_width(1.2)
    cr.stroke()


GLASS_PRESETS = [
    ("crystal", "Crystal", {"glass_frost": 0.12, "glass_refraction": 1.7, "glass_edge": 32, "glass_dispersion": 1.8,
                            "glass_tint": 0.32, "glass_vibrancy": 1.45, "glass_rim": 1.0, "glass_lens": 0.45}),
    ("liquid", "Liquid", {k: liquid.GLASS_DEFAULTS[k] for k in ("glass_frost", "glass_refraction", "glass_edge",
                                                                "glass_dispersion", "glass_tint", "glass_vibrancy",
                                                                "glass_rim", "glass_lens")}),
    ("frosted", "Frosted", {"glass_frost": 0.9, "glass_refraction": 0.6, "glass_edge": 22, "glass_dispersion": 0.5,
                            "glass_tint": 0.55, "glass_vibrancy": 1.1, "glass_rim": 0.5, "glass_lens": 0.1}),
    ("smoked", "Smoked", {"glass_frost": 0.7, "glass_refraction": 1.0, "glass_edge": 26, "glass_dispersion": 0.8,
                          "glass_tint": 0.78, "glass_vibrancy": 0.9, "glass_rim": 0.6, "glass_lens": 0.2}),
]


class Prefs(Gtk.Window):
    def __init__(self, app):
        super().__init__(title=f"{NAME} Preferences", default_width=980, default_height=680)
        self.app = app
        self.s = app.s
        self.add_css_class("istl-prefs")
        hb = Gtk.HeaderBar()
        self.set_titlebar(hb)
        self.search = Gtk.SearchEntry(placeholder_text="Search settings…", width_chars=24)
        hb.pack_start(self.search)
        reset = Gtk.Button(label="Reset all")
        reset.add_css_class("flat")
        reset.connect("clicked", lambda *_: self._confirm_reset())
        hb.pack_end(reset)

        root = Gtk.Box()
        self.set_child(root)
        self.side = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, width_request=210)
        self.side.add_css_class("prefs-side")
        self.side.add_css_class("navigation-sidebar")
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        sw.set_child(self.side)
        root.append(sw)
        root.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.stack = Gtk.Stack(hexpand=True, vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        root.append(self.stack)
        self.rows_index = []   # (page, row widget, searchable text)
        self.builders = {}
        for pid, title, icon in PAGES:
            r = Gtk.ListBoxRow()
            r.pid = pid
            b = Gtk.Box(spacing=10)
            b.append(icons.Icon(icon, 18))
            b.append(Gtk.Label(label=title, xalign=0))
            r.set_child(b)
            self.side.append(r)
        self.side.connect("row-selected", self._on_side)
        self.search.connect("search-changed", self._on_search)
        self.reload()
        self.side.select_row(self.side.get_row_at_index(0))

    # ------------------------------------------------------------------ scaffolding
    def reload(self):
        cur = self.stack.get_visible_child_name()
        for c in list(self._children(self.stack)):
            self.stack.remove(c)
        self.rows_index = []
        for pid, title, _ in PAGES:
            page = getattr(self, f"_page_{pid}")()
            self.stack.add_named(page, pid)
        if cur:
            self.stack.set_visible_child_name(cur)

    @staticmethod
    def _children(w):
        c = w.get_first_child()
        while c:
            n = c.get_next_sibling()
            yield c
            c = n

    def show_page(self, pid):
        for i, (p, _, _) in enumerate(PAGES):
            if p == pid:
                self.side.select_row(self.side.get_row_at_index(i))

    def _on_side(self, lb, row):
        if row:
            self.stack.set_visible_child_name(row.pid)

    def _on_search(self, e):
        q = e.get_text().strip().lower()
        for page, row, text in self.rows_index:
            row.set_visible(not q or q in text)
        if q:
            for page, row, text in self.rows_index:
                if q in text:
                    self.show_page(page)
                    break

    def _page(self, title, sub):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_start=28, margin_end=28,
                      margin_top=22, margin_bottom=28)
        t = Gtk.Label(label=title, xalign=0)
        t.add_css_class("prefs-title")
        box.append(t)
        st = Gtk.Label(label=sub, xalign=0, wrap=True)
        st.add_css_class("prefs-sub")
        box.append(st)
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        clamp.append(box)
        sw.set_child(clamp)
        sw.content = box
        return sw

    def _group(self, page_sw, title):
        lbl = Gtk.Label(label=title.upper(), xalign=0)
        lbl.add_css_class("prefs-group")
        page_sw.content.append(lbl)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("prefs-card")
        page_sw.content.append(card)
        return card

    def _row(self, card, page, title, desc, widget):
        row = Gtk.Box(spacing=14)
        row.add_css_class("prefs-row")
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        txt.append(Gtk.Label(label=title, xalign=0, wrap=True))
        if desc:
            d = Gtk.Label(label=desc, xalign=0, wrap=True)
            d.add_css_class("desc")
            txt.append(d)
        row.append(txt)
        if widget is not None:
            widget.set_valign(Gtk.Align.CENTER)
            row.append(widget)
        card.append(row)
        self.rows_index.append((page, row, f"{title} {desc}".lower()))
        return row

    # widgets bound to settings ------------------------------------------------
    def _switch(self, key):
        sw = Gtk.Switch(active=bool(self.s[key]))
        sw.connect("notify::active", lambda w, _p: self.s.__setitem__(key, w.get_active()))
        return sw

    def _choice(self, key, options):
        """options: [(value, label)]"""
        dd = Gtk.DropDown.new_from_strings([l for _, l in options])
        vals = [v for v, _ in options]
        if self.s[key] in vals:
            dd.set_selected(vals.index(self.s[key]))
        dd.connect("notify::selected", lambda d, _p: self.s.__setitem__(key, vals[d.get_selected()]))
        return dd

    def _segmented(self, key, options):
        box = Gtk.Box(css_classes=["linked"])
        first = None
        for v, label in options:
            b = Gtk.ToggleButton(label=label, active=self.s[key] == v)
            if first:
                b.set_group(first)
            else:
                first = b
            b.connect("toggled", lambda btn, val=v: btn.get_active() and self.s.__setitem__(key, val))
            box.append(b)
        return box

    def _scale(self, key, lo, hi, step, digits=2, fmt=None, width=220):
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        sc.set_value(float(self.s[key]))
        sc.set_digits(digits)
        sc.set_draw_value(True)
        sc.set_value_pos(Gtk.PositionType.LEFT)
        sc.set_size_request(width, -1)
        if fmt:
            sc.set_format_value_func(lambda s_, v: fmt(v))
        pending = {"id": 0}

        def changed(w):
            v = round(w.get_value(), digits) if digits else int(w.get_value())
            if pending["id"]:
                GLib.source_remove(pending["id"])
            pending["id"] = GLib.timeout_add(60, lambda: (self.s.__setitem__(key, v), pending.__setitem__("id", 0), False)[2])
        sc.connect("value-changed", changed)
        return sc

    def _spin(self, key, lo, hi, step=1):
        sp = Gtk.SpinButton.new_with_range(lo, hi, step)
        sp.set_value(int(self.s[key]))
        sp.connect("value-changed", lambda w: self.s.__setitem__(key, int(w.get_value())))
        return sp

    def _entry(self, key, placeholder="", width=28):
        e = Gtk.Entry(text=str(self.s[key] or ""), placeholder_text=placeholder, width_chars=width)
        e.connect("changed", lambda w: self.s.__setitem__(key, w.get_text()))
        return e

    def _color(self, key, allow_theme=True):
        box = Gtk.Box(spacing=6)
        btn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
        c = Gdk.RGBA()
        c.parse(self.s[key] or themes.get(self.s["theme"])["cursor"])
        btn.set_rgba(c)

        def changed(b, _p):
            r = b.get_rgba()
            self.s[key] = "#%02x%02x%02x" % (round(r.red * 255), round(r.green * 255), round(r.blue * 255))
        btn.connect("notify::rgba", changed)
        box.append(btn)
        if allow_theme:
            rb = Gtk.Button(label="Theme")
            rb.add_css_class("flat")
            rb.set_tooltip_text("Use the theme's colour")
            rb.connect("clicked", lambda *_: self.s.__setitem__(key, ""))
            box.append(rb)
        return box

    # ------------------------------------------------------------------ pages
    def _page_themes(self):
        pg = self._page("Themes", "Hover a theme to preview it on your open terminals, click to keep it. "
                        "✦ marks the space originals, ◈ the Liquid Glass themes.")
        bar = Gtk.Box(spacing=8, margin_bottom=8)
        filt = Gtk.SearchEntry(placeholder_text="Filter themes", width_chars=18)
        bar.append(filt)
        kind = Gtk.DropDown.new_from_strings(["All", "✦ Space", "Dark", "Light", "Custom", "◈ Liquid Glass"])
        bar.append(kind)
        bar.append(Gtk.Box(hexpand=True))
        imp = icons.button("plus", label="Import theme…")
        imp.connect("clicked", lambda *_: self._import_theme())
        bar.append(imp)
        rnd = icons.button("sparkle", label="Surprise me")
        rnd.connect("clicked", lambda *_: self._random_theme())
        bar.append(rnd)
        pg.content.append(bar)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=2,
                           row_spacing=10, column_spacing=10, homogeneous=True)
        pg.content.append(flow)
        tiles = []
        for th in themes.all_themes():
            b = Gtk.Button()
            b.add_css_class("theme-tile")
            b.add_css_class("flat")
            if th["name"] == self.s["theme"]:
                b.add_css_class("active")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            da = Gtk.DrawingArea(content_width=170, content_height=100)
            da.set_draw_func(lambda a, cr, w, h, t=th: draw_theme_preview(cr, w, h, t))
            v.append(da)
            name = ("◈ " if th.get("liquid") else "✦ " if th.get("space") else "") + th["name"]
            v.append(Gtk.Label(label=name, ellipsize=3))
            b.set_child(v)
            b.connect("clicked", lambda _b, n=th["name"]: self._pick_theme(n))
            mc = Gtk.EventControllerMotion()
            mc.connect("enter", lambda *_a, n=th["name"]: self.app.preview_theme(n))
            mc.connect("leave", lambda *_a: self.app.preview_theme(None))
            b.add_controller(mc)
            flow.append(b)
            tiles.append((b.get_parent(), th))

        def refilter(*_):
            q = filt.get_text().lower()
            k = kind.get_selected()
            for child, th in tiles:
                light = themes.luminance(th["bg"]) > 0.5
                ok = q in th["name"].lower() and (k == 0 or (k == 1 and th.get("space")) or (k == 2 and not light)
                                                   or (k == 3 and light) or (k == 4 and th.get("custom"))
                                                   or (k == 5 and th.get("liquid")))
                child.set_visible(ok)
        filt.connect("search-changed", refilter)
        kind.connect("notify::selected", refilter)
        self.rows_index.append(("themes", Gtk.Box(), "theme themes colour color scheme palette gallery"))
        return pg

    def _pick_theme(self, name):
        self.app.preview_theme(None)
        self.s["theme"] = name
        GLib.idle_add(lambda: (self.reload(), False)[1])

    def _random_theme(self):
        ts = [t["name"] for t in themes.all_themes() if t["name"] != self.s["theme"]]
        self._pick_theme(random.choice(ts))

    def _import_theme(self):
        dlg = Gtk.FileDialog(title="Import a kitty, Alacritty or base16 theme")

        def done(d, res):
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            try:
                t = themes.import_file(f.get_path())
                themes.save_custom(t)
                self._pick_theme(t["name"])
            except (OSError, ValueError) as e:
                Gtk.AlertDialog(message="Couldn't import that theme", detail=str(e)).show(self)
        dlg.open(self, None, done)

    # ---------------------------------------------------------------- studio
    def _page_studio(self):
        pg = self._page("Theme Studio", "Make your own theme. Start from any theme, tweak the colours, save it — "
                        "it shows up everywhere (palette, gallery, profiles). Custom themes live in "
                        "~/.config/interstellar/themes as JSON you can share.")
        base = copy.deepcopy(themes.get(self.s["theme"]))
        self.studio = base
        top = Gtk.Box(spacing=8, margin_bottom=10)
        top.append(Gtk.Label(label="Start from"))
        names = [t["name"] for t in themes.all_themes()]
        start = Gtk.DropDown.new_from_strings(names)
        start.set_enable_search(True)
        if base["name"] in names:
            start.set_selected(names.index(base["name"]))
        top.append(start)
        top.append(Gtk.Label(label="Name"))
        name = Gtk.Entry(text=base["name"] if base.get("custom") else base["name"] + " (mine)", hexpand=True)
        top.append(name)
        pg.content.append(top)

        preview = Gtk.DrawingArea(content_height=200, hexpand=True)
        preview.set_draw_func(lambda a, cr, w, h: self._draw_studio(cr, w, h))
        frame = Gtk.Frame()
        frame.set_child(preview)
        pg.content.append(frame)

        grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin_top=14)
        pg.content.append(grid)
        buttons = {}

        def mk(key, idx=None):
            b = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
            b.add_css_class("swatch-btn")

            def changed(btn, _p):
                r = btn.get_rgba()
                hexc = "#%02x%02x%02x" % (round(r.red * 255), round(r.green * 255), round(r.blue * 255))
                if idx is None:
                    self.studio[key] = hexc
                else:
                    self.studio["palette"][idx] = hexc
                preview.queue_draw()
            b.connect("notify::rgba", changed)
            buttons[(key, idx)] = b
            return b

        basics = [("bg", "Background"), ("fg", "Text"), ("cursor", "Cursor"), ("selection", "Selection"),
                  ("accent", "Accent (tabs, UI)")]
        for i, (k, label) in enumerate(basics):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, i, 1, 1)
            grid.attach(mk(k), 1, i, 1, 1)
        cn = ["Black", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White"]
        grid.attach(Gtk.Label(label="Normal", xalign=0, css_classes=["dim"]), 3, 0, 1, 1)
        grid.attach(Gtk.Label(label="Bright", xalign=0, css_classes=["dim"]), 5, 0, 1, 1)
        for i, n in enumerate(cn):
            r = i + 1
            grid.attach(Gtk.Label(label=n, xalign=1, margin_start=40), 2, r, 1, 1)
            grid.attach(mk("palette", i), 3, r, 1, 1)
            grid.attach(mk("palette", i + 8), 5, r, 1, 1)
        space = Gtk.CheckButton(label="Space theme (nebula glow behind the stars)", active=bool(base.get("space")))
        space.connect("toggled", lambda c: (self.studio.__setitem__("space", c.get_active()), preview.queue_draw()))
        grid.attach(space, 0, len(basics) + 1, 2, 1)

        def load(th):
            self.studio = copy.deepcopy(th)
            self.studio["palette"] = list(th["palette"])
            for (k, idx), b in buttons.items():
                c = Gdk.RGBA()
                c.parse(self.studio[k] if idx is None else self.studio["palette"][idx])
                b.set_rgba(c)
            space.set_active(bool(th.get("space")))
            name.set_text(th["name"] if th.get("custom") else th["name"] + " (mine)")
            preview.queue_draw()
        load(base)
        start.connect("notify::selected", lambda d, _p: load(themes.get(names[d.get_selected()])))

        act = Gtk.Box(spacing=8, margin_top=16)
        save = Gtk.Button(label="Save & use theme")
        save.add_css_class("suggested-action")

        def do_save(*_):
            t = dict(self.studio)
            t["name"] = name.get_text().strip() or "My Theme"
            themes.save_custom(t)
            self._pick_theme(t["name"])
        save.connect("clicked", do_save)
        try_ = Gtk.Button(label="Try on terminals")
        try_.connect("clicked", lambda *_: self._try_studio(name.get_text()))
        exp = Gtk.Button(label="Export…")
        exp.connect("clicked", lambda *_: self._export_theme(name.get_text()))
        imp = Gtk.Button(label="Import…")
        imp.connect("clicked", lambda *_: self._import_theme())
        inv = Gtk.Button(label="Swap light / dark")
        inv.set_tooltip_text("Swap background and text colours")

        def swap(*_):
            t = self.studio
            t["bg"], t["fg"] = t["fg"], t["bg"]
            load(dict(t, name=name.get_text().replace(" (mine)", "")))
        inv.connect("clicked", swap)
        for b in (save, try_, inv, imp, exp):
            act.append(b)
        pg.content.append(act)
        self.rows_index.append(("studio", Gtk.Box(), "theme studio editor custom colours colors import export kitty alacritty base16"))
        return pg

    def _draw_studio(self, cr, w, h):
        t = self.studio
        cr.set_source_rgb(*rgb(t["bg"]))
        cr.paint()
        if t.get("space"):
            ar = rgb(t["accent"])
            g = cairo.RadialGradient(w * 0.85, 0, 0, w * 0.85, 0, w * 0.6)
            g.add_color_stop_rgba(0, *ar, 0.16)
            g.add_color_stop_rgba(1, *ar, 0)
            cr.set_source(g)
            cr.paint()
            rnd = random.Random(3)
            for _ in range(60):
                cr.set_source_rgba(1, 1, 1, rnd.uniform(0.15, 0.7))
                cr.arc(rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(0.4, 1.2), 0, math.tau)
                cr.fill()
        P = t["palette"]
        lines = [
            [(P[2], "you@starship"), (t["fg"], ":"), (P[4], "~/orbit"), (t["fg"], "$ ls --color")],
            [(P[4], "src/  "), (P[2], "launch.sh*  "), (t["fg"], "README.md  "), (P[5], "logo.png  "), (P[6], "link@")],
            [(P[2], "you@starship"), (t["fg"], ":"), (P[4], "~/orbit"), (t["fg"], "$ git diff --stat")],
            [(t["fg"], " engine.c | 12 "), (P[2], "++++++++"), (P[1], "----")],
            [(P[3], "warning: "), (t["fg"], "fuel low  "), (P[1], "error: "), (t["fg"], "oxygen 12%")],
            [(P[8], "bright: "), (P[9], "red "), (P[10], "green "), (P[11], "yellow "), (P[12], "blue "),
             (P[13], "magenta "), (P[14], "cyan "), (P[15], "white")],
        ]
        layout = Pango.Layout.new(self.get_pango_context())
        layout.set_font_description(Pango.FontDescription.from_string("Monospace 11"))
        from gi.repository import PangoCairo
        y = 14
        for i, line in enumerate(lines):
            x = 16
            for col, text in line:
                layout.set_text(text, -1)
                cr.set_source_rgb(*rgb(col))
                cr.move_to(x, y)
                PangoCairo.show_layout(cr, layout)
                x += layout.get_pixel_size()[0]
            y += 24
        layout.set_text("$ ", -1)
        cr.set_source_rgb(*rgb(t["fg"]))
        cr.move_to(16, y)
        PangoCairo.show_layout(cr, layout)
        cw, chh = layout.get_pixel_size()
        cr.set_source_rgb(*rgb(t["selection"]))
        cr.rectangle(16 + cw, y, 150, chh)
        cr.fill()
        layout.set_text("selected text", -1)
        cr.set_source_rgb(*rgb(t["fg"]))
        cr.move_to(16 + cw + 4, y)
        PangoCairo.show_layout(cr, layout)
        cr.set_source_rgb(*rgb(t["cursor"]))
        cr.rectangle(16 + cw + 158, y, chh * 0.55, chh)
        cr.fill()
        # accent tab sample
        cr.set_source_rgb(*rgb(t["accent"]))
        cr.rectangle(w - 120, 12, 100, 3)
        cr.fill()

    def _try_studio(self, name):
        t = dict(self.studio)
        t["name"] = (name or "My Theme").strip()
        themes.save_custom(t)
        self.app.preview_theme(t["name"])
        GLib.timeout_add(4000, lambda: (self.app.preview_theme(None), False)[1])

    def _export_theme(self, name):
        dlg = Gtk.FileDialog(title="Export theme", initial_name=(name or "theme").lower().replace(" ", "-") + ".json")

        def done(d, res):
            try:
                f = d.save_finish(res)
            except GLib.Error:
                return
            t = {k: self.studio[k] for k in ("fg", "bg", "cursor", "selection", "accent", "palette")}
            t["name"] = name
            t["space"] = bool(self.studio.get("space"))
            with open(f.get_path(), "w") as fh:
                json.dump(t, fh, indent=2)
        dlg.save(self, None, done)

    # ---------------------------------------------------------------- text
    def _page_text(self):
        pg = self._page("Text & Cursor", "Font, spacing and the cursor. Everything updates as you change it.")
        c = self._group(pg, "Font")
        lower = {f.lower() for f in FALLBACK_FONTS}
        fam_names = {}
        try:
            from gi.repository import PangoCairo
            for f in PangoCairo.FontMap.get_default().list_families():
                if f.is_monospace():
                    fam_names[f.get_name().lower()] = f.get_name()
        except Exception:
            pass
        disp = sorted(fam_names.values(), key=lambda n: (n.lower() not in lower, n.lower())) or ["Monospace"]
        fd = Pango.FontDescription.from_string(self.s["font"])
        cur_f = fd.get_family() or "Monospace"
        size = (fd.get_size() / Pango.SCALE) or 12
        if cur_f not in disp:
            disp.insert(0, cur_f)
        dd = Gtk.DropDown.new_from_strings(disp)
        dd.set_enable_search(True)
        dd.set_selected(disp.index(cur_f))
        sp = Gtk.SpinButton.new_with_range(6, 48, 1)
        sp.set_value(size)

        def font_changed(*_):
            self.s["font"] = f"{disp[dd.get_selected()]} {int(sp.get_value())}"
        dd.connect("notify::selected", font_changed)
        sp.connect("value-changed", font_changed)
        self._row(c, "text", "Font", "Monospace fonts installed on your system (missing fonts fall back automatically).", dd)
        self._row(c, "text", "Size", "Ctrl + / Ctrl − zooms a single pane.", sp)
        self._row(c, "text", "Line height", "Space between lines.", self._scale("line_height", 1.0, 1.8, 0.05))
        self._row(c, "text", "Letter spacing", "Space between characters.", self._scale("letter_spacing", 1.0, 1.4, 0.02))
        self._row(c, "text", "Bold text in bright colours", "", self._switch("bold_is_bright"))
        self._row(c, "text", "Padding", "Space between the window edge and the text, in pixels.", self._spin("padding", 0, 64))
        c = self._group(pg, "Cursor")
        self._row(c, "text", "Shape", "", self._segmented("cursor_shape", [("block", "█ Block"), ("ibeam", "│ Beam"),
                                                                         ("underline", "▁ Underline")]))
        self._row(c, "text", "Blink", "", self._segmented("cursor_blink", [("on", "On"), ("off", "Off"), ("system", "System")]))
        self._row(c, "text", "Colour", "Override the theme's cursor colour.", self._color("cursor_color"))
        return pg

    # ---------------------------------------------------------------- space
    def _page_space(self):
        pg = self._page("Space & Window", "The animated starfield, background images, transparency and the look of the window itself.")
        c = self._group(pg, "Starfield")
        self._row(c, "space", "Animated starfield", "Parallax stars drift behind your text, with the odd shooting star. "
                  "Toggle: Ctrl+Shift+F11.", self._switch("starfield"))
        self._row(c, "space", "Motion", "Still uses no CPU at all.",
                  self._segmented("starfield_motion", [("drift", "Drift"), ("twinkle", "Twinkle"), ("still", "Still")]))
        self._row(c, "space", "Star density", "", self._scale("starfield_density", 0.2, 3.0, 0.1, 1,
                                                              fmt=lambda v: f"{v:.1f}×"))
        c = self._group(pg, "Background")
        box = Gtk.Box(spacing=6)
        lbl = Gtk.Label(label=os.path.basename(self.s["background_image"]) or "None", ellipsize=3, max_width_chars=22)
        pick = Gtk.Button(label="Choose…")
        clear = Gtk.Button(label="Clear")
        clear.add_css_class("flat")
        box.append(lbl)
        box.append(pick)
        box.append(clear)

        def choose(*_):
            dlg = Gtk.FileDialog(title="Background image")
            f = Gtk.FileFilter()
            f.set_name("Images")
            f.add_pixbuf_formats()
            store = Gio.ListStore.new(Gtk.FileFilter)
            store.append(f)
            dlg.set_filters(store)

            def done(d, res):
                try:
                    fl = d.open_finish(res)
                except GLib.Error:
                    return
                self.s["background_image"] = fl.get_path()
                lbl.set_text(os.path.basename(fl.get_path()))
            dlg.open(self, None, done)
        pick.connect("clicked", choose)
        clear.connect("clicked", lambda *_: (self.s.__setitem__("background_image", ""), lbl.set_text("None")))
        self._row(c, "space", "Background image", "Any picture — wallpapers, a nebula photo, your cat. Replaces the nebula glow.", box)
        self._row(c, "space", "Image dimming", "How much the theme colour covers the image (keeps text readable).",
                  self._scale("background_dim", 0.0, 0.95, 0.05, 2, fmt=lambda v: f"{int(v * 100)}%"))
        self._row(c, "space", "Window opacity", "See your desktop through the terminal (needs a compositor).",
                  self._scale("opacity", 0.3, 1.0, 0.01, 2, fmt=lambda v: f"{int(v * 100)}%"))
        c = self._group(pg, "Window style")
        self._row(c, "space", "UI style", "Glass: translucent bars · Solid: classic · Minimal: flat and quiet · "
                  "Liquid Glass: the whole window is curved glass over your wallpaper.",
                  self._segmented("ui_style", [("glass", "Glass"), ("solid", "Solid"), ("minimal", "Minimal"),
                                               ("liquid", "Liquid Glass")]))
        return pg

    # ---------------------------------------------------------------- liquid glass
    def _page_glass(self):
        pg = self._page("Liquid Glass", "The window becomes a slab of curved glass that bends and frosts your wallpaper, "
                        "lit along its rim. Pick a ◈ Liquid theme, or switch any theme to it here. Every slider "
                        "applies live.")
        pct = lambda v: f"{int(round(v * 100))}%"  # noqa: E731
        times = lambda v: f"{v:.1f}×"  # noqa: E731
        px = lambda v: f"{int(v)} px"  # noqa: E731

        c = self._group(pg, "Liquid Glass")
        th = themes.get(self.s["theme"])
        sw = Gtk.Switch(active=self.s["ui_style"] == "liquid")
        sw.connect("notify::active", lambda w, _p: self.s.__setitem__("ui_style", "liquid" if w.get_active() else "glass"))
        note = " It's on now because your theme is a Liquid theme." if th.get("liquid") else ""
        self._row(c, "glass", "Use Liquid Glass with any theme",
                  "Same as UI style → Liquid Glass. The theme's background colour becomes the glass tint." + note, sw)
        self._row(c, "glass", "Preset", "A starting point. Fine-tune with the sliders below.", self._glass_presets())
        self._row(c, "glass", "Glass tone", "Dark or light glass. Auto follows the theme.",
                  self._segmented("glass_tone", [("auto", "Auto"), ("dark", "Dark"), ("light", "Light")]))

        c = self._group(pg, "Glass")
        self._row(c, "glass", "Frost (blur)", "How much the wallpaper behind the glass is blurred.",
                  self._scale("glass_frost", 0.0, 1.0, 0.01, 2, fmt=pct))
        self._row(c, "glass", "Refraction", "How strongly the curved edge bends what's behind it.",
                  self._scale("glass_refraction", 0.0, 3.0, 0.05, 2, fmt=times))
        self._row(c, "glass", "Edge width", "How far in from the border the glass curves.",
                  self._scale("glass_edge", 6, 80, 1, 0, fmt=px))
        self._row(c, "glass", "Chromatic dispersion", "The rainbow fringe where light splits at the rim.",
                  self._scale("glass_dispersion", 0.0, 4.0, 0.05, 2, fmt=times))
        self._row(c, "glass", "Lens", "Magnifies the backdrop through the whole pane, like a thick lens.",
                  self._scale("glass_lens", 0.0, 1.0, 0.01, 2, fmt=pct))

        c = self._group(pg, "Colour & light")
        self._row(c, "glass", "Tint", "The theme's background colour laid over the glass. Higher reads easier.",
                  self._scale("glass_tint", 0.0, 1.0, 0.01, 2, fmt=pct))
        self._row(c, "glass", "Vibrancy", "Saturation of the colours seen through the glass.",
                  self._scale("glass_vibrancy", 0.0, 2.5, 0.05, 2, fmt=times))
        self._row(c, "glass", "Rim light", "The specular highlight running along the edge.",
                  self._scale("glass_rim", 0.0, 2.0, 0.05, 2, fmt=times))
        self._row(c, "glass", "Grain", "Fine texture over the glass.",
                  self._scale("glass_grain", 0.0, 1.0, 0.01, 2, fmt=pct))
        self._row(c, "glass", "Stars on the glass", "Keep the starfield drifting inside the glass.",
                  self._switch("glass_stars"))

        c = self._group(pg, "Shape")
        self._row(c, "glass", "Corner radius", "Match your compositor's rounding (Hyprland: decoration:rounding).",
                  self._scale("glass_radius", 0, 40, 1, 0, fmt=px))
        self._row(c, "glass", "Shadow", "Drop shadow under floating windows.",
                  self._scale("glass_shadow", 0.0, 1.0, 0.01, 2, fmt=pct))

        c = self._group(pg, "Backdrop")
        box = Gtk.Box(spacing=6)
        cur = self.s["glass_wallpaper"]
        lbl = Gtk.Label(label=os.path.basename(cur) if cur else "Auto-detect", ellipsize=3, max_width_chars=22)
        pick = Gtk.Button(label="Choose…")
        auto = Gtk.Button(label="Auto")
        auto.add_css_class("flat")
        box.append(lbl)
        box.append(pick)
        box.append(auto)

        def choose(*_):
            dlg = Gtk.FileDialog(title="Picture for the glass")
            f = Gtk.FileFilter()
            f.set_name("Images")
            f.add_pixbuf_formats()
            store = Gio.ListStore.new(Gtk.FileFilter)
            store.append(f)
            dlg.set_filters(store)

            def done(d, res):
                try:
                    fl = d.open_finish(res)
                except GLib.Error:
                    return
                self.s["glass_wallpaper"] = fl.get_path()
                lbl.set_text(os.path.basename(fl.get_path()))
            dlg.open(self, None, done)
        pick.connect("clicked", choose)
        auto.connect("clicked", lambda *_: (self.s.__setitem__("glass_wallpaper", ""), lbl.set_text("Auto-detect")))
        self._row(c, "glass", "Wallpaper", "What the glass refracts. Auto finds your wallpaper from swww, awww, "
                  "hyprpaper, waypaper or swaybg; with none, a soft aurora in the theme's colours.", box)
        self._row(c, "glass", "Follow the window", "On Hyprland the glass bends the part of the wallpaper that's "
                  "really behind the window, even while you drag it.", self._switch("glass_follow"))

        reset = Gtk.Button(label="Reset Liquid Glass settings", halign=Gtk.Align.START, margin_top=14)
        reset.connect("clicked", lambda *_: self._apply_glass(dict(liquid.GLASS_DEFAULTS)))
        pg.content.append(reset)
        return pg

    def _glass_presets(self):
        box = Gtk.Box(css_classes=["linked"])
        for _pid, label, vals in GLASS_PRESETS:
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, v=vals: self._apply_glass(v))
            box.append(b)
        return box

    def _apply_glass(self, vals):
        for k, v in vals.items():
            self.s[k] = v
        GLib.idle_add(lambda: (self.reload(), False)[1])

    # ---------------------------------------------------------------- tabs
    def _page_tabs(self):
        pg = self._page("Tabs", "Tabs, splits, sessions and the drop-down terminal.")
        c = self._group(pg, "Tabs")
        self._row(c, "tabs", "Tab bar position", "", self._segmented("tab_position", [("top", "Top"), ("bottom", "Bottom")]))
        self._row(c, "tabs", "Hide the tab bar when there's one tab", "", self._switch("hide_single_tab"))
        self._row(c, "tabs", "Open new tabs and splits in the current folder", "", self._switch("new_tab_cwd"))
        self._row(c, "tabs", "Ask before closing running programs", "", self._switch("confirm_close"))
        self._row(c, "tabs", "Restore tabs and splits on start", "Brings back every tab, split layout and folder.",
                  self._switch("restore_session"))
        c = self._group(pg, "Drop-down (quake) terminal")
        self._row(c, "tabs", "Height", "Share of the screen it covers.",
                  self._scale("quake_height", 0.2, 1.0, 0.05, 2, fmt=lambda v: f"{int(v * 100)}%"))
        cmd = Gtk.Label(label="interstellar --quake", selectable=True)
        cmd.add_css_class("monospace")
        self._row(c, "tabs", "Shortcut", "Bind this command to a key (e.g. F12) in your desktop's keyboard settings — "
                  "it slides the terminal down from the top and hides it again.", cmd)
        return pg

    # ---------------------------------------------------------------- behaviour
    def _page_behaviour(self):
        pg = self._page("Behaviour", "Start-up, scrolling, the clipboard, links, bells and notifications.")
        c = self._group(pg, "Start-up")
        self._row(c, "behaviour", "Keep running in the background",
                  "Interstellar stays loaded after you close the last window, so new windows open instantly "
                  "(Menu → Quit still quits). Start it at login with `interstellar --daemon` and even the first "
                  "window is instant.", self._switch("background"))
        c = self._group(pg, "Scrolling")
        sb = Gtk.Box(spacing=6)
        sp = Gtk.SpinButton.new_with_range(0, 1000000, 1000)
        unl = Gtk.CheckButton(label="Unlimited", active=int(self.s["scrollback"]) < 0)
        sp.set_value(max(0, int(self.s["scrollback"])))
        sp.set_sensitive(not unl.get_active())
        sp.connect("value-changed", lambda w: self.s.__setitem__("scrollback", int(w.get_value())))
        unl.connect("toggled", lambda w: (sp.set_sensitive(not w.get_active()),
                                          self.s.__setitem__("scrollback", -1 if w.get_active() else int(sp.get_value()))))
        sb.append(sp)
        sb.append(unl)
        self._row(c, "behaviour", "Scrollback lines", "", sb)
        self._row(c, "behaviour", "Jump to the bottom on new output", "", self._switch("scroll_on_output"))
        c = self._group(pg, "Clipboard")
        self._row(c, "behaviour", "Copy on select", "Selecting text copies it straight away.", self._switch("copy_on_select"))
        self._row(c, "behaviour", "Safe paste", "Ask before pasting several lines or commands like sudo / rm -rf / curl | sh.",
                  self._switch("safe_paste"))
        c = self._group(pg, "Links and files")
        self._row(c, "behaviour", "Open links with", "Works for URLs, file paths and compiler errors like main.c:42:7.",
                  self._segmented("link_click", [("ctrl", "Ctrl + click"), ("click", "Click")]))
        self._row(c, "behaviour", "Editor command", "Used for file:line links. {file} and {line} are filled in. "
                  "Empty = $VISUAL / $EDITOR in a new tab, else your default app.",
                  self._entry("editor_command", "code -g {file}:{line}"))
        self._row(c, "behaviour", "Word characters", "Characters that count as part of a word on double-click.",
                  self._entry("word_chars", width=22))
        c = self._group(pg, "Alerts")
        self._row(c, "behaviour", "Bell", "", self._segmented("bell", [("visual", "Flash"), ("audible", "Sound"), ("none", "Off")]))
        self._row(c, "behaviour", "Notify when long commands finish", "A desktop notification when a command that ran for "
                  "8+ seconds finishes in a tab you're not looking at.", self._switch("notify_finished"))
        return pg

    # ---------------------------------------------------------------- profiles
    def _page_profiles(self):
        pg = self._page("Profiles", "A profile is a shell or program with its own folder, theme, font and environment — "
                        "e.g. “Python”, “Server logs”, “htop”. Open one from the ▾ next to +.")
        profiles = copy.deepcopy(self.s["profiles"])
        outer = Gtk.Box(spacing=16)
        pg.content.append(outer)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, width_request=200)
        lb = Gtk.ListBox()
        lb.add_css_class("boxed-list")
        left.append(lb)
        btns = Gtk.Box(spacing=4)
        add = Gtk.Button(label="Add")
        dup = Gtk.Button(label="Duplicate")
        rm = Gtk.Button(label="Delete")
        for b in (add, dup, rm):
            btns.append(b)
        left.append(btns)
        outer.append(left)
        form = Gtk.Grid(column_spacing=12, row_spacing=10, hexpand=True)
        outer.append(form)
        name = Gtk.Entry(hexpand=True)
        cmd = Gtk.Entry(placeholder_text="empty = your login shell   e.g.  fish   ·   python3   ·   ssh me@server")
        cwd = Gtk.Entry(placeholder_text="empty = home / current folder   e.g.  ~/projects")
        theme_names = ["Same as window"] + [t["name"] for t in themes.all_themes()]
        theme = Gtk.DropDown.new_from_strings(theme_names)
        theme.set_enable_search(True)
        font = Gtk.Entry(placeholder_text="empty = global font   e.g.  Fira Code 13")
        envv = Gtk.TextView(monospace=True, height_request=80)
        envv.set_tooltip_text("One KEY=value per line")
        default = Gtk.CheckButton(label="Default profile (used for new tabs)")
        for i, (lbl, w) in enumerate((("Name", name), ("Command", cmd), ("Start in", cwd), ("Theme", theme),
                                      ("Font", font), ("Environment", envv))):
            form.attach(Gtk.Label(label=lbl, xalign=1, valign=Gtk.Align.START if w is envv else Gtk.Align.CENTER), 0, i, 1, 1)
            if w is envv:
                f = Gtk.Frame()
                f.set_child(envv)
                form.attach(f, 1, i, 1, 1)
            else:
                form.attach(w, 1, i, 1, 1)
        form.attach(default, 1, 6, 1, 1)
        save = Gtk.Button(label="Save profile", halign=Gtk.Align.START)
        save.add_css_class("suggested-action")
        open_ = Gtk.Button(label="Open in new tab", halign=Gtk.Align.START)
        hb = Gtk.Box(spacing=8)
        hb.append(save)
        hb.append(open_)
        form.attach(hb, 1, 7, 1, 1)
        state = {"i": 0}

        def fill_list():
            c = lb.get_first_child()
            while c:
                n = c.get_next_sibling()
                lb.remove(c)
                c = n
            for p in profiles:
                star = "★ " if p.get("name") == self.s["default_profile"] else ""
                lb.append(Gtk.Label(label=star + p.get("name", "?"), xalign=0, margin_start=10, margin_end=10,
                                    margin_top=8, margin_bottom=8))
            r = lb.get_row_at_index(min(state["i"], len(profiles) - 1))
            if r:
                lb.select_row(r)

        def show(i):
            state["i"] = i
            p = profiles[i]
            name.set_text(p.get("name", ""))
            cmd.set_text(p.get("command", ""))
            cwd.set_text(p.get("cwd", ""))
            t = p.get("theme") or ""
            theme.set_selected(theme_names.index(t) if t in theme_names else 0)
            font.set_text(p.get("font", ""))
            envv.get_buffer().set_text("\n".join(f"{k}={v}" for k, v in (p.get("env") or {}).items()))
            default.set_active(p.get("name") == self.s["default_profile"])

        def collect():
            b = envv.get_buffer()
            env = {}
            for line in b.get_text(b.get_start_iter(), b.get_end_iter(), False).splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip():
                        env[k.strip()] = v.strip()
            old = profiles[state["i"]].get("name")
            nm = name.get_text().strip() or "Profile"
            existing = {p.get("name") for j, p in enumerate(profiles) if j != state["i"]}
            base, n = nm, 2
            while nm in existing:
                nm, n = f"{base} {n}", n + 1
            profiles[state["i"]] = {"name": nm, "command": cmd.get_text().strip(), "cwd": cwd.get_text().strip(),
                                    "theme": "" if theme.get_selected() == 0 else theme_names[theme.get_selected()],
                                    "font": font.get_text().strip(), "env": env}
            if default.get_active() or self.s["default_profile"] == old:
                self.s.set_quiet("default_profile", nm)
            self.s["profiles"] = copy.deepcopy(profiles)
            fill_list()

        def on_sel(_lb, row):
            if row:
                show(row.get_index())
        lb.connect("row-selected", on_sel)
        save.connect("clicked", lambda *_: collect())
        open_.connect("clicked", lambda *_: (collect(), self._open_profile(profiles[state["i"]]["name"])))

        def do_add(*_):
            profiles.append({"name": f"Profile {len(profiles) + 1}", "command": "", "cwd": "", "theme": "", "font": "", "env": {}})
            state["i"] = len(profiles) - 1
            self.s["profiles"] = copy.deepcopy(profiles)
            fill_list()

        def do_dup(*_):
            p = copy.deepcopy(profiles[state["i"]])
            p["name"] += " copy"
            profiles.append(p)
            state["i"] = len(profiles) - 1
            self.s["profiles"] = copy.deepcopy(profiles)
            fill_list()

        def do_rm(*_):
            if len(profiles) <= 1:
                return
            gone = profiles.pop(state["i"])
            if gone.get("name") == self.s["default_profile"]:
                self.s.set_quiet("default_profile", profiles[0]["name"])
            state["i"] = max(0, state["i"] - 1)
            self.s["profiles"] = copy.deepcopy(profiles)
            fill_list()
        add.connect("clicked", do_add)
        dup.connect("clicked", do_dup)
        rm.connect("clicked", do_rm)
        fill_list()
        self.rows_index.append(("profiles", Gtk.Box(), "profiles shell command ssh environment default program"))
        return pg

    def _open_profile(self, name):
        wins = [w for w in self.app.windows_ if w.get_visible()]
        if wins:
            wins[-1].new_tab(profile=self.s.profile(name))
            wins[-1].present()

    # ---------------------------------------------------------------- keys
    def _page_keys(self):
        pg = self._page("Keyboard", "Click a shortcut, then press the new keys. Backspace removes it, Esc cancels.")
        top = Gtk.Box(spacing=8, margin_bottom=8)
        filt = Gtk.SearchEntry(placeholder_text="Filter shortcuts", hexpand=True)
        top.append(filt)
        reset = Gtk.Button(label="Reset to defaults")
        reset.connect("clicked", lambda *_: (self.s.__setitem__("keybindings", {}), self.reload()))
        top.append(reset)
        pg.content.append(top)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("prefs-card")
        pg.content.append(card)
        rows = []
        for action, label, _ in keys.ACTIONS:
            b = Gtk.Button(label=self._accel_label(keys.accel(self.s, action)))
            b.add_css_class("kbd-btn")
            b.connect("clicked", lambda btn, a=action: self._capture(a, btn))
            r = self._row(card, "keys", label, "", b)
            rows.append((r, label.lower() + " " + action))

        def refilter(*_):
            q = filt.get_text().lower()
            for r, t in rows:
                r.set_visible(q in t)
        filt.connect("search-changed", refilter)
        return pg

    @staticmethod
    def _accel_label(a):
        if not a:
            return "—"
        ok, kv, mods = Gtk.accelerator_parse(a)
        return Gtk.accelerator_get_label(kv, mods) if ok else a

    def _capture(self, action, btn):
        btn.set_label("Press keys…")
        kc = Gtk.EventControllerKey()
        kc.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        mods_only = {Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Shift_L, Gdk.KEY_Shift_R, Gdk.KEY_Alt_L,
                     Gdk.KEY_Alt_R, Gdk.KEY_Super_L, Gdk.KEY_Super_R, Gdk.KEY_Meta_L, Gdk.KEY_Meta_R}

        def done():
            self.remove_controller(kc)

        def on_key(c, kv, code, state):
            if kv in mods_only:
                return True
            st = state & Gtk.accelerator_get_default_mod_mask()
            kb = dict(self.s["keybindings"] or {})
            if kv == Gdk.KEY_Escape and not st:
                btn.set_label(self._accel_label(keys.accel(self.s, action)))
                done()
                return True
            if kv == Gdk.KEY_BackSpace and not st:
                kb[action] = ""
            else:
                kv = Gdk.keyval_to_lower(kv)
                acc = Gtk.accelerator_name(kv, st)
                clash = [a for a, k in keys.all_accels(self.s).items() if k == acc and a != action]
                for a in clash:
                    kb[a] = ""
                kb[action] = acc
                if clash:
                    self._toast_label = f"Removed it from: {', '.join(keys.LABELS[a] for a in clash)}"
            self.s["keybindings"] = kb
            done()
            GLib.idle_add(lambda: (self.reload(), False)[1])
            return True
        kc.connect("key-pressed", on_key)
        self.add_controller(kc)

    # ---------------------------------------------------------------- advanced
    def _page_advanced(self):
        pg = self._page("Advanced", f"{NAME} {VERSION} · settings are stored in {CFG_FILE}")
        c = self._group(pg, "Custom CSS")
        tv = Gtk.TextView(monospace=True, height_request=160, top_margin=8, left_margin=8)
        tv.get_buffer().set_text(self.s["custom_css"] or "/* e.g.  .istl-tab.active { box-shadow: inset 0 -3px #ff6ad5; } */")
        f = Gtk.Frame(margin_start=14, margin_end=14, margin_top=10)
        f.set_child(tv)
        c.append(f)
        ap = Gtk.Button(label="Apply CSS", halign=Gtk.Align.START, margin_start=14, margin_top=8, margin_bottom=12)

        def apply_css(*_):
            b = tv.get_buffer()
            txt = b.get_text(b.get_start_iter(), b.get_end_iter(), False)
            self.s["custom_css"] = "" if txt.strip().startswith("/* e.g.") else txt
        ap.connect("clicked", apply_css)
        c.append(ap)
        self.rows_index.append(("advanced", Gtk.Box(), "custom css style advanced"))
        c = self._group(pg, "Settings")
        b1 = Gtk.Button(label="Open folder")
        b1.connect("clicked", lambda *_: Gtk.FileLauncher.new(Gio.File.new_for_path(CFG_DIR)).launch(self, None, None, None))
        self._row(c, "advanced", "Configuration folder", CFG_DIR, b1)
        b2 = Gtk.Button(label="Export…")
        b2.connect("clicked", lambda *_: self._export_settings())
        b3 = Gtk.Button(label="Import…")
        b3.connect("clicked", lambda *_: self._import_settings())
        bx = Gtk.Box(spacing=6)
        bx.append(b2)
        bx.append(b3)
        self._row(c, "advanced", "Back up or move your setup", "Exports settings, profiles and keys as one JSON file.", bx)
        b4 = Gtk.Button(label="Reset…")
        b4.add_css_class("destructive-action")
        b4.connect("clicked", lambda *_: self._confirm_reset())
        self._row(c, "advanced", "Reset everything", "Profiles, keys and your session are kept.", b4)
        return pg

    def _export_settings(self):
        dlg = Gtk.FileDialog(title="Export settings", initial_name="interstellar-settings.json")

        def done(d, res):
            try:
                f = d.save_finish(res)
            except GLib.Error:
                return
            data = {k: v for k, v in self.s.d.items() if k != "session"}
            with open(f.get_path(), "w") as fh:
                json.dump(data, fh, indent=2)
        dlg.save(self, None, done)

    def _import_settings(self):
        dlg = Gtk.FileDialog(title="Import settings")

        def done(d, res):
            try:
                f = d.open_finish(res)
                data = json.load(open(f.get_path()))
            except (GLib.Error, OSError, ValueError):
                return
            for k, v in data.items():
                if k in DEFAULTS and k != "session":
                    self.s.set_quiet(k, v)
            for fn in list(self.s.listeners):
                fn("*")
        dlg.open(self, None, done)

    def _confirm_reset(self):
        d = Gtk.AlertDialog(message="Reset all settings?", detail="Appearance and behaviour go back to the defaults. "
                            "Your profiles, shortcuts and session are kept.", buttons=["Cancel", "Reset"],
                            cancel_button=0, default_button=0)

        def done(dlg, res):
            try:
                if dlg.choose_finish(res) == 1:
                    self.s.reset()
            except GLib.Error:
                pass
        d.choose(self, None, done)

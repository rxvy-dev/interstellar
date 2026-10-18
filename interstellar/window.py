"""Main window: custom title bar with tabs, a stack of tabs where each tab is a tree of split panes,
the starfield backdrop behind everything, and all window actions."""
import os, time

from gi.repository import Gtk, Gdk, Gio, GLib, GObject

from . import keys, themes, liquid, NAME
from .pane import Pane
from . import icons
from .starfield import Backdrop
from .glass import GlassLayer


class Tab:
    _ids = 0

    def __init__(self, win):
        Tab._ids += 1
        self.id = f"tab{Tab._ids}"
        self.win = win
        self.root = Gtk.Box(hexpand=True, vexpand=True)
        self.focused = None
        self.title = ""
        self.broadcast = False
        self.zoomed = None
        self.widget = None   # tab-strip button
        self.label = None
        self.dot = None
        self.icon = None

    def panes(self):
        out = []

        def walk(w):
            if isinstance(w, Pane):
                out.append(w)
            elif isinstance(w, Gtk.Paned):
                walk(w.get_start_child())
                walk(w.get_end_child())
            elif w is not None:
                c = w.get_first_child()
                while c:
                    walk(c)
                    c = c.get_next_sibling()
        walk(self.root)
        return out

    def display_title(self):
        if self.title:
            return self.title
        p = self.focused or (self.panes() or [None])[0]
        return p.title() if p else "shell"


class Window(Gtk.ApplicationWindow):
    def __init__(self, app, quake=False, restore=None, cwd=None, argv=None, profile=None):
        super().__init__(application=app)
        self.app = app
        self.s = app.s
        self.quake = quake
        self.tabs = []
        self._feeding = False
        self.add_css_class("istl")
        self.set_title(NAME)
        self.set_icon_name("interstellar")
        self.set_default_size(int(self.s["width"]), int(self.s["height"]))

        # ---- layout: Liquid Glass (when on) under the backdrop (stars) under everything
        self.overlay = Gtk.Overlay()
        self.bg = Gtk.Overlay(can_target=False, can_focus=False)
        self.glass_holder = Gtk.Box(hexpand=True, vexpand=True, can_target=False)
        self.bg.set_child(self.glass_holder)
        self.backdrop = Backdrop(self.s)
        self.bg.add_overlay(self.backdrop)
        self.overlay.set_child(self.bg)
        self.glass = None
        self.liquid = False
        self._inline_hb = None
        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.overlay.add_overlay(self.main)
        self.overlay.set_measure_overlay(self.main, True)
        self.set_child(self.overlay)

        self.stack = Gtk.Stack(hexpand=True, vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE,
                               transition_duration=110)
        self.stack.add_css_class("istl-pages")

        self._build_bar()
        self.main.append(self.stack)

        # floating bits
        self.toast_rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.CROSSFADE,
                                      halign=Gtk.Align.CENTER, valign=Gtk.Align.END, can_target=False)
        self.toast_lbl = Gtk.Label()
        self.toast_lbl.add_css_class("istl-toast")
        self.toast_rev.set_child(self.toast_lbl)
        self.overlay.add_overlay(self.toast_rev)
        self._toast_id = 0
        self.status = Gtk.Label(halign=Gtk.Align.START, valign=Gtk.Align.END, margin_start=10, margin_bottom=6,
                                can_target=False, visible=False, ellipsize=3, max_width_chars=90)
        self.status.add_css_class("istl-banner")
        self.overlay.add_overlay(self.status)
        self.palette = None
        self.quick = None

        self._install_actions()
        self.backdrop.set_theme(themes.get(self.app.theme_name()))
        self.apply_liquid(layout=False)
        self.apply_layout()

        if restore:
            for t in restore:
                self.restore_tab(t)
        if not self.tabs:
            self.new_tab(cwd=cwd, argv=argv, profile=profile)

        self.connect("close-request", self._on_close_request)
        self.connect("notify::is-active", self._on_active)
        self._poll_id = GLib.timeout_add(1000, self._poll)
        if quake:
            self.set_decorated(False)

    # ================================================================== title bar + tabs
    def _build_bar(self):
        self.tabbox = Gtk.Box(spacing=0)
        self.tabscroll = Gtk.ScrolledWindow(hexpand=True, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                            hscrollbar_policy=Gtk.PolicyType.EXTERNAL, propagate_natural_width=False)
        self.tabscroll.set_child(self.tabbox)
        sc = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        sc.connect("scroll", self._tab_scroll)
        self.tabscroll.add_controller(sc)

        self.bar = Gtk.Box(spacing=2)
        self.bar.add_css_class("istl-bar")
        brand = Gtk.Label(label="✦")
        brand.add_css_class("istl-brand")
        brand.set_tooltip_text(NAME)
        self.brand = brand
        self.bar.append(brand)
        self.bar.append(self.tabscroll)

        newb = icons.button("plus", "New tab (Ctrl+Shift+T)")
        newb.connect("clicked", lambda *_: self.new_tab())
        self.profile_btn = icons.menu_button("down", "New tab with profile…", 14)
        self.bar.append(newb)
        self.bar.append(self.profile_btn)
        self.bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_top=10, margin_bottom=10))

        pal = icons.button("search", "Command palette (Ctrl+Shift+P)")
        pal.connect("clicked", lambda *_: self.show_palette())
        self.bar.append(pal)
        theme_btn = icons.button("planet", "Themes", 18)
        theme_btn.connect("clicked", lambda *_: self.show_palette("theme: "))
        self.bar.append(theme_btn)
        menu = icons.menu_button("menu", "Menu")
        menu.set_menu_model(self._main_menu())
        menu.get_popover().add_css_class("istl-pop")
        self.bar.append(menu)
        self.wctl = Gtk.WindowControls(side=Gtk.PackType.END)
        self.bar.append(self.wctl)

        self.handle = Gtk.WindowHandle()
        self.bottom_holder = Gtk.Box()
        self._refresh_profile_menu()

    def apply_liquid(self, layout=True):
        """Liquid Glass on/off: the glass layer under the stars, the title bar moved onto the glass."""
        th = themes.get(self.app.theme_name())
        on = liquid.is_liquid(self.s["ui_style"], th)
        if on and self.glass is None:
            self.glass = GlassLayer(self)
            self.glass_holder.append(self.glass)
        elif not on and self.glass is not None:
            self.glass.shutdown()
            self.glass_holder.remove(self.glass)
            self.glass = None
        changed = on != self.liquid
        self.liquid = on
        self.backdrop.set_liquid(on)
        if on:
            self.add_css_class("liquid")
        else:
            self.remove_css_class("liquid")
        if changed and layout:
            self.apply_layout()
        if self.glass is not None:
            self.glass.refresh()

    def apply_layout(self):
        """Tabs on top live in the title bar; at the bottom they sit under the terminal.
        With Liquid Glass the title bar sits inside the window instead, so it is part of the glass."""
        bottom = self.s["tab_position"] == "bottom"
        inline = self.liquid and not self.quake
        if self.handle.get_parent() is self.main:
            self.main.remove(self.handle)
        if self._inline_hb is not None and self._inline_hb.get_parent() is self.main:
            self.main.remove(self._inline_hb)
        self._inline_hb = None
        parent = self.bar.get_parent()
        if isinstance(parent, Gtk.WindowHandle):
            parent.set_child(None)
        elif parent is not None:
            parent.remove(self.bar)
        self.bar.remove_css_class("bottom")
        if self.quake:
            self.wctl.set_visible(False)
            self.main.prepend(self.bar)
        elif bottom:
            self.wctl.set_visible(False)
            self.bar.add_css_class("bottom")
            self.main.append(self.bar)
            hb = Gtk.HeaderBar()
            hb.add_css_class("istl-bar")
            self.title_lbl = Gtk.Label(label=NAME)
            hb.set_title_widget(self.title_lbl)
            if inline:
                self.set_titlebar(Gtk.Box())     # empty: keeps client-side decorations, no title bar
                self.main.prepend(hb)
                self._inline_hb = hb
            else:
                self.set_titlebar(hb)
        else:
            self.wctl.set_visible(True)
            self.title_lbl = None
            if inline:
                self.set_titlebar(Gtk.Box())
                self.handle.set_child(self.bar)
                self.main.prepend(self.handle)
            else:
                self.handle.set_child(self.bar)
                self.set_titlebar(self.handle)
        self._update_tabstrip_visibility()

    def _main_menu(self):
        m = Gio.Menu()
        s1 = Gio.Menu()
        s1.append("New Window", "win.new-window")
        s1.append("Split Right", "win.split-right")
        s1.append("Split Down", "win.split-down")
        s1.append("Broadcast Input to Panes", "win.broadcast")
        m.append_section(None, s1)
        s2 = Gio.Menu()
        s2.append("Toggle Starfield", "win.toggle-starfield")
        s2.append("Next Theme", "win.next-theme")
        s2.append("Fullscreen", "win.fullscreen")
        m.append_section(None, s2)
        s3 = Gio.Menu()
        s3.append("Preferences", "win.preferences")
        s3.append("Keyboard Shortcuts", "win.show-keys")
        s3.append("About Interstellar", "win.about")
        m.append_section(None, s3)
        return m

    def _refresh_profile_menu(self):
        m = Gio.Menu()
        sec = Gio.Menu()
        for p in self.s["profiles"]:
            sec.append(p.get("name", "?"), f"win.new-tab-profile::{p.get('name', '')}")
        m.append_section("New tab with profile", sec)
        s2 = Gio.Menu()
        s2.append("Edit profiles…", "win.edit-profiles")
        m.append_section(None, s2)
        self.profile_btn.set_menu_model(m)
        pop = self.profile_btn.get_popover()
        if pop:
            pop.add_css_class("istl-pop")

    def _make_tab_widget(self, tab):
        w = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        w.add_css_class("istl-tab")
        tab.dot = Gtk.Box(valign=Gtk.Align.CENTER, visible=False)
        tab.dot.add_css_class("istl-dot")
        tab.icon = icons.Icon("prompt", 14)
        tab.icon.add_css_class("icon")
        tab.label = Gtk.Label(label="shell", ellipsize=3, max_width_chars=22, width_chars=6, xalign=0)
        tab.label.add_css_class("title")
        close = icons.button("close", size=12)
        close.set_valign(Gtk.Align.CENTER)
        close.add_css_class("close")
        close.set_tooltip_text("Close tab")
        close.connect("clicked", lambda *_: self.close_tab(tab))
        for c in (tab.dot, tab.icon, tab.label, close):
            w.append(c)
        g = Gtk.GestureClick(button=0)
        g.connect("pressed", self._tab_pressed, tab)
        w.add_controller(g)
        # drag to reorder
        ds = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        ds.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(tab.id))
        w.add_controller(ds)
        dt = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        dt.connect("drop", self._tab_drop, tab)
        w.add_controller(dt)
        tab.widget = w
        return w

    def _tab_pressed(self, g, n, x, y, tab):
        btn = g.get_current_button()
        if btn == 2:
            self.close_tab(tab)
        elif btn == 3:
            self.select_tab(tab)
            self._tab_menu(tab, x, y)
        elif btn == 1:
            if n == 2:
                self.rename_tab(tab)
            else:
                self.select_tab(tab)

    def _tab_menu(self, tab, x, y):
        m = Gio.Menu()
        m.append("Rename…", "win.rename-tab")
        m.append("Duplicate", "win.duplicate-tab")
        m.append("Move to New Window", "win.detach-tab")
        sec = Gio.Menu()
        sec.append("Close Other Tabs", "win.close-others")
        sec.append("Close Tab", "win.close-tab")
        m.append_section(None, sec)
        pop = Gtk.PopoverMenu.new_from_model(m)
        pop.add_css_class("istl-pop")
        pop.set_parent(tab.widget)
        r = Gdk.Rectangle()
        r.x, r.y, r.width, r.height = int(x), int(y), 1, 1
        pop.set_pointing_to(r)
        pop.set_has_arrow(False)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        pop.popup()

    def _tab_drop(self, target, value, x, y, dest):
        src = next((t for t in self.tabs if t.id == value), None)
        if not src or src is dest:
            return False
        self.tabs.remove(src)
        self.tabs.insert(self.tabs.index(dest) + (1 if x > dest.widget.get_width() / 2 else 0), src)
        self._reorder_strip()
        return True

    def _reorder_strip(self):
        prev = None
        for t in self.tabs:
            self.tabbox.reorder_child_after(t.widget, prev)
            prev = t.widget

    def _tab_scroll(self, c, dx, dy):
        cur = self.current_tab()
        if cur and self.tabs:
            i = (self.tabs.index(cur) + (1 if dy > 0 else -1)) % len(self.tabs)
            self.select_tab(self.tabs[i])
        return True

    def _update_tabstrip_visibility(self):
        show = not (self.s["hide_single_tab"] and len(self.tabs) <= 1)
        self.tabscroll.set_visible(show)
        self.brand.set_hexpand(not show)
        self.brand.set_halign(Gtk.Align.START)

    # ================================================================== tabs
    def current_tab(self):
        child = self.stack.get_visible_child()
        return next((t for t in self.tabs if t.root is child), None)

    def current_pane(self):
        t = self.current_tab()
        if not t:
            return None
        if t.focused and t.focused.get_root() is self:
            return t.focused
        ps = t.panes()
        return ps[0] if ps else None

    def new_tab(self, profile=None, cwd=None, argv=None, title=None, select=True):
        if cwd is None and self.s["new_tab_cwd"] and argv is None:
            p = self.current_pane()
            if p and not (profile and profile.get("cwd")):
                cwd = p.cwd
        tab = Tab(self)
        pane = Pane(self, profile=profile, cwd=cwd, argv=argv, title=None)
        if title:
            tab.title = title
        tab.root.append(pane)
        tab.focused = pane
        self._add_tab(tab, select)
        return tab

    def _add_tab(self, tab, select=True, index=None):
        cur = self.current_tab()
        if index is None:
            index = self.tabs.index(cur) + 1 if cur in self.tabs else len(self.tabs)
        self.tabs.insert(index, tab)
        self.stack.add_named(tab.root, tab.id)
        self.tabbox.append(self._make_tab_widget(tab))
        self._reorder_strip()
        self._update_tabstrip_visibility()
        self._refresh_tab(tab)
        if select:
            self.select_tab(tab)

    def select_tab(self, tab):
        self.stack.set_visible_child(tab.root)
        for t in self.tabs:
            if t is tab:
                t.widget.add_css_class("active")
            else:
                t.widget.remove_css_class("active")
        tab.dot.set_visible(False)
        tab.dot.set_css_classes(["istl-dot"])
        self._refresh_tab(tab)
        p = tab.focused or (tab.panes() or [None])[0]
        if p:
            GLib.idle_add(self._focus_once, p)
        # keep the active tab visible in the strip
        GLib.idle_add(self._scroll_to_tab, tab)

    def _scroll_to_tab(self, tab):
        if tab.widget and tab.widget.get_mapped():
            ok, b = tab.widget.compute_bounds(self.tabbox)
            if ok:
                adj = self.tabscroll.get_hadjustment()
                if b.origin.x < adj.get_value():
                    adj.set_value(b.origin.x)
                elif b.origin.x + b.size.width > adj.get_value() + adj.get_page_size():
                    adj.set_value(b.origin.x + b.size.width - adj.get_page_size())
        return False

    @staticmethod
    def _focus_once(p):
        p.term.grab_focus()
        return False

    def _refresh_tab(self, tab):
        title = tab.display_title()
        if tab.label:
            tab.label.set_text(title)
            tab.widget.set_tooltip_text(title)
            icon = "prompt"
            if len(tab.panes()) > 1:
                icon = "grid"
            p = tab.focused
            if p and p.running_command():
                icon = "play"
            if tab.broadcast:
                icon = "broadcast"
            tab.icon.set_icon(icon)
        if tab is self.current_tab():
            self.set_title(f"{title} — {NAME}")
            if getattr(self, "title_lbl", None):
                self.title_lbl.set_text(title)

    def close_tab(self, tab, force=False):
        if not force and self.s["confirm_close"]:
            running = [p for p in tab.panes() if p.running_command()]
            if running:
                names = ", ".join(sorted({p.proc_name for p in running if p.proc_name})) or "a program"
                self._confirm("Close this tab?", f"{names} is still running in it.", "Close Tab",
                              lambda: self.close_tab(tab, force=True))
                return
        if tab not in self.tabs:
            return
        i = self.tabs.index(tab)
        was_current = tab is self.current_tab()
        self.tabs.remove(tab)
        self.tabbox.remove(tab.widget)
        self.stack.remove(tab.root)
        for p in tab.panes():
            self._kill(p)
        if not self.tabs:
            self._really_close = True
            self.close()
            return
        if was_current:
            self.select_tab(self.tabs[min(i, len(self.tabs) - 1)])
        self._update_tabstrip_visibility()

    def _kill(self, p):
        if p.child_pid > 0 and not p.exited:
            try:
                os.kill(p.child_pid, 1)  # SIGHUP, like closing a real terminal
            except OSError:
                pass

    def rename_tab(self, tab=None):
        tab = tab or self.current_tab()
        if not tab:
            return
        entry = Gtk.Entry(text=tab.display_title(), width_chars=14)
        lbl = tab.label
        lbl.set_visible(False)
        tab.widget.insert_child_after(entry, lbl)
        entry.grab_focus()
        done = {"v": False}

        def finish(save):
            if done["v"]:
                return
            done["v"] = True
            if save:
                tab.title = entry.get_text().strip()
            tab.widget.remove(entry)
            lbl.set_visible(True)
            self._refresh_tab(tab)
            if tab.focused:
                tab.focused.term.grab_focus()

        entry.connect("activate", lambda *_: finish(True))
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", lambda c, kv, *_: (finish(False), True)[1] if kv == Gdk.KEY_Escape else False)
        entry.add_controller(kc)
        fc = Gtk.EventControllerFocus()
        fc.connect("leave", lambda *_: GLib.idle_add(lambda: (finish(True), False)[1]))
        entry.add_controller(fc)

    def move_tab(self, d):
        t = self.current_tab()
        if not t:
            return
        i = self.tabs.index(t)
        j = max(0, min(len(self.tabs) - 1, i + d))
        self.tabs.insert(j, self.tabs.pop(i))
        self._reorder_strip()

    # ================================================================== panes / splits
    def tab_of(self, pane):
        for t in self.tabs:
            w = pane
            while w is not None:
                if w is t.root:
                    return t
                w = w.get_parent()
        return None

    @staticmethod
    def _replace(old, new):
        parent = old.get_parent()
        if isinstance(parent, Gtk.Paned):
            if parent.get_start_child() is old:
                parent.set_start_child(None)
                parent.set_start_child(new)
            else:
                parent.set_end_child(None)
                parent.set_end_child(new)
        else:
            parent.remove(old)
            parent.append(new)

    def split(self, pane=None, vertical=False, profile=None):
        pane = pane or self.current_pane()
        tab = self.tab_of(pane) if pane else None
        if not tab:
            return
        if tab.zoomed:
            self.toggle_zoom()
        w, h = pane.get_width(), pane.get_height()
        cwd = pane.cwd if self.s["new_tab_cwd"] else None
        new = Pane(self, profile=profile or pane.profile, cwd=cwd)
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,
                          wide_handle=False, shrink_start_child=False, shrink_end_child=False)
        paned.add_css_class("istl")
        self._replace(pane, paned)
        paned.set_start_child(pane)
        paned.set_end_child(new)
        self._half(paned, (h if vertical else w))
        tab.focused = new
        self._mark_split(tab)
        GLib.idle_add(self._focus_once, new)
        self._refresh_tab(tab)
        return new

    @staticmethod
    def _half(paned, size, ratio=0.5):
        """Put the divider at `ratio`, now if the size is known, else as soon as the paned is allocated."""
        if size > 2:
            paned.set_position(int(size * ratio))
            return

        def on_max(p, _pspec):
            if p.get_property("max-position") > 2:
                p.disconnect(hid[0])
                full = p.get_height() if p.get_orientation() == Gtk.Orientation.VERTICAL else p.get_width()
                p.set_position(int((full or p.get_property("max-position")) * ratio))
        hid = [paned.connect("notify::max-position", on_max)]

    def _mark_split(self, tab):
        ps = tab.panes()
        for p in ps:
            if len(ps) > 1:
                p.add_css_class("split")
            else:
                p.remove_css_class("split")
            if p is tab.focused:
                p.add_css_class("focused")
            else:
                p.remove_css_class("focused")
            if tab.broadcast and len(ps) > 1:
                p.add_css_class("broadcast")
            else:
                p.remove_css_class("broadcast")

    def close_pane(self, pane=None, force=False):
        pane = pane or self.current_pane()
        tab = self.tab_of(pane) if pane else None
        if not tab:
            return
        if not force and self.s["confirm_close"] and pane.running_command():
            self._confirm("Close this pane?", f"{pane.proc_name or 'A program'} is still running in it.",
                          "Close", lambda: self.close_pane(pane, force=True))
            return
        if len(tab.panes()) <= 1:
            self.close_tab(tab, force=True)
            return
        if tab.zoomed:
            self.toggle_zoom(tab)
        parent = pane.get_parent()
        sibling = parent.get_end_child() if parent.get_start_child() is pane else parent.get_start_child()
        parent.set_start_child(None)
        parent.set_end_child(None)
        self._replace(parent, sibling)
        self._kill(pane)
        rest = tab.panes()
        tab.focused = rest[0] if rest else None
        # prefer a pane from the sibling subtree
        sib_panes = [sibling] if isinstance(sibling, Pane) else [p for p in rest if p.is_ancestor(sibling)]
        if sib_panes:
            tab.focused = sib_panes[0]
        self._mark_split(tab)
        if tab.focused:
            GLib.idle_add(self._focus_once, tab.focused)
        self._refresh_tab(tab)

    def focus_dir(self, dx, dy):
        tab = self.current_tab()
        cur = self.current_pane()
        if not tab or not cur:
            return
        ok, cb = cur.compute_bounds(tab.root)
        if not ok:
            return
        cx, cy = cb.origin.x + cb.size.width / 2, cb.origin.y + cb.size.height / 2
        best, bd = None, 1e18
        for p in tab.panes():
            if p is cur or not p.get_mapped():
                continue
            ok, b = p.compute_bounds(tab.root)
            if not ok:
                continue
            px, py = b.origin.x + b.size.width / 2, b.origin.y + b.size.height / 2
            vx, vy = px - cx, py - cy
            if dx and (vx * dx <= 0 or abs(vy) > (b.size.height + cb.size.height) / 2):
                continue
            if dy and (vy * dy <= 0 or abs(vx) > (b.size.width + cb.size.width) / 2):
                continue
            d = abs(vx) + abs(vy)
            if d < bd:
                best, bd = p, d
        if best:
            best.term.grab_focus()

    def toggle_zoom(self, tab=None):
        tab = tab or self.current_tab()
        if not tab or len(tab.panes()) < 2:
            return
        if tab.zoomed:
            def show_all(w):
                if w is None:
                    return
                w.set_visible(True)
                if isinstance(w, Gtk.Paned):
                    show_all(w.get_start_child())
                    show_all(w.get_end_child())
            c = tab.root.get_first_child()
            show_all(c)
            tab.zoomed = None
            self.toast("Showing all panes")
        else:
            p = tab.focused or self.current_pane()
            w = p
            while w.get_parent() is not tab.root:
                par = w.get_parent()
                other = par.get_end_child() if par.get_start_child() is w else par.get_start_child()
                other.set_visible(False)
                w = par
            tab.zoomed = p
            self.toast("Pane zoomed — Ctrl+Shift+Z to show all")
        if tab.focused:
            GLib.idle_add(self._focus_once, tab.focused)

    # ================================================================== callbacks from panes
    def on_pane_focus(self, pane):
        tab = self.tab_of(pane)
        if not tab:
            return
        tab.focused = pane
        self._mark_split(tab)
        self._refresh_tab(tab)

    def on_pane_title(self, pane):
        tab = self.tab_of(pane)
        if tab:
            self._refresh_tab(tab)

    def on_pane_activity(self, pane, kind):
        tab = self.tab_of(pane)
        if not tab or tab is self.current_tab():
            return
        if kind == "bell":
            tab.dot.set_css_classes(["istl-dot", "bell"])
        elif "done" in tab.dot.get_css_classes() or "bell" in tab.dot.get_css_classes():
            return
        tab.dot.set_visible(True)

    def on_command_finished(self, pane, name, took):
        tab = self.tab_of(pane)
        if not tab:
            return
        mins, secs = divmod(int(took), 60)
        dur = f"{mins}m {secs}s" if mins else f"{secs}s"
        visible = tab is self.current_tab() and self.is_active()
        if visible:
            return
        if tab is not self.current_tab():
            tab.dot.set_css_classes(["istl-dot", "done"])
            tab.dot.set_visible(True)
        if self.s["notify_finished"]:
            n = Gio.Notification.new(f"✓ {name or 'Command'} finished")
            n.set_body(f"in {tab.display_title()} after {dur}")
            n.set_default_action_and_target("app.focus-tab", GLib.Variant("s", tab.id))
            try:
                self.app.send_notification(f"done-{tab.id}", n)
            except Exception:
                pass
        if self.is_active():
            self.toast(f"✓ {name or 'Command'} finished in “{tab.display_title()}” ({dur})")
        self._refresh_tab(tab)

    def on_pane_commit(self, pane, text):
        tab = self.tab_of(pane)
        if not tab or not tab.broadcast or self._feeding:
            return
        self._feeding = True
        try:
            data = text.encode()
            for p in tab.panes():
                if p is not pane and not p.exited:
                    p.term.feed_child(data)
        finally:
            self._feeding = False

    def update_context_menu(self, pane):
        m = Gio.Menu()
        if pane.ctx_link:
            sec = Gio.Menu()
            kind, text = pane.ctx_link
            sec.append("Open Link" if kind == "url" else "Open File", "win.open-link")
            sec.append("Copy Link" if kind == "url" else "Copy Path", "win.copy-link")
            m.append_section(None, sec)
        s1 = Gio.Menu()
        s1.append("Copy", "win.copy")
        s1.append("Paste", "win.paste")
        s1.append("Select All", "win.select-all")
        s1.append("Find…", "win.find")
        m.append_section(None, s1)
        s2 = Gio.Menu()
        s2.append("Split Right", "win.split-right")
        s2.append("Split Down", "win.split-down")
        if len(self.current_tab().panes()) > 1:
            s2.append("Zoom Pane", "win.zoom-pane")
        s2.append("Quick Select", "win.quick-select")
        m.append_section(None, s2)
        s3 = Gio.Menu()
        s3.append("Clear Scrollback", "win.clear")
        s3.append("Save Output…", "win.save-output")
        s3.append("Open Folder", "win.open-cwd")
        m.append_section(None, s3)
        s4 = Gio.Menu()
        s4.append("Preferences", "win.preferences")
        s4.append("Close Pane", "win.close-pane")
        m.append_section(None, s4)
        pane.term.set_context_menu_model(m)

    # ================================================================== small UI
    def toast(self, text, ms=2200):
        self.toast_lbl.set_text(text)
        self.toast_rev.set_reveal_child(True)
        self._toast_id += 1
        tid = self._toast_id

        def hide():
            if tid == self._toast_id:
                self.toast_rev.set_reveal_child(False)
            return False
        GLib.timeout_add(ms, hide)

    def show_status(self, text):
        self.status.set_text(text)
        self.status.set_visible(bool(text))

    def _confirm(self, heading, body, ok_label, on_ok):
        d = Gtk.AlertDialog(message=heading, detail=body, buttons=["Cancel", ok_label], cancel_button=0,
                            default_button=1, modal=True)

        def done(dlg, res):
            try:
                if dlg.choose_finish(res) == 1:
                    on_ok()
            except GLib.Error:
                pass
        d.choose(self, None, done)

    def confirm_paste(self, pane, text, lines):
        preview = "\n".join(text.splitlines()[:8])
        if lines > 8:
            preview += f"\n… ({lines - 8} more lines)"
        d = Gtk.AlertDialog(message=f"Paste {lines} line{'s' if lines != 1 else ''}?" if lines > 1 else "Paste this command?",
                            detail=preview + "\n\nMulti-line or risky pastes can run commands as soon as they land.",
                            buttons=["Cancel", "Paste as one line", "Paste"], cancel_button=0, default_button=2,
                            modal=True)

        def done(dlg, res):
            try:
                r = dlg.choose_finish(res)
            except GLib.Error:
                return
            if r == 2:
                pane.term.paste_text(text)
            elif r == 1:
                pane.term.paste_text(" ".join(l.strip() for l in text.splitlines() if l.strip()))
            pane.term.grab_focus()
        d.choose(self, None, done)

    def show_palette(self, prefill=""):
        from .palette import Palette
        if self.palette is None:
            self.palette = Palette(self)
            self.overlay.add_overlay(self.palette)
        self.palette.open(prefill)

    def quick_select(self):
        from .quickselect import QuickSelect
        p = self.current_pane()
        if not p:
            return
        QuickSelect(self, p).start()

    # ================================================================== actions
    def _install_actions(self):
        A = {
            "new-tab": lambda: self.new_tab(),
            "close-pane": lambda: self.close_pane(),
            "close-tab": lambda: self.current_tab() and self.close_tab(self.current_tab()),
            "close-others": self._close_others,
            "new-window": lambda: self.app.new_window(cwd=(self.current_pane().cwd if self.current_pane() else None)),
            "split-right": lambda: self.split(vertical=False),
            "split-down": lambda: self.split(vertical=True),
            "focus-left": lambda: self.focus_dir(-1, 0),
            "focus-right": lambda: self.focus_dir(1, 0),
            "focus-up": lambda: self.focus_dir(0, -1),
            "focus-down": lambda: self.focus_dir(0, 1),
            "zoom-pane": lambda: self.toggle_zoom(),
            "next-tab": lambda: self._cycle(1),
            "prev-tab": lambda: self._cycle(-1),
            "move-tab-left": lambda: self.move_tab(-1),
            "move-tab-right": lambda: self.move_tab(1),
            "rename-tab": lambda: self.rename_tab(),
            "duplicate-tab": self._duplicate,
            "detach-tab": self._detach,
            "copy": lambda: self._pane(lambda p: p.copy()),
            "paste": lambda: self._pane(lambda p: p.paste()),
            "select-all": lambda: self._pane(lambda p: p.term.select_all()),
            "find": lambda: self._pane(lambda p: p.show_search()),
            "zoom-in": lambda: self._pane(lambda p: p.zoom(0.1)),
            "zoom-out": lambda: self._pane(lambda p: p.zoom(-0.1)),
            "zoom-reset": lambda: self._pane(lambda p: p.zoom(0)),
            "palette": lambda: self.show_palette(),
            "quick-select": self.quick_select,
            "preferences": lambda: self.app.show_prefs(self),
            "edit-profiles": lambda: self.app.show_prefs(self, "profiles"),
            "next-theme": self._next_theme,
            "toggle-starfield": lambda: self.s.__setitem__("starfield", not self.s["starfield"]),
            "broadcast": self._toggle_broadcast,
            "fullscreen": lambda: self.unfullscreen() if self.is_fullscreen() else self.fullscreen(),
            "clear": lambda: self._pane(lambda p: p.clear()),
            "jump-prev-prompt": lambda: self._pane(lambda p: p.jump_prompt(-1)),
            "jump-next-prompt": lambda: self._pane(lambda p: p.jump_prompt(1)),
            "open-cwd": lambda: self._pane(lambda p: Gtk.FileLauncher.new(Gio.File.new_for_path(p.cwd)).launch(self, None, None, None)),
            "save-output": self._save_output,
            "open-link": lambda: self._pane(lambda p: p.ctx_link and p.open_link(p.ctx_link)),
            "copy-link": self._copy_link,
            "show-keys": lambda: self.show_palette("> "),
            "about": self._about,
        }
        for i in range(1, 10):
            A[f"tab-{i}"] = (lambda n: lambda: self._goto(n))(i)
        for name, fn in A.items():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda _a, _p, f=fn: f())
            self.add_action(a)
        a = Gio.SimpleAction.new("new-tab-profile", GLib.VariantType.new("s"))
        a.connect("activate", lambda _a, v: self.new_tab(profile=self.s.profile(v.get_string())))
        self.add_action(a)
        self.actions_map = A

        # Fallback key handling for when the app-level accels lose to the terminal
        kc = Gtk.EventControllerKey()
        kc.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        kc.connect("key-pressed", self._on_key)
        self.add_controller(kc)
        self._reload_shortcuts()

    def _reload_shortcuts(self):
        self._shortcuts = []
        for action, accel in keys.all_accels(self.s).items():
            if not accel:
                continue
            ok, kv, mods = Gtk.accelerator_parse(accel)
            if ok and kv:
                self._shortcuts.append((Gdk.keyval_to_lower(kv), mods, action))

    def _on_key(self, c, keyval, code, state):
        if self.quick is not None:
            return self.quick.key(keyval, state)
        mask = Gtk.accelerator_get_default_mod_mask()
        st = state & mask
        kv = Gdk.keyval_to_lower(keyval)
        # Ctrl+Shift+letter arrives as uppercase; ctrl+plus might come as equal/KP_Add
        aliases = {Gdk.KEY_equal: Gdk.KEY_plus, Gdk.KEY_KP_Add: Gdk.KEY_plus, Gdk.KEY_KP_Subtract: Gdk.KEY_minus,
                   Gdk.KEY_ISO_Left_Tab: Gdk.KEY_Tab}
        for want_kv, want_mods, action in self._shortcuts:
            if (kv == want_kv or aliases.get(kv) == want_kv) and (st == want_mods or
                                                                  (want_kv == Gdk.KEY_plus and st & ~Gdk.ModifierType.SHIFT_MASK == want_mods)):
                focus = self.get_focus()
                # don't steal ordinary editing keys from text entries (rename box, palette, search)
                if isinstance(focus, Gtk.Text) and action in ("copy", "paste", "select-all", "zoom-in", "zoom-out"):
                    return False
                self.actions_map[action]()
                return True
        return False

    def _pane(self, fn):
        p = self.current_pane()
        if p:
            fn(p)

    def _cycle(self, d):
        t = self.current_tab()
        if t and len(self.tabs) > 1:
            self.select_tab(self.tabs[(self.tabs.index(t) + d) % len(self.tabs)])

    def _goto(self, n):
        if n == 9 and self.tabs:
            self.select_tab(self.tabs[-1])
        elif n <= len(self.tabs):
            self.select_tab(self.tabs[n - 1])

    def _close_others(self):
        cur = self.current_tab()
        for t in list(self.tabs):
            if t is not cur:
                self.close_tab(t, force=True)

    def _duplicate(self):
        p = self.current_pane()
        if p:
            self.new_tab(profile=p.profile, cwd=p.cwd)

    def _detach(self):
        t = self.current_tab()
        if not t or len(self.tabs) < 2:
            return
        state = self.tab_state(t)
        self.close_tab(t, force=True)
        self.app.new_window(restore=[state])

    def _next_theme(self):
        names = [t["name"] for t in themes.all_themes()]
        cur = self.s["theme"]
        nxt = names[(names.index(cur) + 1) % len(names)] if cur in names else names[0]
        self.s["theme"] = nxt
        self.toast(f"Theme: {nxt}")

    def _toggle_broadcast(self):
        t = self.current_tab()
        if not t:
            return
        if len(t.panes()) < 2:
            self.toast("Broadcast needs split panes — Ctrl+Shift+D to split")
            return
        t.broadcast = not t.broadcast
        self._mark_split(t)
        self._refresh_tab(t)
        self.toast("Broadcasting keystrokes to every pane in this tab" if t.broadcast else "Broadcast off")

    def _copy_link(self):
        p = self.current_pane()
        if p and p.ctx_link:
            self.get_clipboard().set(p.ctx_link[1])

    def _save_output(self):
        p = self.current_pane()
        if not p:
            return
        dlg = Gtk.FileDialog(title="Save terminal output", initial_name=f"terminal-{time.strftime('%Y%m%d-%H%M%S')}.txt")

        def done(d, res):
            try:
                f = d.save_finish(res)
            except GLib.Error:
                return
            with open(f.get_path(), "w") as fh:
                fh.write(p.all_text())
            self.toast(f"Saved {os.path.basename(f.get_path())}")
        dlg.save(self, None, done)

    def _about(self):
        from . import VERSION, REPO
        a = Gtk.AboutDialog(transient_for=self, modal=True, program_name="Interstellar Terminal", version=VERSION,
                            logo_icon_name="interstellar", license_type=Gtk.License.MIT_X11,
                            website=f"https://github.com/{REPO}",
                            comments="A terminal that's out of this world.\nTabs, splits, themes, a starfield and full GUI customization.")
        a.present()

    # ================================================================== settings / theme
    def apply_settings(self, key):
        if key in ("theme", "*"):
            self.backdrop.set_theme(themes.get(self.app.theme_name()))
        if key in ("theme", "ui_style", "*"):
            self.apply_liquid()
        elif key.startswith("glass_") and self.glass is not None:
            if key == "glass_follow":
                self.glass._schedule()
            self.glass.refresh()
        if key in ("glass_stars", "starfield"):
            self.backdrop.refresh()
        if key in ("starfield", "starfield_motion", "starfield_density", "opacity", "background_image",
                   "background_dim", "*"):
            self.backdrop.refresh()
        if key in ("tab_position", "*"):
            self.apply_layout()
        if key in ("hide_single_tab", "*"):
            self._update_tabstrip_visibility()
        if key in ("profiles", "*"):
            self._refresh_profile_menu()
        if key in ("keybindings", "*"):
            self._reload_shortcuts()
        for t in self.tabs:
            for p in t.panes():
                if key == "profiles":
                    p.profile = self.s.profile(p.profile_name)
                p.apply_settings()

    # ================================================================== session
    def tab_state(self, tab):
        def ser(w):
            if isinstance(w, Pane):
                return {"pane": w.state()}
            if isinstance(w, Gtk.Paned):
                size = w.get_height() if w.get_orientation() == Gtk.Orientation.VERTICAL else w.get_width()
                return {"split": "v" if w.get_orientation() == Gtk.Orientation.VERTICAL else "h",
                        "ratio": round(w.get_position() / size, 3) if size else 0.5,
                        "a": ser(w.get_start_child()), "b": ser(w.get_end_child())}
            return None
        return {"title": tab.title, "tree": ser(tab.root.get_first_child())}

    def state(self):
        return {"tabs": [self.tab_state(t) for t in self.tabs],
                "current": self.tabs.index(self.current_tab()) if self.current_tab() in self.tabs else 0}

    def restore_tab(self, st):
        tab = Tab(self)
        tab.title = st.get("title", "")
        ratios = []

        def build(node):
            if not node:
                return None
            if "pane" in node:
                ps = node["pane"]
                p = Pane(self, profile=self.s.profile(ps.get("profile")), cwd=ps.get("cwd"))
                p.custom_title = ps.get("title", "")
                tab.focused = tab.focused or p
                return p
            paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL if node.get("split") == "v" else Gtk.Orientation.HORIZONTAL,
                              shrink_start_child=False, shrink_end_child=False)
            paned.add_css_class("istl")
            a, b = build(node.get("a")), build(node.get("b"))
            paned.set_start_child(a)
            paned.set_end_child(b)
            ratios.append((paned, float(node.get("ratio", 0.5))))
            return paned
        w = build(st.get("tree"))
        if w is None:
            return
        tab.root.append(w)
        self._add_tab(tab, select=True, index=len(self.tabs))
        self._mark_split(tab)

        for paned, r in ratios:
            self._half(paned, 0, r)

    # ================================================================== window lifecycle
    def _poll(self):
        for t in self.tabs:
            for p in t.panes():
                p.poll()
            self._refresh_tab(t)
        return True

    def _on_active(self, *_):
        t = self.current_tab()
        if self.is_active() and t:
            t.dot.set_visible(False)
            try:
                self.app.withdraw_notification(f"done-{t.id}")
            except Exception:
                pass

    def _on_close_request(self, *_):
        if getattr(self, "_really_close", False) or not self.s["confirm_close"]:
            return self._finish_close()
        running = [p for t in self.tabs for p in t.panes() if p.running_command()]
        if running:
            names = ", ".join(sorted({p.proc_name for p in running if p.proc_name})) or "Programs"
            def go():
                self._really_close = True
                self.close()
            self._confirm("Close Interstellar?", f"{names} still running.", "Close Window", go)
            return True
        return self._finish_close()

    def _finish_close(self):
        if not self.quake and not self.is_maximized() and not self.is_fullscreen():
            w, h = self.get_default_size()
            if w > 200 and h > 150:
                self.s.set_quiet("width", w)
                self.s.set_quiet("height", h)
        self.app.window_closing(self)
        GLib.source_remove(self._poll_id)
        if self.glass is not None:
            self.glass.shutdown()
        for t in self.tabs:
            for p in t.panes():
                self._kill(p)
        return False

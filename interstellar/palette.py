"""Command palette (Ctrl+Shift+P): every action, theme (with live preview), profile, open tab
and common setting toggle — fuzzy-searchable from one box."""
from gi.repository import Gtk, Gdk, GLib

from . import keys, themes, icons


def fuzzy(q, text):
    """Subsequence match score (higher is better) or None."""
    if not q:
        return 0
    t = text.lower()
    q = q.lower()
    if q in t:
        return 1000 - t.index(q) * 2 - len(t) * 0.1
    i, score, last = 0, 0, -2
    for j, ch in enumerate(t):
        if i < len(q) and ch == q[i]:
            score += 8 if j == last + 1 else (5 if j == 0 or t[j - 1] in " :-_/" else 1)
            last = j
            i += 1
    return score if i == len(q) else None


def pretty_accel(a):
    if not a:
        return ""
    ok, kv, mods = Gtk.accelerator_parse(a)
    return Gtk.accelerator_get_label(kv, mods) if ok else a


class Palette(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.START, margin_top=14, width_request=560, visible=False)
        self.win = win
        self.s = win.s
        self.add_css_class("istl-float")
        self.entry = Gtk.SearchEntry(placeholder_text="Type a command, theme, profile or tab…  (theme:  >  tab:)")
        self.append(self.entry)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE)
        self.list.set_activate_on_single_click(True)
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                max_content_height=380)
        sw.set_child(self.list)
        self.append(sw)
        self.hint = Gtk.Label(label="↑↓ choose · Enter run · Esc close   —   themes preview live", xalign=0)
        self.hint.add_css_class("dim")
        self.append(self.hint)
        self.items = []
        self.saved_theme = None
        self.entry.connect("search-changed", lambda *_: self.refresh())
        self.entry.connect("activate", lambda *_: self.run_selected())
        self.entry.connect("stop-search", lambda *_: self.close(revert=True))
        self.list.connect("row-activated", lambda l, r: self.run(r.item))
        self.list.connect("row-selected", self._selected)
        kc = Gtk.EventControllerKey()
        kc.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        kc.connect("key-pressed", self._key)
        self.entry.add_controller(kc)

    # ------------------------------------------------------------------ items
    def _collect(self):
        W, S = self.win, self.s
        items = []
        accels = keys.all_accels(S)
        for a, label, _ in keys.ACTIONS:
            items.append(("action", label, pretty_accel(accels.get(a)), a))
        items += [("action", "Close tab", "", "close-tab"), ("action", "Duplicate tab", "", "duplicate-tab"),
                  ("action", "Move tab to new window", "", "detach-tab"), ("action", "Close other tabs", "", "close-others"),
                  ("action", "About Interstellar", "", "about")]
        for th in themes.all_themes():
            tag = "✦ space" if th.get("space") else ("custom" if th.get("custom") else "")
            items.append(("theme", f"Theme: {th['name']}", ("● current " if th["name"] == S["theme"] else "") + tag, th["name"]))
        for p in S["profiles"]:
            items.append(("profile", f"New tab: {p.get('name')}", p.get("command") or "shell", p.get("name")))
        for i, t in enumerate(W.tabs):
            items.append(("tab", f"Tab {i + 1}: {t.display_title()}", "", t))
        toggles = [
            ("starfield", "Starfield"), ("copy_on_select", "Copy on select"), ("safe_paste", "Safe paste"),
            ("scroll_on_output", "Scroll on output"), ("hide_single_tab", "Hide tab bar with one tab"),
            ("notify_finished", "Notify when long commands finish"), ("bold_is_bright", "Bold is bright"),
            ("confirm_close", "Confirm before closing"),
        ]
        for k, label in toggles:
            items.append(("toggle", f"Toggle: {label}", "on" if S[k] else "off", k))
        for k, vals in (("cursor_shape", ("block", "ibeam", "underline")), ("starfield_motion", ("drift", "twinkle", "still")),
                        ("ui_style", ("glass", "solid", "minimal")), ("tab_position", ("top", "bottom")),
                        ("cursor_blink", ("on", "off", "system")), ("bell", ("visual", "audible", "none"))):
            for v in vals:
                items.append(("set", f"{k.replace('_', ' ').capitalize()}: {v}", "● current" if S[k] == v else "", (k, v)))
        for op in (1.0, 0.95, 0.9, 0.85, 0.8, 0.7):
            items.append(("set", f"Opacity: {int(op * 100)}%", "● current" if abs(S["opacity"] - op) < 0.01 else "", ("opacity", op)))
        return items

    def refresh(self):
        q = self.entry.get_text().strip()
        kind = None
        low = q.lower()
        for prefix, k in (("theme:", "theme"), ("tab:", "tab"), (">", "action"), ("profile:", "profile"), ("set:", "set")):
            if low.startswith(prefix):
                kind, q = k, q[len(prefix):].strip()
                break
        scored = []
        for it in self.items:
            if kind and it[0] != kind and not (kind == "set" and it[0] == "toggle"):
                continue
            hay = it[1] if not kind else it[1].split(":", 1)[-1]
            sc = fuzzy(q, hay)
            if sc is not None:
                scored.append((-sc, len(scored), it))
        scored.sort()
        child = self.list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.list.remove(child)
            child = nxt
        for _, _, it in scored[:80]:
            row = Gtk.ListBoxRow()
            row.item = it
            box = Gtk.Box(spacing=10)
            icon = {"action": "bolt", "theme": "planet", "profile": "terminal", "tab": "tab",
                    "toggle": "check", "set": "settings"}[it[0]]
            img = icons.Icon(icon, 16)
            img.add_css_class("accent")
            box.append(img)
            box.append(Gtk.Label(label=it[1], xalign=0, hexpand=True, ellipsize=3))
            if it[2]:
                k = Gtk.Label(label=it[2])
                k.add_css_class("kbd" if it[0] == "action" else "dim")
                box.append(k)
            row.set_child(box)
            self.list.append(row)
        first = self.list.get_row_at_index(0)
        if first:
            self.list.select_row(first)

    # ------------------------------------------------------------------ open / close
    def open(self, prefill=""):
        self.items = self._collect()
        self.saved_theme = self.s["theme"]
        self.set_visible(True)
        self.entry.set_text(prefill)
        self.refresh()
        self.entry.grab_focus()
        self.entry.set_position(-1)

    def close(self, revert=False):
        if not self.get_visible():
            return
        self.set_visible(False)
        if revert:
            self.win.app.preview_theme(None)
        p = self.win.current_pane()
        if p:
            p.term.grab_focus()

    def _selected(self, lb, row):
        if row is None or not self.get_visible():
            return
        it = row.item
        if it[0] == "theme":
            self.win.app.preview_theme(it[3])
        else:
            self.win.app.preview_theme(None)

    def _key(self, c, kv, code, state):
        if kv in (Gdk.KEY_Down, Gdk.KEY_Up, Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
            row = self.list.get_selected_row()
            i = row.get_index() if row else -1
            step = {Gdk.KEY_Down: 1, Gdk.KEY_Up: -1, Gdk.KEY_Page_Down: 8, Gdk.KEY_Page_Up: -8}[kv]
            n = 0
            while self.list.get_row_at_index(n):
                n += 1
            if n:
                j = max(0, min(n - 1, i + step))
                r = self.list.get_row_at_index(j)
                self.list.select_row(r)
                adj = self.list.get_parent().get_vadjustment() if hasattr(self.list.get_parent(), "get_vadjustment") else None
                ok, b = r.compute_bounds(self.list)
                sw = self.list.get_ancestor(Gtk.ScrolledWindow)
                if ok and sw:
                    adj = sw.get_vadjustment()
                    if b.origin.y < adj.get_value():
                        adj.set_value(b.origin.y)
                    elif b.origin.y + b.size.height > adj.get_value() + adj.get_page_size():
                        adj.set_value(b.origin.y + b.size.height - adj.get_page_size())
            return True
        if kv == Gdk.KEY_Escape:
            self.close(revert=True)
            return True
        return False

    def run_selected(self):
        row = self.list.get_selected_row()
        if row:
            self.run(row.item)

    def run(self, it):
        kind, label, _, val = it
        self.win.app.preview_theme(None)
        self.close()
        W, S = self.win, self.s
        if kind == "action":
            fn = W.actions_map.get(val)
            if fn:
                GLib.idle_add(lambda: (fn(), False)[1])
        elif kind == "theme":
            S["theme"] = val
            W.toast(f"Theme: {val}")
        elif kind == "profile":
            W.new_tab(profile=S.profile(val))
        elif kind == "tab":
            if val in W.tabs:
                W.select_tab(val)
        elif kind == "toggle":
            S[val] = not S[val]
            W.toast(f"{label.split(': ', 1)[1]}: {'on' if S[val] else 'off'}")
        elif kind == "set":
            k, v = val
            S[k] = v
            W.toast(label)

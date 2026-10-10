"""Quick select (Ctrl+Shift+Space): every URL, path, git hash, IP, UUID or e-mail on screen gets a
letter hint. Type the letters to copy it; hold Shift on the last letter to paste it at the prompt
instead; Ctrl+letter opens it."""
import re

from gi.repository import Gtk, Gdk, Pango, PangoCairo

from .chrome import _rgb
from .pane import cell_width
from . import themes

PATTERNS = [
    ("url", r"(?:https?|ftp|file|ssh|git)://[^\s<>\"'`()\[\]{}]*[^\s<>\"'`()\[\]{}.,;:!?]"),
    ("email", r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    ("uuid", r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    ("fileline", r"(?:~|\.{1,2})?/?(?:[\w.@+-]+/)*[\w@+-][\w.@+-]*\.[A-Za-z0-9]{1,10}:\d+(?::\d+)?"),
    ("path", r"(?<![\w/])(?:~|\.{1,2})?/(?:[\w.@+-]+/)*[\w.@+-]+/?"),
    ("ip", r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b"),
    ("hash", r"\b[0-9a-f]{7,64}\b"),
    ("file", r"\b[\w@+-][\w.@+-]*\.(?:c|h|cc|cpp|hpp|py|rs|go|js|ts|tsx|jsx|java|kt|rb|php|sh|md|txt|json|toml|ya?ml|lua|zig|conf|log|html|css)\b"),
    ("number", r"\b\d{4,}\b"),
]
ALPHABET = "asdfghjklqwertyuiopzxcvbnm"


def make_hints(n):
    if n <= len(ALPHABET):
        return list(ALPHABET[:n])
    out = []
    for a in ALPHABET:
        for b in ALPHABET:
            out.append(a + b)
            if len(out) == n:
                return out
    return out


class QuickSelect(Gtk.DrawingArea):
    def __init__(self, win, pane):
        super().__init__(hexpand=True, vexpand=True, can_target=False)
        self.win, self.pane = win, pane
        self.typed = ""
        self.matches = []
        self.set_draw_func(self._draw)

    def start(self):
        p = self.pane
        rows, top = p.visible_rows()
        taken = {}
        found = []
        for r, text in rows:
            for kind, pat in PATTERNS:
                for m in re.finditer(pat, text):
                    s, e = m.span()
                    if any(not (e <= a or s >= b) for a, b in taken.get(r, [])):
                        continue
                    if kind == "number" and len(m.group()) < 5:
                        continue
                    taken.setdefault(r, []).append((s, e))
                    col = sum(cell_width(c) for c in text[:s])
                    width = sum(cell_width(c) for c in m.group())
                    found.append([kind, m.group(), r - top, col, width])
        if not found:
            self.win.toast("Nothing to quick-select on screen")
            return
        # closest to the bottom (most recent output) gets the shortest hints
        found.sort(key=lambda f: (-f[2], f[3]))
        hints = make_hints(len(found))
        self.matches = [f + [h] for f, h in zip(found, hints)]
        p.add_overlay(self)
        self.win.quick = self
        self.win.toast("Type a hint to copy · Shift = paste · Ctrl = open · Esc = cancel", 2600)

    def stop(self):
        if self.get_parent():
            self.pane.remove_overlay(self)
        self.win.quick = None
        self.pane.term.grab_focus()

    def key(self, kv, state):
        if kv == Gdk.KEY_Escape:
            self.stop()
            return True
        if kv in (Gdk.KEY_BackSpace,):
            self.typed = self.typed[:-1]
            self.queue_draw()
            return True
        ch = chr(Gdk.keyval_to_unicode(kv) or 0)
        if not ch.isalpha():
            return True
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        self.typed += ch.lower()
        hits = [m for m in self.matches if m[5].startswith(self.typed)]
        if not hits:
            self.typed = ""
        elif len(hits) == 1 and hits[0][5] == self.typed:
            kind, text = hits[0][0], hits[0][1]
            self.stop()
            if ctrl:
                self.pane.open_link(("url" if kind == "url" else "fileline" if kind in ("fileline", "path", "file") else "url", text))
            elif shift:
                self.pane.term.paste_text(text)
            else:
                self.win.get_clipboard().set(text)
                self.win.toast(f"Copied {text if len(text) < 60 else text[:57] + '…'}")
            return True
        self.queue_draw()
        return True

    def _draw(self, area, cr, w, h):
        p = self.pane
        t = p.term
        th = themes.get(self.win.app.theme_name())
        cw, ch = t.get_char_width(), t.get_char_height()
        ok, b = t.compute_bounds(p)
        ox, oy = (b.origin.x, b.origin.y) if ok else (0, 0)
        pad = self.win.s["padding"]
        ox += pad
        oy += pad
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.paint()
        ar, ag, ab = [c / 255 for c in _rgb(th["accent"])]
        layout = PangoCairo.create_layout(cr)
        fd = Pango.FontDescription.from_string(self.win.s["font"])
        fd.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(fd)
        for kind, text, row, col, width, hint in self.matches:
            if not hint.startswith(self.typed):
                continue
            x, y = ox + col * cw, oy + row * ch
            cr.set_source_rgba(ar, ag, ab, 0.18)
            cr.rectangle(x, y, width * cw, ch)
            cr.fill()
            cr.set_source_rgba(ar, ag, ab, 0.9)
            cr.rectangle(x, y + ch - 2, width * cw, 2)
            cr.fill()
            layout.set_text(hint.upper(), -1)
            lw, lh = layout.get_pixel_size()
            cr.set_source_rgba(ar, ag, ab, 1)
            _round(cr, x - 2, y, lw + 6, ch, 3)
            cr.fill()
            fg = (0, 0, 0) if themes.luminance(th["accent"]) > 0.5 else (1, 1, 1)
            cr.set_source_rgb(*fg)
            cr.move_to(x + 1, y + (ch - lh) / 2)
            PangoCairo.show_layout(cr, layout)


def _round(cr, x, y, w, h, r):
    import math
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()

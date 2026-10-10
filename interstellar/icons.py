"""Vector icons drawn with cairo: no icon theme or SVG loader needed, crisp at any scale, and they
take the widget's CSS colour (so hover / active styles apply)."""
import math

import cairo
from gi.repository import Gtk


def _p(cr, pts, close=False):
    cr.move_to(*pts[0])
    for pt in pts[1:]:
        cr.line_to(*pt)
    if close:
        cr.close_path()


def _rrect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def _circle(cr, x, y, r):
    cr.new_sub_path()
    cr.arc(x, y, r, 0, math.tau)


def _plus(cr):
    _p(cr, [(12, 5), (12, 19)]); _p(cr, [(5, 12), (19, 12)]); cr.stroke()


def _down(cr):
    _p(cr, [(7, 10), (12, 15), (17, 10)]); cr.stroke()


def _up(cr):
    _p(cr, [(7, 14), (12, 9), (17, 14)]); cr.stroke()


def _close(cr):
    _p(cr, [(7, 7), (17, 17)]); _p(cr, [(17, 7), (7, 17)]); cr.stroke()


def _search(cr):
    _circle(cr, 10.5, 10.5, 6); _p(cr, [(15, 15), (20, 20)]); cr.stroke()


def _menu(cr):
    for y in (7, 12, 17):
        _p(cr, [(5, y), (19, y)])
    cr.stroke()


def _planet(cr):
    _circle(cr, 12, 12, 5.5); cr.stroke()
    cr.save(); cr.translate(12, 12); cr.rotate(-0.42); cr.scale(1, 0.32)
    cr.new_sub_path(); cr.arc(0, 0, 10.5, math.radians(200), math.radians(340 + 360)); cr.restore()
    cr.stroke()


def _star(cr):
    pts = []
    for i in range(10):
        r = 8.5 if i % 2 == 0 else 3.4
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((12 + r * math.cos(a), 12.6 + r * math.sin(a)))
    _p(cr, pts, True); cr.fill_preserve(); cr.stroke()


def _sparkle(cr):
    cr.move_to(12, 3)
    for (x, y), (cx, cy) in (((21, 12), (13, 11)), ((12, 21), (13, 13)), ((3, 12), (11, 13)), ((12, 3), (11, 11))):
        cr.curve_to(cx, cy, cx, cy, x, y)
    cr.close_path(); cr.fill()


def _terminal(cr):
    _rrect(cr, 3, 4.5, 18, 15, 3); _p(cr, [(7, 9.5), (10, 12), (7, 14.5)]); _p(cr, [(12, 15), (16.5, 15)]); cr.stroke()


def _prompt(cr):
    _p(cr, [(5, 7), (11, 12), (5, 17)]); _p(cr, [(13, 17), (19, 17)]); cr.stroke()


def _grid(cr):
    _rrect(cr, 3.5, 4.5, 17, 15, 2.5); _p(cr, [(12, 4.5), (12, 19.5)]); _p(cr, [(12, 12), (20.5, 12)]); cr.stroke()


def _split_h(cr):
    _rrect(cr, 3.5, 4.5, 17, 15, 2.5); _p(cr, [(12, 4.5), (12, 19.5)]); cr.stroke()


def _split_v(cr):
    _rrect(cr, 3.5, 4.5, 17, 15, 2.5); _p(cr, [(3.5, 12), (20.5, 12)]); cr.stroke()


def _broadcast(cr):
    _circle(cr, 12, 12, 1.8); cr.fill()
    for r in (5, 8.5):
        cr.new_sub_path(); cr.arc(12, 12, r, math.radians(-50), math.radians(50)); cr.stroke()
        cr.new_sub_path(); cr.arc(12, 12, r, math.radians(130), math.radians(230)); cr.stroke()


def _play(cr):
    _p(cr, [(8, 5.5), (18, 12), (8, 18.5)], True); cr.fill_preserve(); cr.stroke()


def _gear(cr):
    n, ro, ri = 8, 9.2, 7.0
    for i in range(n * 2):
        a = i * math.pi / n
        r = ro if i % 2 == 0 else ri
        a1, a2 = a - math.pi / (n * 2.6), a + math.pi / (n * 2.6)
        (cr.move_to if i == 0 else cr.line_to)(12 + r * math.cos(a1), 12 + r * math.sin(a1))
        cr.line_to(12 + r * math.cos(a2), 12 + r * math.sin(a2))
    cr.close_path(); _circle(cr, 12, 12, 2.8); cr.stroke()


def _check(cr):
    _p(cr, [(5, 12.5), (10, 17), (19, 7.5)]); cr.stroke()


def _bolt(cr):
    _p(cr, [(13, 3), (6, 13.5), (11.5, 13.5), (10.5, 21), (18, 10), (12.5, 10)], True); cr.fill_preserve(); cr.stroke()


def _tab(cr):
    _p(cr, [(3.5, 19.5), (3.5, 6.5), (11, 6.5), (13, 9.5), (20.5, 9.5), (20.5, 19.5)], True); cr.stroke()


def _palette(cr):
    _rrect(cr, 3.5, 5, 17, 14, 3); _p(cr, [(7, 9.5), (17, 9.5)]); _p(cr, [(7, 13), (14, 13)]); cr.stroke()


def _keyboard(cr):
    _rrect(cr, 2.5, 6, 19, 12, 2.5); cr.stroke()
    for x in (6, 9.3, 12.6, 15.9):
        _circle(cr, x + 0.6, 10, 0.9); cr.fill()
    _p(cr, [(8, 14.5), (16, 14.5)]); cr.stroke()


def _image(cr):
    _rrect(cr, 3.5, 4.5, 17, 15, 2.5); cr.stroke()
    _p(cr, [(4, 17), (9.5, 11.5), (13, 15), (15.5, 12.5), (20, 17)]); cr.stroke()
    _circle(cr, 15.5, 8.5, 1.5); cr.fill()


def _profile(cr):
    _circle(cr, 12, 8.5, 3.6); cr.stroke()
    cr.new_sub_path(); cr.arc(12, 21, 7.5, math.pi, 2 * math.pi); cr.stroke()


def _code(cr):
    _p(cr, [(8, 7), (3.5, 12), (8, 17)]); _p(cr, [(16, 7), (20.5, 12), (16, 17)]); _p(cr, [(13.5, 5), (10.5, 19)]); cr.stroke()


def _brush(cr):
    _p(cr, [(19.5, 4.5), (10.5, 13.5)]); cr.stroke()
    cr.move_to(10.5, 13.5); cr.curve_to(6, 12, 4, 16, 4.5, 19.5); cr.curve_to(8, 20, 12, 18.5, 10.5, 13.5)
    cr.fill_preserve(); cr.stroke()


def _zoom(cr):
    _p(cr, [(4, 9), (4, 4), (9, 4)]); _p(cr, [(15, 4), (20, 4), (20, 9)])
    _p(cr, [(20, 15), (20, 20), (15, 20)]); _p(cr, [(9, 20), (4, 20), (4, 15)]); cr.stroke()


ICONS = {"plus": _plus, "down": _down, "up": _up, "close": _close, "search": _search, "menu": _menu,
         "planet": _planet, "star": _star, "sparkle": _sparkle, "terminal": _terminal, "prompt": _prompt,
         "grid": _grid, "split-h": _split_h, "split-v": _split_v, "broadcast": _broadcast, "play": _play,
         "settings": _gear, "check": _check, "bolt": _bolt, "tab": _tab, "palette": _palette,
         "keyboard": _keyboard, "image": _image, "profile": _profile, "code": _code, "brush": _brush,
         "zoom": _zoom}


def draw_icon(cr, name, size, rgba, width=1.8):
    fn = ICONS.get(name)
    if not fn:
        return
    cr.save()
    s = size / 24.0
    cr.scale(s, s)
    cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    fn(cr)
    cr.restore()


class Icon(Gtk.DrawingArea):
    def __init__(self, name, size=16):
        super().__init__(can_target=False, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        self.name, self.size = name, size
        self.set_content_width(size)
        self.set_content_height(size)
        self.add_css_class("istl-icon")
        self.set_draw_func(self._draw)

    def set_icon(self, name):
        if name != self.name:
            self.name = name
            self.queue_draw()

    def _draw(self, area, cr, w, h):
        cr.translate((w - self.size) / 2, (h - self.size) / 2)
        draw_icon(cr, self.name, self.size, self.get_color())


def button(name, tooltip=None, size=16, label=None, cls=None):
    b = Gtk.Button(tooltip_text=tooltip)
    if label:
        box = Gtk.Box(spacing=6)
        box.append(Icon(name, size))
        box.append(Gtk.Label(label=label))
        b.set_child(box)
    else:
        b.set_child(Icon(name, size))
    if cls:
        b.add_css_class(cls)
    return b


def menu_button(name, tooltip=None, size=16):
    b = Gtk.MenuButton(tooltip_text=tooltip)
    b.set_child(Icon(name, size))
    return b

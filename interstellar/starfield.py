"""The window backdrop: theme background (with opacity), an optional background image,
a soft nebula glow and an animated, parallax starfield with the odd shooting star.

It is one widget behind the whole window, so the starfield flows continuously across split panes.
"""
import math, random, time

import cairo
from gi.repository import Gtk, GLib

from .chrome import _rgb

try:
    from gi.repository import GdkPixbuf, Gdk
except ImportError:  # pragma: no cover
    GdkPixbuf = None

STAR_TINTS = [(1, 1, 1), (1, 1, 1), (1, 1, 1), (0.8, 0.88, 1.0), (1.0, 0.92, 0.78), (1.0, 0.8, 0.8)]


class Backdrop(Gtk.DrawingArea):
    FPS = 30

    def __init__(self, settings):
        super().__init__()
        self.s = settings
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_can_target(False)
        self.set_can_focus(False)
        self.theme = None
        self.rng = random.Random(7)
        self.stars = []
        self.meteors = []
        self.t0 = time.monotonic()
        self.last = 0.0
        self._tick = None
        self._cache = None       # (w, h, key) -> surface of bg + nebula + image
        self._img = None
        self._img_path = None
        self.paused = False
        self.liquid = False      # Liquid Glass draws the window; we only add stars on top of it
        self.set_draw_func(self._draw)
        self._make_stars()
        self.connect("map", lambda *_: self._sync_anim())
        self.connect("unmap", lambda *_: self._stop())

    # ------------------------------------------------------------------ public
    def set_theme(self, theme):
        self.theme = theme
        self._cache = None
        self._sync_anim()
        self.queue_draw()

    def refresh(self):
        self._cache = None
        self._make_stars()
        self._sync_anim()
        self.queue_draw()

    def set_liquid(self, on):
        if on != self.liquid:
            self.liquid = on
            self._cache = None
            self._sync_anim()
            self.queue_draw()

    def _stars_on(self):
        return self.s["starfield"] and (not self.liquid or self.s["glass_stars"])

    def set_paused(self, paused):
        self.paused = paused
        self._sync_anim()

    # ------------------------------------------------------------------ internals
    def _make_stars(self):
        n = int(260 * max(0.1, float(self.s["starfield_density"] or 1)))
        r = self.rng
        self.stars = []
        for _ in range(n):
            layer = r.choices([0, 1, 2], [0.62, 0.28, 0.10])[0]
            self.stars.append([r.random(), r.random(), (0.45, 0.85, 1.4)[layer] * r.uniform(0.7, 1.25),
                               r.uniform(0.25, 1.0), layer, r.uniform(0, math.tau), r.uniform(0.6, 2.2),
                               r.choice(STAR_TINTS)])

    def _animated(self):
        return (self._stars_on() and self.s["starfield_motion"] != "still" and not self.paused
                and self.get_mapped())

    def _sync_anim(self):
        if self._animated() and self._tick is None:
            self._tick = self.add_tick_callback(self._on_tick)
        elif not self._animated():
            self._stop()

    def _stop(self):
        if self._tick is not None:
            self.remove_tick_callback(self._tick)
            self._tick = None

    def _on_tick(self, widget, clock):
        now = time.monotonic()
        if now - self.last >= 1.0 / self.FPS:
            self.last = now
            if self.s["starfield_motion"] == "drift" and self.rng.random() < 0.004 and len(self.meteors) < 2:
                self.meteors.append([self.rng.uniform(0.1, 1.0), self.rng.uniform(-0.05, 0.4), now,
                                     self.rng.uniform(0.7, 1.3)])
            self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _load_image(self):
        path = self.s["background_image"] or ""
        if path == self._img_path:
            return self._img
        self._img_path, self._img = path, None
        if not path or GdkPixbuf is None:
            return None
        try:
            self._img = GdkPixbuf.Pixbuf.new_from_file(path)
        except Exception:
            self._img = None
        return self._img

    def _base(self, w, h):
        th = self.theme
        if th is None:
            return None
        key = (w, h, th["bg"], th["accent"], self.s["opacity"], self.s["background_image"],
               self.s["background_dim"], self.s["starfield"], th.get("space"))
        if self._cache and self._cache[0] == key:
            return self._cache[1]
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(w, 1), max(h, 1))
        cr = cairo.Context(surf)
        op = max(0.0, min(1.0, float(self.s["opacity"] or 1.0)))
        r, g, b = [c / 255 for c in _rgb(th["bg"])]
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(r, g, b, op)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        img = self._load_image()
        if img is not None:
            iw, ih = img.get_width(), img.get_height()
            sc = max(w / iw, h / ih)
            cr.save()
            cr.translate((w - iw * sc) / 2, (h - ih * sc) / 2)
            cr.scale(sc, sc)
            Gdk.cairo_set_source_pixbuf(cr, img, 0, 0)
            cr.paint_with_alpha(op)
            cr.restore()
            cr.set_source_rgba(r, g, b, max(0.0, min(1.0, float(self.s["background_dim"]))) * op)
            cr.paint()
        elif self.s["starfield"] and _lum(th["bg"]) < 0.5:
            # nebula: two very soft glows in the accent colour + a cooler complement
            ar, ag, ab = [c / 255 for c in _rgb(th["accent"])]
            for (cx, cy, rad, col, a) in ((0.82, 0.18, 0.75, (ar, ag, ab), 0.10),
                                          (0.12, 0.92, 0.65, (0.35, 0.45, 1.0), 0.07),
                                          (0.55, 0.55, 0.35, (ar, ag, ab), 0.03)):
                grad = cairo.RadialGradient(cx * w, cy * h, 0, cx * w, cy * h, rad * max(w, h))
                grad.add_color_stop_rgba(0, *col, a * op)
                grad.add_color_stop_rgba(1, *col, 0)
                cr.set_source(grad)
                cr.paint()
            # a whisper of noise hides 8-bit gradient banding
            cr.set_source(_noise_pattern())
            cr.paint()
        self._cache = (key, surf)
        return surf

    def _draw(self, area, cr, w, h):
        if self.liquid:
            if self.theme is None or not self._stars_on():
                return
        else:
            base = self._base(w, h)
            if base is None:
                return
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.set_source_surface(base, 0, 0)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            if not self.s["starfield"]:
                return
        t = time.monotonic() - self.t0
        motion = self.s["starfield_motion"]
        light = self.theme and _lum(self.theme["bg"]) > 0.5
        op = max(0.2, float(self.s["opacity"] or 1.0))
        if self.liquid:
            op = 0.7      # stars drift inside the glass, a little softer
        for x, y, size, br, layer, ph, sp, tint in self.stars:
            if motion == "drift":
                x = (x - t * (0.0016, 0.0042, 0.0095)[layer]) % 1.0
                y = (y + t * (0.0004, 0.0010, 0.0022)[layer]) % 1.0
            a = br
            if motion != "still":
                a = br * (0.65 + 0.35 * math.sin(t * sp + ph))
            if light:
                cr.set_source_rgba(0.2, 0.22, 0.35, a * 0.35 * op)
            else:
                cr.set_source_rgba(*tint, a * op)
            px, py = x * w, y * h
            if size > 1.2 and not light:
                # bright star: soft halo + cross glint
                g = cairo.RadialGradient(px, py, 0, px, py, size * 3.2)
                g.add_color_stop_rgba(0, *tint, a * 0.55 * op)
                g.add_color_stop_rgba(1, *tint, 0)
                cr.set_source(g)
                cr.arc(px, py, size * 3.2, 0, math.tau)
                cr.fill()
                cr.set_source_rgba(*tint, a * op)
            cr.arc(px, py, size, 0, math.tau)
            cr.fill()
        now = time.monotonic()
        keep = []
        for m in self.meteors:
            x0, y0, born, speed = m
            age = (now - born) * speed
            if age > 1.1:
                continue
            keep.append(m)
            hx, hy = (x0 - age * 0.55) * w, (y0 + age * 0.33) * h
            tail = 0.16 * max(w, h)
            fade = math.sin(min(age / 1.1, 1.0) * math.pi)
            g = cairo.LinearGradient(hx, hy, hx + tail * 0.86, hy - tail * 0.5)
            g.add_color_stop_rgba(0, 1, 1, 1, 0.85 * fade * op)
            g.add_color_stop_rgba(1, 1, 1, 1, 0)
            cr.set_source(g)
            cr.set_line_width(1.6)
            cr.move_to(hx, hy)
            cr.line_to(hx + tail * 0.86, hy - tail * 0.5)
            cr.stroke()
        self.meteors = keep


_NOISE = None


def _noise_pattern():
    global _NOISE
    if _NOISE is None:
        n = 96
        stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, n)
        buf = bytearray(stride * n)
        rnd = random.Random(1)
        for y in range(n):
            for x in range(n):
                a = rnd.randint(0, 4)
                v = a if rnd.random() < 0.5 else 0      # premultiplied white or black
                i = y * stride + x * 4
                buf[i:i + 4] = bytes((v, v, v, a))
        surf = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, n, n, stride)
        pat = cairo.SurfacePattern(surf)
        pat.set_extend(cairo.EXTEND_REPEAT)
        pat.set_filter(cairo.FILTER_NEAREST)
        _NOISE = (pat, buf, surf)
    return _NOISE[0]


def _lum(h):
    r, g, b = _rgb(h)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255

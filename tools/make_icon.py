"""Renders the app icon (SVG + PNGs) with cairo:  python3 tools/make_icon.py"""
import math, os, random
import cairo

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "icons", "hicolor")


def rrect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def draw(cr, S, detail=True):
    cr.scale(S / 256, S / 256)
    # tile
    rrect(cr, 16, 16, 224, 224, 52)
    g = cairo.LinearGradient(16, 16, 240, 240)
    g.add_color_stop_rgb(0, 0.10, 0.06, 0.19)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.04)
    cr.set_source(g)
    cr.fill_preserve()
    cr.save()
    cr.clip()
    # nebula glows
    for cx, cy, r, col, a in ((190, 60, 150, (1.0, 0.42, 0.84), 0.35), (60, 210, 140, (0.36, 0.55, 1.0), 0.28)):
        rg = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
        rg.add_color_stop_rgba(0, *col, a)
        rg.add_color_stop_rgba(1, *col, 0)
        cr.set_source(rg)
        cr.paint()
    if detail:
        rnd = random.Random(11)
        for _ in range(38):
            x, y = rnd.uniform(20, 236), rnd.uniform(20, 236)
            cr.set_source_rgba(1, 1, 1, rnd.uniform(0.35, 0.95))
            cr.arc(x, y, rnd.uniform(0.7, 1.9), 0, math.tau)
            cr.fill()
    # back half of the ring
    cr.save()
    cr.translate(128, 132)
    cr.rotate(-0.38)
    cr.scale(1, 0.30)
    cr.set_line_width(16)
    cr.set_source_rgba(1.0, 0.82, 0.55, 0.9)
    cr.arc(0, 0, 98, math.pi, 2 * math.pi)
    cr.stroke()
    cr.restore()
    # planet
    pg = cairo.RadialGradient(104, 100, 6, 128, 132, 72)
    pg.add_color_stop_rgb(0, 1.0, 0.86, 0.55)
    pg.add_color_stop_rgb(0.55, 1.0, 0.56, 0.22)
    pg.add_color_stop_rgb(1, 0.62, 0.16, 0.36)
    cr.set_source(pg)
    cr.arc(128, 132, 62, 0, math.tau)
    cr.fill()
    # front half of the ring
    cr.save()
    cr.translate(128, 132)
    cr.rotate(-0.38)
    cr.scale(1, 0.30)
    cr.set_line_width(16)
    cr.set_source_rgba(1.0, 0.86, 0.62, 1.0)
    cr.arc(0, 0, 98, 0, math.pi)
    cr.stroke()
    cr.restore()
    # prompt on the planet
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.set_source_rgb(0.08, 0.04, 0.12)
    cr.set_line_width(13)
    cr.move_to(100, 108); cr.line_to(124, 128); cr.line_to(100, 148)
    cr.stroke()
    cr.move_to(134, 152); cr.line_to(160, 152)
    cr.stroke()
    # sparkle
    cr.set_source_rgb(1, 1, 1)
    cx, cy, r = 196, 62, 15
    cr.move_to(cx, cy - r)
    for (x, y) in ((cx + r, cy), (cx, cy + r), (cx - r, cy), (cx, cy - r)):
        cr.curve_to(cx, cy, cx, cy, x, y)
    cr.fill()
    cr.restore()
    # subtle rim
    rrect(cr, 16.5, 16.5, 223, 223, 52)
    cr.set_source_rgba(1, 1, 1, 0.10)
    cr.set_line_width(2)
    cr.stroke()


def main():
    os.makedirs(os.path.join(OUT, "scalable", "apps"), exist_ok=True)
    s = cairo.SVGSurface(os.path.join(OUT, "scalable", "apps", "interstellar.svg"), 256, 256)
    cr = cairo.Context(s)
    draw(cr, 256)
    s.finish()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        d = os.path.join(OUT, f"{size}x{size}", "apps")
        os.makedirs(d, exist_ok=True)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        draw(cairo.Context(surf), size, detail=size >= 48)
        surf.write_to_png(os.path.join(d, "interstellar.png"))
    print("icons written to", os.path.normpath(OUT))


if __name__ == "__main__":
    main()

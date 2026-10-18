"""Liquid Glass: the layer that sits behind the terminals and draws the window as a slab of curved glass
refracting your wallpaper.

* The shader (liquid.py) runs in a Gtk.GLArea. GL is called through libepoxy with ctypes, so there are no
  new dependencies (GTK 4 itself links libepoxy). If GL isn't available, a cairo version draws frosted
  glass without the refraction.
* The backdrop is the wallpaper of the monitor the window is on, found from swww / awww / hyprpaper /
  waypaper / swaybg, or the picture chosen in Preferences. With none, a soft aurora in the theme's colours.
* On Hyprland the window's position on screen comes from the IPC socket, so the glass bends the part of
  the wallpaper that is really behind it, and keeps doing so while you move it. Elsewhere the glass
  refracts the wallpaper as if the window sat in the top-left corner.
* The shader only runs when something changes (move, resize, a setting). Terminal output just recomposites.
"""
import ctypes, json, math, os, socket, time

import cairo
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib

from . import liquid, themes

# ===================================================================================== GL via epoxy
_c = ctypes
_SIG = {
    "glCreateShader": (_c.c_uint, [_c.c_uint]),
    "glShaderSource": (None, [_c.c_uint, _c.c_int, _c.POINTER(_c.c_char_p), _c.c_void_p]),
    "glCompileShader": (None, [_c.c_uint]),
    "glGetShaderiv": (None, [_c.c_uint, _c.c_uint, _c.POINTER(_c.c_int)]),
    "glGetShaderInfoLog": (None, [_c.c_uint, _c.c_int, _c.c_void_p, _c.c_char_p]),
    "glDeleteShader": (None, [_c.c_uint]),
    "glCreateProgram": (_c.c_uint, []),
    "glAttachShader": (None, [_c.c_uint, _c.c_uint]),
    "glLinkProgram": (None, [_c.c_uint]),
    "glGetProgramiv": (None, [_c.c_uint, _c.c_uint, _c.POINTER(_c.c_int)]),
    "glGetProgramInfoLog": (None, [_c.c_uint, _c.c_int, _c.c_void_p, _c.c_char_p]),
    "glDeleteProgram": (None, [_c.c_uint]),
    "glUseProgram": (None, [_c.c_uint]),
    "glGetUniformLocation": (_c.c_int, [_c.c_uint, _c.c_char_p]),
    "glUniform1f": (None, [_c.c_int, _c.c_float]),
    "glUniform2f": (None, [_c.c_int, _c.c_float, _c.c_float]),
    "glUniform3f": (None, [_c.c_int, _c.c_float, _c.c_float, _c.c_float]),
    "glUniform1i": (None, [_c.c_int, _c.c_int]),
    "glGenVertexArrays": (None, [_c.c_int, _c.POINTER(_c.c_uint)]),
    "glBindVertexArray": (None, [_c.c_uint]),
    "glDeleteVertexArrays": (None, [_c.c_int, _c.POINTER(_c.c_uint)]),
    "glGenTextures": (None, [_c.c_int, _c.POINTER(_c.c_uint)]),
    "glDeleteTextures": (None, [_c.c_int, _c.POINTER(_c.c_uint)]),
    "glBindTexture": (None, [_c.c_uint, _c.c_uint]),
    "glActiveTexture": (None, [_c.c_uint]),
    "glTexImage2D": (None, [_c.c_uint, _c.c_int, _c.c_int, _c.c_int, _c.c_int, _c.c_int, _c.c_uint, _c.c_uint,
                            _c.c_void_p]),
    "glTexParameteri": (None, [_c.c_uint, _c.c_uint, _c.c_int]),
    "glGenerateMipmap": (None, [_c.c_uint]),
    "glPixelStorei": (None, [_c.c_uint, _c.c_int]),
    "glDrawArrays": (None, [_c.c_uint, _c.c_int, _c.c_int]),
    "glClearColor": (None, [_c.c_float, _c.c_float, _c.c_float, _c.c_float]),
    "glClear": (None, [_c.c_uint]),
    "glDisable": (None, [_c.c_uint]),
}
GL_FRAGMENT_SHADER, GL_VERTEX_SHADER = 0x8B30, 0x8B31
GL_COMPILE_STATUS, GL_LINK_STATUS = 0x8B81, 0x8B82
GL_TEXTURE_2D, GL_TEXTURE0 = 0x0DE1, 0x84C0
GL_RGBA, GL_RGBA8, GL_UNSIGNED_BYTE = 0x1908, 0x8058, 0x1401
GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER = 0x2801, 0x2800
GL_LINEAR, GL_LINEAR_MIPMAP_LINEAR = 0x2601, 0x2703
GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE = 0x2802, 0x2803, 0x812F
GL_UNPACK_ROW_LENGTH, GL_UNPACK_ALIGNMENT = 0x0CF2, 0x0CF5
GL_TRIANGLES, GL_COLOR_BUFFER_BIT, GL_BLEND = 0x0004, 0x4000, 0x0BE2


class _GL:
    _fns = None

    @classmethod
    def load(cls):
        if cls._fns is not None:
            return cls._fns
        lib = None
        for name in ("libepoxy.so.0", "libepoxy.so"):
            try:
                lib = _c.CDLL(name)
                break
            except OSError:
                continue
        if lib is None:
            raise RuntimeError("libepoxy not found")
        fns = {}
        for name, (res, args) in _SIG.items():
            addr = _c.c_void_p.in_dll(lib, "epoxy_" + name).value
            if not addr:
                raise RuntimeError(f"{name} unavailable")
            fns[name] = _c.CFUNCTYPE(res, *args)(addr)
        cls._fns = fns
        return fns


# ===================================================================================== Hyprland
class _Hypr:
    def __init__(self):
        self.sock = None
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        if sig:
            for base in (os.path.join(os.environ.get("XDG_RUNTIME_DIR", ""), "hypr", sig), f"/tmp/hypr/{sig}"):
                if os.path.exists(os.path.join(base, ".socket.sock")):
                    self.sock = os.path.join(base, ".socket.sock")
                    break
        self._mons, self._mons_t = [], 0.0
        self._clients, self._clients_t = [], 0.0

    def req(self, cmd):
        if not self.sock:
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.15)
                s.connect(self.sock)
                s.sendall(cmd.encode())
                parts = []
                while True:
                    b = s.recv(65536)
                    if not b:
                        break
                    parts.append(b)
            return json.loads(b"".join(parts) or b"null")
        except (OSError, ValueError):
            return None

    def monitors(self, force=False):
        now = time.monotonic()
        if force or now - self._mons_t > 3.0 or not self._mons:
            m = self.req("j/monitors")
            if isinstance(m, list) and m:
                self._mons = m
            self._mons_t = now
        return self._mons

    def locate(self, win):
        """→ (monitor name, x on monitor, y on monitor, monitor w, monitor h) for this window, or None."""
        pid = os.getpid()
        cl = None
        if win.is_active():
            c = self.req("j/activewindow")
            if isinstance(c, dict) and c.get("pid") == pid:
                cl = c
        if cl is None:
            now = time.monotonic()
            if now - self._clients_t > 0.15:
                c = self.req("j/clients")
                self._clients = c if isinstance(c, list) else []
                self._clients_t = now
            mine = [c for c in self._clients if c.get("pid") == pid and c.get("mapped", True)]
            if not mine:
                return None
            w, h = win.get_width(), win.get_height()
            cl = min(mine, key=lambda c: abs(c.get("size", [0, 0])[0] - w) + abs(c.get("size", [0, 0])[1] - h))
        at = cl.get("at") or [0, 0]
        for force in (False, True):
            for m in self.monitors(force):
                if m.get("id") == cl.get("monitor"):
                    name, mx, my, mw, mh = liquid.monitor_logical(m)
                    return name, at[0] - mx, at[1] - my, mw, mh
        return None


HYPR = _Hypr()


# ===================================================================================== wallpapers
class _Wallpapers:
    def __init__(self):
        self.map = {}
        self.listeners = []
        self._busy = False
        self._timer = 0

    def start(self):
        if not self._timer:
            self._timer = GLib.timeout_add_seconds(5, self._tick)
            self.refresh()

    def _tick(self):
        if not self.listeners:
            self._timer = 0
            return False
        self.refresh()
        return True

    def refresh(self):
        if self._busy:
            return
        try:
            proc = Gio.Subprocess.new(["sh", "-c", liquid.WALLPAPER_SCRIPT],
                                      Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error:
            return
        self._busy = True
        proc.communicate_utf8_async(None, None, self._done)

    def _done(self, proc, res):
        self._busy = False
        try:
            _ok, out, _err = proc.communicate_utf8_finish(res)
        except GLib.Error:
            return
        new = liquid.parse_wallpapers(out or "")
        if new != self.map:
            self.map = new
            for fn in list(self.listeners):
                fn()

    def path_for(self, monitor, override=""):
        if override:
            p = os.path.expanduser(override)
            if os.path.isfile(p):
                return p
        return self.map.get(monitor) or self.map.get("*") or ""


WALLPAPERS = _Wallpapers()

# ===================================================================================== backdrop pixels
_PIX = {}


def _aurora(w, h, theme):
    """No wallpaper: a soft aurora in the theme's colours, so the glass still has light to bend."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    bg = [c / 255 for c in _hex(theme["bg"])]
    dark = themes.luminance(theme["bg"]) < 0.5
    base = [c * 0.6 for c in bg] if dark else bg
    cr.set_source_rgb(*base)
    cr.paint()
    pal = theme["palette"]
    blobs = ((0.18, 0.22, 0.55, theme["accent"]), (0.85, 0.18, 0.45, pal[5]), (0.62, 0.86, 0.6, pal[6]),
             (0.08, 0.9, 0.4, pal[4]), (0.95, 0.8, 0.35, pal[3]))
    cr.set_operator(cairo.OPERATOR_SCREEN if dark else cairo.OPERATOR_MULTIPLY)
    for x, y, r, col in blobs:
        c = [v / 255 for v in _hex(col)]
        g = cairo.RadialGradient(x * w, y * h, 0, x * w, y * h, r * max(w, h))
        g.add_color_stop_rgba(0, *c, 0.85 if dark else 0.45)
        g.add_color_stop_rgba(1, *c, 0)
        cr.set_source(g)
        cr.paint()
    surf.flush()
    data = bytearray(surf.get_data())
    data[0::4], data[2::4] = data[2::4], data[0::4]       # cairo BGRA (little endian, opaque) → RGBA
    return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(data)), GdkPixbuf.Colorspace.RGB, True, 8,
                                           w, h, surf.get_stride())


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def backdrop_pixbuf(path, mw, mh, theme):
    """The monitor's wallpaper cropped like the wallpaper daemon does, at texture resolution."""
    tw = max(32, int(min(mw * 0.5, 1600)))
    th = max(32, int(tw * mh / max(mw, 1)))
    mtime = 0
    if path:
        try:
            mtime = os.stat(path).st_mtime_ns
        except OSError:
            path = ""
    key = (path, mtime, tw, th) if path else ("aurora", theme["bg"], theme["accent"], tuple(theme["palette"]), tw, th)
    if key in _PIX:
        return key, _PIX[key]
    pb = None
    if path:
        try:
            src = GdkPixbuf.Pixbuf.new_from_file(path)
            src = src.apply_embedded_orientation() or src
            x, y, cw, ch = liquid.cover_rect(src.get_width(), src.get_height(), tw, th)
            src = src.new_subpixbuf(int(x), int(y), max(1, int(cw)), max(1, int(ch)))
            pb = src.scale_simple(tw, th, GdkPixbuf.InterpType.HYPER)
        except Exception:
            pb = None
    if pb is None:
        key = ("aurora", theme["bg"], theme["accent"], tuple(theme["palette"]), tw, th)
        pb = _aurora(tw, th, theme)
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    if len(_PIX) > 6:
        _PIX.clear()
    _PIX[key] = pb
    return key, pb


# ===================================================================================== the layer
class GlassLayer(Gtk.Box):
    def __init__(self, win):
        super().__init__(hexpand=True, vexpand=True, can_target=False, can_focus=False)
        self.win = win
        self.s = win.s
        self.monitor = ""
        self.ox = self.oy = 0.0
        self.mw, self.mh = 1920.0, 1080.0
        self.located = False
        self.pix_key, self.pixbuf = None, None
        self._timer = 0
        self._fast = False
        self.area = None
        if os.environ.get("ISTL_GLASS") == "cairo":
            self.use_cairo()
        else:
            self.area = _GlassGL(self)
            self.append(self.area)
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self._active_id = win.connect("notify::is-active", lambda *_: self._schedule())
        self._max_id = win.connect("notify::maximized", lambda *_: self.redraw())
        self._fs_id = win.connect("notify::fullscreened", lambda *_: self.redraw())

    # ---------------------------------------------------------------- public
    def theme(self):
        return themes.get(self.win.app.theme_name())

    def params(self):
        maxed = self.win.is_maximized() or self.win.is_fullscreen()
        return liquid.shader_params(self.s, self.theme(), maxed)

    def refresh(self):
        """Settings / theme / wallpaper changed."""
        self._load_backdrop()
        self.redraw()

    def redraw(self):
        if self.area is not None:
            self.area.queue_render() if isinstance(self.area, Gtk.GLArea) else self.area.queue_draw()

    def shutdown(self):
        self._stop()
        for i in (self._active_id, self._max_id, self._fs_id):
            try:
                self.win.disconnect(i)
            except Exception:
                pass
        if self._on_wallpapers in WALLPAPERS.listeners:
            WALLPAPERS.listeners.remove(self._on_wallpapers)

    def use_cairo(self):
        if self.area is not None:
            self.remove(self.area)
        self.area = _GlassCairo(self)
        self.append(self.area)

    # ---------------------------------------------------------------- tracking
    def _on_map(self, *_):
        if self._on_wallpapers not in WALLPAPERS.listeners:
            WALLPAPERS.listeners.append(self._on_wallpapers)
        WALLPAPERS.start()
        self._fallback_monitor()
        self._track()
        self._load_backdrop()
        self._schedule()

    def _on_unmap(self, *_):
        self._stop()

    def _on_wallpapers(self):
        self.refresh()

    def _stop(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _schedule(self):
        self._stop()
        if not self.get_mapped() or not HYPR.sock or not self.s["glass_follow"]:
            return
        # while focused the window may be dragged or resized and Hyprland sends no events mid-drag:
        # follow it every frame. Unfocused, a slow check is plenty.
        self._fast = self.win.is_active()
        self._timer = GLib.timeout_add(16 if self._fast else 1000, self._track)

    def _fallback_monitor(self):
        if HYPR.sock and self.located:
            return
        try:
            surf = self.win.get_surface()
            mon = Gdk.Display.get_default().get_monitor_at_surface(surf) if surf else None
            if mon is not None:
                g = mon.get_geometry()
                self.mw, self.mh = float(g.width), float(g.height)
                self.monitor = mon.get_connector() or ""
        except Exception:
            pass

    def _track(self):
        if not HYPR.sock or not self.s["glass_follow"]:
            if not self.located:
                self._fallback_monitor()
            return False
        loc = HYPR.locate(self.win)
        if loc:
            name, x, y, mw, mh = loc
            try:
                ok, wx, wy = self.translate_coordinates(self.win, 0, 0)
            except Exception:
                wx = wy = 0.0
            nx, ny = x + wx, y + wy
            changed_mon = (name, mw, mh) != (self.monitor, self.mw, self.mh)
            if changed_mon or (nx, ny) != (self.ox, self.oy) or not self.located:
                self.monitor, self.mw, self.mh = name, mw, mh
                self.ox, self.oy = nx, ny
                self.located = True
                if changed_mon:
                    self._load_backdrop()
                self.redraw()
        if self._fast != self.win.is_active():
            self._schedule()
            return False
        return True

    def _load_backdrop(self):
        path = WALLPAPERS.path_for(self.monitor, self.s["glass_wallpaper"] or "")
        key, pb = backdrop_pixbuf(path, self.mw, self.mh, self.theme())
        if key != self.pix_key:
            self.pix_key, self.pixbuf = key, pb
            self.redraw()


class _GlassGL(Gtk.GLArea):
    def __init__(self, layer):
        super().__init__(hexpand=True, vexpand=True, can_target=False, can_focus=False)
        self.layer = layer
        for prop, val in (("has-alpha", True), ("auto-render", True)):   # has-alpha is gone in newer GTK (always on)
            try:
                self.set_property(prop, val)
            except (TypeError, AttributeError):
                pass
        try:
            self.set_allowed_apis(Gdk.GLAPI.GL | Gdk.GLAPI.GLES)
        except (AttributeError, TypeError):
            pass
        try:
            self.set_required_version(3, 0)
        except Exception:
            pass
        self.gl = None
        self.prog = 0
        self.vao = _c.c_uint(0)
        self.tex = _c.c_uint(0)
        self.tex_key = None
        self.loc = {}
        self.fb = (1, 1)
        self.failed = False
        self.connect("realize", self._realize)
        self.connect("unrealize", self._unrealize)
        self.connect("render", self._render)
        self.connect("resize", lambda a, w, h: setattr(self, "fb", (max(w, 1), max(h, 1))))

    def _fail(self, why):
        if self.failed:
            return
        self.failed = True
        print(f"interstellar: Liquid Glass uses the cairo fallback ({why})", flush=True)
        GLib.idle_add(lambda: (self.layer.use_cairo(), self.layer.redraw(), False)[2])

    def _realize(self, *_):
        self.make_current()
        if self.get_error() is not None:
            return self._fail(self.get_error().message)
        try:
            gl = self.gl = _GL.load()
            es = self.get_context().get_use_es()
            vs_src, fs_src = liquid.shader_sources(es)
            prog = gl["glCreateProgram"]()
            shaders = []
            for kind, src in ((GL_VERTEX_SHADER, vs_src), (GL_FRAGMENT_SHADER, fs_src)):
                sh = gl["glCreateShader"](kind)
                arr = (_c.c_char_p * 1)(src.encode())
                gl["glShaderSource"](sh, 1, arr, None)
                gl["glCompileShader"](sh)
                ok = _c.c_int(0)
                gl["glGetShaderiv"](sh, GL_COMPILE_STATUS, _c.byref(ok))
                if not ok.value:
                    log = _c.create_string_buffer(4096)
                    gl["glGetShaderInfoLog"](sh, 4096, None, log)
                    raise RuntimeError("shader: " + log.value.decode(errors="replace").strip())
                gl["glAttachShader"](prog, sh)
                shaders.append(sh)
            gl["glLinkProgram"](prog)
            ok = _c.c_int(0)
            gl["glGetProgramiv"](prog, GL_LINK_STATUS, _c.byref(ok))
            for sh in shaders:
                gl["glDeleteShader"](sh)
            if not ok.value:
                log = _c.create_string_buffer(4096)
                gl["glGetProgramInfoLog"](prog, 4096, None, log)
                raise RuntimeError("link: " + log.value.decode(errors="replace").strip())
            self.prog = prog
            for name in ("src", "glassSize", "srcSize", "srcOffset", "fbHeight", "scale", "radius", "bezel",
                         "thickness", "dispersion", "blurPx", "tintMix", "tintColor", "saturation", "dark",
                         "rim", "grain", "magnify", "ringW"):
                self.loc[name] = gl["glGetUniformLocation"](prog, name.encode())
            gl["glGenVertexArrays"](1, _c.byref(self.vao))
            gl["glGenTextures"](1, _c.byref(self.tex))
        except Exception as e:  # noqa: BLE001 — any GL trouble means: use the fallback
            self._fail(str(e))

    def _unrealize(self, *_):
        if not self.gl or self.failed:
            return
        self.make_current()
        if self.get_error() is not None:
            return
        gl = self.gl
        if self.prog:
            gl["glDeleteProgram"](self.prog)
        gl["glDeleteTextures"](1, _c.byref(self.tex))
        gl["glDeleteVertexArrays"](1, _c.byref(self.vao))
        self.prog = 0
        self.tex_key = None

    def _upload(self):
        gl, pb = self.gl, self.layer.pixbuf
        if pb is None:
            return False
        gl["glActiveTexture"](GL_TEXTURE0)
        gl["glBindTexture"](GL_TEXTURE_2D, self.tex.value)
        if self.tex_key != self.layer.pix_key:
            data = pb.read_pixel_bytes().get_data()
            buf = _c.create_string_buffer(data, len(data))
            gl["glPixelStorei"](GL_UNPACK_ALIGNMENT, 4)
            gl["glPixelStorei"](GL_UNPACK_ROW_LENGTH, pb.get_rowstride() // 4)
            gl["glTexImage2D"](GL_TEXTURE_2D, 0, GL_RGBA8, pb.get_width(), pb.get_height(), 0, GL_RGBA,
                               GL_UNSIGNED_BYTE, _c.cast(buf, _c.c_void_p))
            gl["glPixelStorei"](GL_UNPACK_ROW_LENGTH, 0)
            gl["glTexParameteri"](GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
            gl["glTexParameteri"](GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            gl["glTexParameteri"](GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            gl["glTexParameteri"](GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            gl["glGenerateMipmap"](GL_TEXTURE_2D)
            self.tex_key = self.layer.pix_key
        return True

    def _render(self, area, ctx):
        gl = self.gl
        if not gl or not self.prog or self.failed:
            return False
        gl["glClearColor"](0, 0, 0, 0)
        gl["glClear"](GL_COLOR_BUFFER_BIT)
        if not self._upload():
            return True
        L = self.layer
        p = L.params()
        sc = self.get_scale_factor() or 1
        w, h = self.get_width(), self.get_height()
        u = self.loc
        gl["glDisable"](GL_BLEND)
        gl["glUseProgram"](self.prog)
        gl["glUniform1i"](u["src"], 0)
        gl["glUniform2f"](u["glassSize"], float(w), float(h))
        gl["glUniform2f"](u["srcSize"], float(L.mw), float(L.mh))
        gl["glUniform2f"](u["srcOffset"], float(L.ox), float(L.oy))
        gl["glUniform1f"](u["fbHeight"], float(self.fb[1]))
        gl["glUniform1f"](u["scale"], float(self.fb[0]) / max(w, 1) if w else float(sc))
        for k in ("radius", "bezel", "thickness", "dispersion", "blurPx", "tintMix", "saturation", "dark", "rim",
                  "grain", "magnify", "ringW"):
            gl["glUniform1f"](u[k], float(p[k]))
        gl["glUniform3f"](u["tintColor"], *[float(c) for c in p["tintColor"]])
        gl["glBindVertexArray"](self.vao.value)
        gl["glDrawArrays"](GL_TRIANGLES, 0, 3)
        gl["glBindVertexArray"](0)
        gl["glUseProgram"](0)
        return True


class _GlassCairo(Gtk.DrawingArea):
    """No GL: frosted glass (blurred wallpaper, tint, rim light), without the refraction."""

    def __init__(self, layer):
        super().__init__(hexpand=True, vexpand=True, can_target=False, can_focus=False)
        self.layer = layer
        self._frost = None
        self.set_draw_func(self._draw)

    def _frosted(self, pb, frost):
        key = (self.layer.pix_key, round(frost, 2))
        if self._frost and self._frost[0] == key:
            return self._frost[1]
        k = 1 + frost * 22
        small = pb.scale_simple(max(4, int(pb.get_width() / k)), max(4, int(pb.get_height() / k)),
                                GdkPixbuf.InterpType.BILINEAR)
        self._frost = (key, small)
        return small

    def _draw(self, area, cr, w, h):
        L = self.layer
        p = L.params()
        r = min(p["radius"], w / 2, h / 2)
        _rounded(cr, 0, 0, w, h, r)
        cr.clip()
        pb = L.pixbuf
        if pb is not None:
            small = self._frosted(pb, (p["blurPx"] - 1.5) / 34.0)
            sx, sy = L.mw / small.get_width(), L.mh / small.get_height()
            cr.save()
            cr.scale(sx, sy)
            Gdk.cairo_set_source_pixbuf(cr, small, -L.ox / sx, -L.oy / sy)
            cr.get_source().set_filter(cairo.FILTER_GOOD)
            cr.paint()
            cr.restore()
        tr, tg, tb = p["tintColor"]
        cr.set_source_rgba(tr, tg, tb, p["tintMix"])
        cr.paint()
        lift = 0.02 if p["dark"] else 0.055
        cr.set_source_rgba(1, 1, 1, lift)
        cr.paint()
        # rim light, brighter top-left
        cr.reset_clip()
        g = cairo.LinearGradient(0, 0, w, h)
        g.add_color_stop_rgba(0, 1, 1, 1, min(0.9, 0.55 * p["rim"]))
        g.add_color_stop_rgba(0.5, 1, 1, 1, min(0.9, 0.12 * p["rim"]))
        g.add_color_stop_rgba(1, 1, 1, 1, min(0.9, 0.35 * p["rim"]))
        _rounded(cr, 0.5, 0.5, w - 1, h - 1, max(r - 0.5, 0))
        cr.set_source(g)
        cr.set_line_width(1.2)
        cr.stroke()


def _rounded(cr, x, y, w, h, r):
    if r <= 0:
        cr.rectangle(x, y, w, h)
        return
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()

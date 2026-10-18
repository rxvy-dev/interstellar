"""Live capture of the windows behind the glass, so Liquid Glass refracts them too (Hyprland).

A Wayland app can't see other windows' pixels, so — like MacShell's live window previews — we ask
Hyprland for them through its toplevel-export protocol (protocols/hyprland-toplevel-export-v1.xml,
BSD-licensed, bundled). A worker thread with its own Wayland connection captures the windows that are
behind ours a few times a second into shared memory and lays them over the wallpaper; the glass shader
then bends that picture exactly like it bends the wallpaper.

Needs python-pywayland. Without it (or on another compositor) the glass refracts the wallpaper only.
"""
import math, mmap, os, re, sys, threading, time

import cairo

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO_XML = os.path.join(HERE, "protocols", "hyprland-toplevel-export-v1.xml")
GEN_ROOT = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "interstellar", "wl")

WL_SHM_ARGB8888, WL_SHM_XRGB8888 = 0, 1          # little-endian B,G,R,A in memory — cairo's own layout
FLAG_Y_INVERT = 1

_lock = threading.Lock()
_bind = None          # (WlShm, ExportManager) or an error string


def bindings():
    """→ (WlShm, HyprlandToplevelExportManagerV1), or raise RuntimeError(reason)."""
    global _bind
    with _lock:
        if _bind is None:
            try:
                _bind = _load()
            except Exception as e:  # noqa: BLE001 — any problem just means: wallpaper only
                _bind = str(e) or e.__class__.__name__
        if isinstance(_bind, str):
            raise RuntimeError(_bind)
        return _bind


def status():
    """(ok, reason) — for Preferences."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False, "needs Hyprland"
    try:
        bindings()
        return True, ""
    except RuntimeError as e:
        return False, str(e)


def _load():
    try:
        import pywayland
        from pywayland.protocol.wayland import WlShm
        from pywayland.scanner import Protocol
    except ImportError:
        raise RuntimeError("install python-pywayland (Arch: sudo pacman -S python-pywayland)")
    # generate the Python binding for the Hyprland protocol once per pywayland version
    out = os.path.join(GEN_ROOT, "v" + re.sub(r"[^0-9a-zA-Z.]", "_", getattr(pywayland, "__version__", "0")))
    pkg = os.path.join(out, "istl_wl")
    mod = os.path.join(pkg, "hyprland_toplevel_export_v1.py")
    if not os.path.exists(mod):
        os.makedirs(pkg, exist_ok=True)
        with open(PROTO_XML) as f:
            xml = f.read()
        # v2's capture-by-wlr-handle needs another protocol we don't use
        xml = re.sub(r'<request name="capture_toplevel_with_wlr_toplevel_handle".*?</request>', "", xml, flags=re.S)
        stripped = os.path.join(pkg, "proto.xml")
        with open(stripped, "w") as f:
            f.write(xml)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(pkg, "wayland.py"), "w") as f:     # core types come from pywayland itself
            f.write("from pywayland.protocol.wayland import *  # noqa\n"
                    "from pywayland.protocol.wayland.wl_buffer import WlBuffer, WlBufferProxy  # noqa\n")
        proto = Protocol.parse_file(stripped)
        imports = {"wl_buffer": "wayland"}
        for iface in proto.interface:
            imports[iface.name] = proto.name.replace("-", "_")
        proto.output(pkg, imports)
    if out not in sys.path:
        sys.path.insert(0, out)
    from istl_wl.hyprland_toplevel_export_v1 import HyprlandToplevelExportManagerV1
    return WlShm, HyprlandToplevelExportManagerV1


# ===================================================================================== the worker
class Capturer(threading.Thread):
    """Captures the windows behind one glass window and composites them over its wallpaper.

    The main thread calls update(...) whenever it knows more (which windows are behind, the wallpaper);
    on_frame(key, w, h, stride, data) is called from this thread with a BGRA (cairo) picture of the
    whole monitor at texture resolution."""

    def __init__(self, on_frame, fps=10):
        super().__init__(name="istl-glass-capture", daemon=True)
        self.on_frame = on_frame
        self.fps = fps
        self.error = None
        self._wake = threading.Event()
        self._stop = False
        self._job = None          # dict: targets, wall (bytes/size), mon size, tex size
        self._shm = None          # (fd, mmap, pool, size)
        self._frame_no = 0
        self._wall = (None, None)  # (key, cairo-ordered bytes)

    # ---------------------------------------------------------------- main thread
    def update(self, **job):
        self._job = job
        self._wake.set()

    def stop(self):
        self._stop = True
        self._wake.set()

    # ---------------------------------------------------------------- worker
    def run(self):
        try:
            from pywayland.client import Display
            WlShm, Manager = bindings()
            self.display = Display()
            self.display.connect()
            found = {}
            reg = self.display.get_registry()

            def on_global(registry, name, interface, version):
                if interface in ("wl_shm", "hyprland_toplevel_export_manager_v1"):
                    found[interface] = (name, version)
            reg.dispatcher["global"] = on_global
            self.display.roundtrip()
            if "hyprland_toplevel_export_manager_v1" not in found or "wl_shm" not in found:
                raise RuntimeError("the compositor doesn't offer window capture")
            self.shm = reg.bind(found["wl_shm"][0], WlShm, 1)
            self.mgr = reg.bind(found["hyprland_toplevel_export_manager_v1"][0], Manager, 1)
            self.display.roundtrip()
        except Exception as e:  # noqa: BLE001
            self.error = str(e) or e.__class__.__name__
            return
        try:
            while not self._stop:
                job = self._job
                if not job or not job.get("targets"):
                    self._wake.wait(1.0)
                    self._wake.clear()
                    continue
                t0 = time.monotonic()
                shots = []
                for tgt in job["targets"]:
                    if self._stop:
                        break
                    shot = self._capture(tgt["handle"])
                    if shot:
                        shots.append((tgt, shot))
                if shots and not self._stop:
                    self._frame_no += 1
                    self.on_frame(*self._composite(job, shots))
                wait = max(0.0, 1.0 / max(1, self.fps) - (time.monotonic() - t0))
                self._wake.wait(wait)
                self._wake.clear()
        except Exception as e:  # noqa: BLE001
            self.error = str(e) or e.__class__.__name__
        finally:
            try:
                self.display.disconnect()
            except Exception:  # noqa: BLE001
                pass

    def _pool(self, size):
        if self._shm and self._shm[3] >= size:
            return self._shm
        if self._shm:
            fd, mm, pool, _ = self._shm
            pool.destroy()
            mm.close()
            os.close(fd)
        fd = os.memfd_create("istl-glass", os.MFD_CLOEXEC)
        os.ftruncate(fd, size)
        mm = mmap.mmap(fd, size)
        pool = self.shm.create_pool(fd, size)
        self._shm = (fd, mm, pool, size)
        return self._shm

    def _pump(self, st, keys, timeout):
        end = time.monotonic() + timeout
        while not any(k in st for k in keys):
            if time.monotonic() > end:
                return False
            self.display.roundtrip()
            if not any(k in st for k in keys):
                time.sleep(0.002)
        return True

    def _capture(self, handle):
        st = {}
        frame = self.mgr.capture_toplevel(0, handle & 0xFFFFFFFF)
        frame.dispatcher["buffer"] = lambda f, fmt, w, h, stride: st.setdefault("buf", (fmt, w, h, stride))
        frame.dispatcher["buffer_done"] = lambda f: st.__setitem__("done", True)
        frame.dispatcher["flags"] = lambda f, fl: st.__setitem__("flags", fl)
        frame.dispatcher["ready"] = lambda f, *a: st.__setitem__("ready", True)
        frame.dispatcher["failed"] = lambda f: st.__setitem__("failed", True)
        try:
            if not self._pump(st, ("done", "failed"), 0.25) or "failed" in st or "buf" not in st:
                return None
            fmt, w, h, stride = st["buf"]
            if fmt not in (WL_SHM_ARGB8888, WL_SHM_XRGB8888) or not w or not h:
                return None
            size = stride * h
            _fd, mm, pool, _ = self._pool(size)
            buf = pool.create_buffer(0, w, h, stride, fmt)
            frame.copy(buf, 1)
            ok = self._pump(st, ("ready", "failed"), 0.35) and "ready" in st
            data = mm[:size] if ok else None
            buf.destroy()
            if not ok:
                return None
            return w, h, stride, fmt, data, bool(st.get("flags", 0) & FLAG_Y_INVERT)
        finally:
            frame.destroy()

    def _composite(self, job, shots):
        """Wallpaper + the captured windows (bottom → top) at their places on the monitor."""
        tw, th = job["tex"]
        mw, mh = job["mon"]
        k = tw / max(mw, 1)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, tw, th)
        cr = cairo.Context(surf)
        wall = job.get("wall")
        if wall is not None:
            wkey, ww, wh, wstride, wdata = wall
            if self._wall[0] != wkey:
                b = bytearray(wdata)
                b[0::4], b[2::4] = b[2::4], b[0::4]          # RGBA (opaque) → cairo's BGRA
                self._wall = (wkey, b)
            ws = cairo.ImageSurface.create_for_data(self._wall[1], cairo.FORMAT_ARGB32, ww, wh, wstride)
            cr.save()
            cr.scale(tw / ww, th / wh)
            cr.set_source_surface(ws, 0, 0)
            cr.paint()
            cr.restore()
        else:
            cr.set_source_rgb(0.1, 0.1, 0.12)
            cr.paint()
        for tgt, (w, h, stride, fmt, data, yinv) in shots:
            src = cairo.ImageSurface.create_for_data(
                bytearray(data), cairo.FORMAT_ARGB32 if fmt == WL_SHM_ARGB8888 else cairo.FORMAT_RGB24, w, h, stride)
            x, y, lw, lh = tgt["rect"]
            r = tgt.get("rounding", 0) * k
            cr.save()
            _rounded(cr, x * k, y * k, lw * k, lh * k, r)
            cr.clip()
            cr.translate(x * k, y * k)
            cr.scale(lw * k / w, lh * k / h)
            if yinv:
                cr.translate(0, h)
                cr.scale(1, -1)
            cr.set_source_surface(src, 0, 0)
            cr.get_source().set_filter(cairo.FILTER_GOOD)
            cr.paint()
            cr.restore()
        surf.flush()
        return ("live", self._frame_no), tw, th, surf.get_stride(), bytes(surf.get_data())


def _rounded(cr, x, y, w, h, r):
    r = max(0.0, min(r, w / 2, h / 2))
    if r <= 0:
        cr.rectangle(x, y, w, h)
        return
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


# ===================================================================================== who's behind us
def windows_behind(clients, me, monitor_id, pad=48):
    """Hyprland `j/clients` → the windows drawn under `me` that the glass can see (bottom → top),
    as dicts {handle, rect=(x, y, w, h) in layout coords}. Tiled windows sit under floating ones;
    among floating windows the most recently focused is on top."""
    mx, my = me["at"]
    mw, mh = me["size"]
    ws = (me.get("workspace") or {}).get("id")
    me_float = bool(me.get("floating"))
    me_hist = me.get("focusHistoryID", 0)
    out = []
    for c in clients:
        if c.get("address") == me.get("address") or not c.get("mapped", True) or c.get("hidden"):
            continue
        if c.get("monitor") != monitor_id or (c.get("workspace") or {}).get("id") != ws:
            continue
        x, y = c.get("at", [0, 0])
        w, h = c.get("size", [0, 0])
        if w <= 0 or h <= 0 or x >= mx + mw + pad or y >= my + mh + pad or x + w <= mx - pad or y + h <= my - pad:
            continue
        floating = bool(c.get("floating"))
        if not me_float and floating:
            continue                    # floating windows draw above tiled ones
        if me_float and floating and c.get("focusHistoryID", 0) < me_hist:
            continue                    # focused more recently than us = above us
        out.append(c)
    out.sort(key=lambda c: (bool(c.get("floating")), -c.get("focusHistoryID", 0)))
    res = []
    for c in out:
        try:
            handle = int(str(c.get("address", "0")), 16)
        except ValueError:
            continue
        res.append({"handle": handle, "rect": (c["at"][0], c["at"][1], c["size"][0], c["size"][1])})
    return res

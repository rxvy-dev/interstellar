"""`interstellar --doctor`: check that everything Interstellar needs is installed, on any distro."""
import os, shutil, sys

if sys.stdout.isatty():
    OK, BAD, OPT = "\033[32m✔\033[0m", "\033[31m✖\033[0m", "\033[33m•\033[0m"
else:
    OK, BAD, OPT = "✔", "✖", "•"


def _typelib(ns, ver):
    try:
        import gi
        gi.require_version(ns, ver)
        mod = __import__("gi.repository", fromlist=[ns])
        return getattr(mod, ns)
    except Exception:
        return None


def check():
    """Returns (problems, report_lines). problems = number of missing *required* things."""
    lines, problems = [], 0

    def row(ok, required, name, detail=""):
        nonlocal problems
        mark = OK if ok else (BAD if required else OPT)
        if not ok and required:
            problems += 1
        lines.append(f"  {mark} {name}{('  — ' + detail) if detail else ''}")

    lines.append("Required")
    row(sys.version_info >= (3, 9), True, f"Python {sys.version.split()[0]}", "" if sys.version_info >= (3, 9) else "need 3.9+")
    try:
        import gi  # noqa: F401
        row(True, True, "PyGObject (python gi bindings)")
    except ImportError:
        row(False, True, "PyGObject (python gi bindings)", "not found for " + sys.executable)
        return problems, lines
    try:
        gi.require_foreign("cairo")
        import cairo  # noqa: F401  (pycairo itself must import)
        row(True, True, "PyGObject cairo bridge")
    except Exception:
        row(False, True, "PyGObject cairo bridge", "draws the starfield and icons (python3-gi-cairo / python-cairo)")
    Gtk = _typelib("Gtk", "4.0")
    if Gtk:
        v = (Gtk.get_major_version(), Gtk.get_minor_version())
        row(v >= (4, 10), True, f"GTK {v[0]}.{v[1]}", "" if v >= (4, 10) else "need 4.10+")
    else:
        row(False, True, "GTK 4", "typelib Gtk-4.0 not found")
    Vte = _typelib("Vte", "3.91")
    if Vte:
        row(True, True, f"VTE {Vte.get_major_version()}.{Vte.get_minor_version()} (GTK 4)")
    else:
        row(False, True, "VTE for GTK 4", "typelib Vte-3.91 not found (vte4 / vte3-gtk4 / gir1.2-vte-3.91 / vte291-gtk4)")

    lines.append("Optional")
    try:
        from gi.repository import PangoCairo
        fams = {f.get_name().lower() for f in PangoCairo.FontMap.get_default().list_families()}
        good = [f for f in ("JetBrains Mono", "Fira Code", "Cascadia Code", "Iosevka", "Hack") if f.lower() in fams]
        row(bool(good), False, "Programming font", ", ".join(good) if good else "install JetBrains Mono or Fira Code for the best look")
    except Exception:
        pass
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    ls = _typelib("Gtk4LayerShell", "1.0")
    if wayland:
        row(ls is not None, False, "gtk4-layer-shell", "drop-down terminal on Wayland (wlroots / KDE)")
    else:
        row(shutil.which("xdotool") is not None, False, "xdotool", "places the drop-down terminal on X11")
        row(shutil.which("wmctrl") is not None, False, "wmctrl", "keeps the drop-down terminal on top on X11")
    return problems, lines


def main():
    problems, lines = check()
    from . import VERSION
    print(f"Interstellar Terminal {VERSION} — doctor\n")
    print("\n".join(lines))
    print()
    if problems:
        print(f"{problems} required component(s) missing. Run ./install.sh from the source folder (or install the ✖ items).")
    else:
        print("Everything required is installed. Missing extras are optional.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

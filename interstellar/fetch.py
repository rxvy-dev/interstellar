"""`istl --fetch`: a space-themed system summary (no GTK needed, works in any terminal)."""
import os, platform, re, shutil, socket, sys

ART = [
    '          .    *       ✦     ',
    "     *      .-'''''-.     .  ",
    "          .'  >_      '.     ",
    '   ✦     /              \\    ',
    '  ======|================|===',
    '   ====  \\              /  ==',
    "          '.          .'   * ",
    "     .      '-......-'       ",
    '        *        .      ✦    ',
]


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def info():
    osr = dict(re.findall(r'^(\w+)="?([^"\n]*)"?', _read("/etc/os-release"), re.M))
    up = float((_read("/proc/uptime").split() or ["0"])[0])
    h, m = int(up // 3600), int(up % 3600 // 60)
    mem = dict(re.findall(r"^(\w+):\s+(\d+)", _read("/proc/meminfo"), re.M))
    total = int(mem.get("MemTotal", 0)) / 1048576
    used = total - int(mem.get("MemAvailable", 0)) / 1048576
    cpu = re.search(r"model name\s*:\s*(.+)", _read("/proc/cpuinfo"))
    cpu = re.sub(r"\s+", " ", cpu.group(1)).replace("(R)", "").replace("(TM)", "") if cpu else platform.machine()
    pkgs = []
    for cmd, d in (("xbps-query", "/var/db/xbps"), ("pacman", "/var/lib/pacman/local"), ("dpkg", "/var/lib/dpkg/info"),
                   ("rpm", None), ("apk", "/lib/apk/db")):
        if shutil.which(cmd) and d and os.path.isdir(d):
            try:
                n = len(os.listdir(d))
                if cmd == "dpkg":
                    n = len([f for f in os.listdir(d) if f.endswith(".list")])
                if cmd == "xbps-query":
                    n = None
                if n:
                    pkgs.append(f"{n} ({cmd})")
            except OSError:
                pass
    de = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or ""
    session = "Wayland" if os.environ.get("WAYLAND_DISPLAY") else ("X11" if os.environ.get("DISPLAY") else "tty")
    term = "Interstellar" if os.environ.get("INTERSTELLAR") else os.environ.get("TERM_PROGRAM", os.environ.get("TERM", "?"))
    rows = [
        ("OS", osr.get("PRETTY_NAME", platform.system())),
        ("Kernel", platform.release()),
        ("Uptime", f"{h}h {m}m"),
        ("Shell", os.path.basename(os.environ.get("SHELL", "sh"))),
        ("Desktop", f"{de} ({session})" if de else session),
        ("Terminal", term),
        ("CPU", cpu[:38]),
        ("Memory", f"{used:.1f} / {total:.1f} GiB"),
    ]
    if pkgs:
        rows.insert(3, ("Packages", ", ".join(pkgs)))
    return rows


def main():
    color = sys.stdout.isatty() or os.environ.get("INTERSTELLAR")
    A = "\033[33m" if color else ""
    P = "\033[35m" if color else ""
    C = "\033[36m" if color else ""
    B = "\033[1m" if color else ""
    D = "\033[2m" if color else ""
    X = "\033[0m" if color else ""
    user = os.environ.get("USER") or "astronaut"
    host = socket.gethostname()
    right = [f"{B}{A}{user}{X}@{B}{P}{host}{X}", D + "─" * (len(user) + len(host) + 1) + X]
    right += [f"{B}{C}{k:<9}{X}{v}" for k, v in info()]
    right.append("")
    if color:
        right.append("".join(f"\033[4{i}m   " for i in range(8)) + X)
        right.append("".join(f"\033[10{i}m   " for i in range(8)) + X)
    cols = shutil.get_terminal_size((100, 30)).columns
    room = cols - len(ART[0]) - 4
    show_art = room >= 22
    if not show_art:
        room = cols - 2
    vis = re.compile(r"\033\[[0-9;]*m")

    def fit(line):
        plain = vis.sub("", line)
        if len(plain) <= room:
            return line
        # cut by visible characters, keep colour codes
        out, n, i = "", 0, 0
        while i < len(line) and n < room - 1:
            m = vis.match(line, i)
            if m:
                out += m.group()
                i = m.end()
                continue
            out += line[i]
            n += 1
            i += 1
        return out + "…" + X
    right = [fit(r) for r in right]
    if not show_art:
        for r in right:
            print(" " + r)
        return 0
    n = max(len(ART), len(right))
    for i in range(n):
        art = ART[i] if i < len(ART) else " " * len(ART[0])
        art = (A + art.replace("✦", P + "✦" + A).replace(">_", B + ">_" + X + A) + X) if color else art
        print(f" {art}  {right[i] if i < len(right) else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

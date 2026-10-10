"""Colour themes. Each: name, fg, bg, cursor, selection, accent, 16-colour palette (0-7 normal, 8-15 bright).

Custom themes live in ~/.config/interstellar/themes/*.json (same keys). Importers for kitty,
Alacritty (TOML/YAML) and base16 YAML are at the bottom.
"""
import json, os, re

from .settings import CFG_DIR

THEME_DIR = os.path.join(CFG_DIR, "themes")


def T(name, fg, bg, cursor, sel, accent, pal, space=False):
    return {"name": name, "fg": fg, "bg": bg, "cursor": cursor, "selection": sel, "accent": accent,
            "palette": pal.split(), "space": space}


BUILTIN = [
    # ---- space themes (Interstellar originals)
    T("Event Horizon", "#e6e1d6", "#050507", "#ffb347", "#3a2a12", "#ffb347",
      "#14141a #ff5c57 #9ccc65 #ffb347 #6fa8ff #c792ea #4fd6be #cfc8bb "
      "#4a4a55 #ff7b72 #b9e769 #ffd27d #8fbcff #ddb3ff #7ff0dc #ffffff", True),
    T("Nebula", "#ece6ff", "#0c0717", "#ff6ad5", "#3b1e5c", "#ff6ad5",
      "#1b1230 #ff5c8a #7ef2b0 #ffd36a #8b8cff #ff6ad5 #5cf2ff #d9d0f5 "
      "#4b3d6e #ff86a8 #a3ffd0 #ffe39a #b0b1ff #ff9be3 #93f7ff #ffffff", True),
    T("Supernova", "#fff1e0", "#0b0503", "#ff7a1a", "#4a1f08", "#ff7a1a",
      "#1c100a #ff3b30 #a6e22e #ffb000 #4ea1ff #ff5ec4 #3ee6c4 #f2dcc8 "
      "#5a4033 #ff6a5c #c4f25a #ffd24d #85c0ff #ff8fd6 #78f2dc #ffffff", True),
    T("Red Giant", "#e9e4e6", "#0a0a0c", "#ff2e43", "#46121b", "#ff2e43",
      "#17121a #ff2e43 #8fd38b #ffb454 #6c9eff #ff7a85 #64d6c4 #d9cfd2 "
      "#4b3f45 #ff5468 #b0eaa6 #ffd08a #96b9ff #ff9ca5 #92eadc #ffffff", True),
    T("Deep Space", "#cfe3ff", "#02050c", "#5cc8ff", "#12305a", "#5cc8ff",
      "#0c1626 #ff6b81 #7ce0a0 #ffd479 #5cc8ff #b19cff #5eead4 #b8cce6 "
      "#34465f #ff8fa0 #a4f0c2 #ffe3a6 #8fdcff #cbbcff #8ff3e4 #ffffff", True),
    T("Andromeda", "#e5e9f0", "#1a1a2e", "#ee5d43", "#3d3d5c", "#00e8c6",
      "#23232e #ee5d43 #96e072 #ffe66d #7cb7ff #c74ded #00e8c6 #d5ced9 "
      "#4b4b63 #f39c81 #b4eea0 #fff1a6 #a8cfff #da8ef3 #6bf2dc #ffffff", True),
    T("Pulsar", "#eaf6ff", "#000000", "#7df9ff", "#16323d", "#7df9ff",
      "#0d1418 #ff4d6d #59f7a0 #f9f871 #4cc9f0 #b5179e #7df9ff #cfe6f0 "
      "#3a4b52 #ff7a93 #8bfac0 #fbfba6 #82dbf6 #d65ac1 #b0fbff #ffffff", True),
    T("Aurora", "#dff7ee", "#03090b", "#5effc4", "#0f3a33", "#5effc4",
      "#0b171a #ff6b8b #5effc4 #f4e285 #6ec3ff #b18cff #3ee0e0 #c8e6dc "
      "#33484c #ff93a9 #9bffdc #f8ecaa #9ed8ff #cdb5ff #82f0f0 #ffffff", True),
    # ---- classics
    T("Dracula", "#f8f8f2", "#282a36", "#f8f8f2", "#44475a", "#bd93f9",
      "#21222c #ff5555 #50fa7b #f1fa8c #bd93f9 #ff79c6 #8be9fd #f8f8f2 "
      "#6272a4 #ff6e6e #69ff94 #ffffa5 #d6acff #ff92df #a4ffff #ffffff"),
    T("Catppuccin Mocha", "#cdd6f4", "#1e1e2e", "#f5e0dc", "#45475a", "#cba6f7",
      "#45475a #f38ba8 #a6e3a1 #f9e2af #89b4fa #f5c2e7 #94e2d5 #bac2de "
      "#585b70 #f38ba8 #a6e3a1 #f9e2af #89b4fa #f5c2e7 #94e2d5 #a6adc8"),
    T("Catppuccin Latte", "#4c4f69", "#eff1f5", "#dc8a78", "#ccd0da", "#8839ef",
      "#5c5f77 #d20f39 #40a02b #df8e1d #1e66f5 #ea76cb #179299 #acb0be "
      "#6c6f85 #d20f39 #40a02b #df8e1d #1e66f5 #ea76cb #179299 #bcc0cc"),
    T("Tokyo Night", "#c0caf5", "#1a1b26", "#c0caf5", "#33467c", "#7aa2f7",
      "#15161e #f7768e #9ece6a #e0af68 #7aa2f7 #bb9af7 #7dcfff #a9b1d6 "
      "#414868 #f7768e #9ece6a #e0af68 #7aa2f7 #bb9af7 #7dcfff #c0caf5"),
    T("Gruvbox Dark", "#ebdbb2", "#282828", "#ebdbb2", "#504945", "#fe8019",
      "#282828 #cc241d #98971a #d79921 #458588 #b16286 #689d6a #a89984 "
      "#928374 #fb4934 #b8bb26 #fabd2f #83a598 #d3869b #8ec07c #ebdbb2"),
    T("Nord", "#d8dee9", "#2e3440", "#d8dee9", "#434c5e", "#88c0d0",
      "#3b4252 #bf616a #a3be8c #ebcb8b #81a1c1 #b48ead #88c0d0 #e5e9f0 "
      "#4c566a #bf616a #a3be8c #ebcb8b #81a1c1 #b48ead #8fbcbb #eceff4"),
    T("One Dark", "#abb2bf", "#282c34", "#528bff", "#3e4451", "#61afef",
      "#282c34 #e06c75 #98c379 #e5c07b #61afef #c678dd #56b6c2 #abb2bf "
      "#5c6370 #e06c75 #98c379 #e5c07b #61afef #c678dd #56b6c2 #ffffff"),
    T("Rosé Pine", "#e0def4", "#191724", "#524f67", "#2a283e", "#ebbcba",
      "#26233a #eb6f92 #31748f #f6c177 #9ccfd8 #c4a7e7 #ebbcba #e0def4 "
      "#6e6a86 #eb6f92 #31748f #f6c177 #9ccfd8 #c4a7e7 #ebbcba #e0def4"),
    T("Kanagawa", "#dcd7ba", "#1f1f28", "#c8c093", "#2d4f67", "#7e9cd8",
      "#16161d #c34043 #76946a #c0a36e #7e9cd8 #957fb8 #6a9589 #c8c093 "
      "#727169 #e82424 #98bb6c #e6c384 #7fb4ca #938aa9 #7aa89f #dcd7ba"),
    T("Everforest", "#d3c6aa", "#2d353b", "#d3c6aa", "#475258", "#a7c080",
      "#475258 #e67e80 #a7c080 #dbbc7f #7fbbb3 #d699b6 #83c092 #d3c6aa "
      "#859289 #e67e80 #a7c080 #dbbc7f #7fbbb3 #d699b6 #83c092 #d3c6aa"),
    T("Solarized Dark", "#839496", "#002b36", "#93a1a1", "#073642", "#268bd2",
      "#073642 #dc322f #859900 #b58900 #268bd2 #d33682 #2aa198 #eee8d5 "
      "#002b36 #cb4b16 #586e75 #657b83 #839496 #6c71c4 #93a1a1 #fdf6e3"),
    T("Solarized Light", "#657b83", "#fdf6e3", "#586e75", "#eee8d5", "#268bd2",
      "#073642 #dc322f #859900 #b58900 #268bd2 #d33682 #2aa198 #eee8d5 "
      "#002b36 #cb4b16 #586e75 #657b83 #839496 #6c71c4 #93a1a1 #fdf6e3"),
    T("Monokai", "#f8f8f2", "#272822", "#f8f8f0", "#49483e", "#a6e22e",
      "#272822 #f92672 #a6e22e #f4bf75 #66d9ef #ae81ff #a1efe4 #f8f8f2 "
      "#75715e #f92672 #a6e22e #f4bf75 #66d9ef #ae81ff #a1efe4 #f9f8f5"),
    T("GitHub Dark", "#e6edf3", "#0d1117", "#2f81f7", "#264f78", "#2f81f7",
      "#484f58 #ff7b72 #3fb950 #d29922 #58a6ff #bc8cff #39c5cf #b1bac4 "
      "#6e7681 #ffa198 #56d364 #e3b341 #79c0ff #d2a8ff #56d4dd #ffffff"),
    T("GitHub Light", "#1f2328", "#ffffff", "#0969da", "#b6e3ff", "#0969da",
      "#24292f #cf222e #116329 #4d2d00 #0969da #8250df #1b7c83 #6e7781 "
      "#57606a #a40e26 #1a7f37 #633c01 #218bff #a475f9 #3192aa #8c959f"),
    T("Matrix", "#33ff66", "#000500", "#66ff99", "#0f3d1c", "#33ff66",
      "#001a05 #1fae4a #33ff66 #a8ff60 #1f9e5a #22cc77 #44ffaa #c8ffd6 "
      "#0f4d1f #2bd45d #66ff99 #ccff99 #2fbf73 #33e08d #77ffc4 #eaffef"),
    T("Amber CRT", "#ffb000", "#120a00", "#ffcc4d", "#4a3000", "#ffb000",
      "#2a1a00 #ff6a00 #ffb000 #ffd24d #cc8a00 #ff9e3d #ffc966 #ffe0a3 "
      "#5c3b00 #ff8c33 #ffc533 #ffe080 #e6a52e #ffb870 #ffd89c #fff2d6"),
]


def _load_custom():
    out = []
    try:
        for fn in sorted(os.listdir(THEME_DIR)):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(THEME_DIR, fn)) as f:
                        t = json.load(f)
                    if len(t.get("palette", [])) == 16 and t.get("fg") and t.get("bg"):
                        t.setdefault("cursor", t["fg"]); t.setdefault("selection", t["palette"][8])
                        t.setdefault("accent", t["palette"][4]); t["custom"] = True
                        out.append(t)
                except (OSError, ValueError):
                    pass
    except OSError:
        pass
    return out


_cache = {"key": None, "themes": None}


def all_themes():
    try:
        key = os.stat(THEME_DIR).st_mtime_ns
    except OSError:
        key = 0
    if _cache["key"] == key and _cache["themes"] is not None:
        return _cache["themes"]
    custom = _load_custom()
    names = {t["name"] for t in custom}
    _cache["themes"] = custom + [t for t in BUILTIN if t["name"] not in names]
    _cache["key"] = key
    return _cache["themes"]


def invalidate():
    _cache["key"] = None


def get(name):
    for t in all_themes():
        if t["name"] == name:
            return t
    return BUILTIN[0]


def save_custom(theme):
    os.makedirs(THEME_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", theme["name"].lower()).strip("-") or "theme"
    t = {k: theme[k] for k in ("name", "fg", "bg", "cursor", "selection", "accent", "palette")}
    with open(os.path.join(THEME_DIR, slug + ".json"), "w") as f:
        json.dump(t, f, indent=2)
    invalidate()
    return os.path.join(THEME_DIR, slug + ".json")


def luminance(hexc):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ------------------------------------------------------------------ importers
def _norm(c):
    c = c.strip().strip("'\"")
    if c.startswith("0x"):
        c = "#" + c[2:]
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", c):
        return "#" + c.lstrip("#").lower()
    return None


def parse_kitty(text):
    kv = {}
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 2 and not line.lstrip().startswith("#"):
            kv[p[0]] = p[1]
    pal = [_norm(kv.get(f"color{i}", "")) for i in range(16)]
    if None in pal or "foreground" not in kv or "background" not in kv:
        raise ValueError("not a kitty colour file (needs foreground, background, color0..color15)")
    fg, bg = _norm(kv["foreground"]), _norm(kv["background"])
    return {"fg": fg, "bg": bg, "cursor": _norm(kv.get("cursor", "")) or fg,
            "selection": _norm(kv.get("selection_background", "")) or pal[8], "accent": pal[4], "palette": pal}


def parse_alacritty(text):
    """Alacritty TOML ([colors.primary] …) or YAML (colors: primary: …)."""
    sec, vals = None, {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0] if not re.search(r"['\"]#", raw) else raw
        s = line.strip()
        if not s:
            continue
        m = re.match(r"\[colors\.(\w+)\]", s)
        if m:
            sec = m.group(1); continue
        m = re.match(r"^(\w+)\s*:\s*$", s)
        if m and m.group(1) in ("primary", "normal", "bright", "cursor", "selection"):
            sec = m.group(1); continue
        m = re.match(r"^(\w+)\s*[:=]\s*['\"]?(#|0x)([0-9a-fA-F]{6})", s)
        if m and sec:
            vals[(sec, m.group(1))] = "#" + m.group(3).lower()
    names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    pal = [vals.get(("normal", n)) for n in names] + [vals.get(("bright", n)) for n in names]
    fg, bg = vals.get(("primary", "foreground")), vals.get(("primary", "background"))
    if None in pal or not fg or not bg:
        raise ValueError("not an Alacritty theme (needs primary + normal + bright colours)")
    return {"fg": fg, "bg": bg, "cursor": vals.get(("cursor", "cursor")) or fg,
            "selection": vals.get(("selection", "background")) or pal[8], "accent": pal[4], "palette": pal}


def parse_base16(text):
    b = {}
    for m in re.finditer(r"base0([0-9A-Fa-f])\s*:\s*['\"]?#?([0-9a-fA-F]{6})", text):
        b[m.group(1).upper()] = "#" + m.group(2).lower()
    if len(b) < 16:
        raise ValueError("not a base16 scheme (needs base00..base0F)")
    pal = [b["0"], b["8"], b["B"], b["A"], b["D"], b["E"], b["C"], b["5"],
           b["3"], b["8"], b["B"], b["A"], b["D"], b["E"], b["C"], b["7"]]
    return {"fg": b["5"], "bg": b["0"], "cursor": b["5"], "selection": b["2"], "accent": b["D"], "palette": pal}


def import_file(path):
    with open(path, errors="replace") as f:
        text = f.read()
    errors = []
    for fn in (parse_kitty, parse_alacritty, parse_base16):
        try:
            t = fn(text)
            m = re.search(r"(?:scheme|name)\s*[:=]\s*['\"]?([^'\"\n]+)", text)
            t["name"] = (m.group(1).strip() if m else os.path.splitext(os.path.basename(path))[0]).title()
            return t
        except ValueError as e:
            errors.append(str(e))
    raise ValueError("Unrecognised theme file.\n" + "\n".join(errors))

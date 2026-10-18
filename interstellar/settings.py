"""Settings: ~/.config/interstellar/settings.json. Every change is saved and applied live."""
import copy, json, os

CFG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "interstellar")
CFG_FILE = os.path.join(CFG_DIR, "settings.json")

DEFAULTS = {
    # appearance
    "theme": "Event Horizon",
    "font": "JetBrains Mono 12",
    "line_height": 1.0,            # cell height scale
    "letter_spacing": 1.0,         # cell width scale
    "bold_is_bright": True,
    "cursor_shape": "block",       # block | ibeam | underline
    "cursor_blink": "on",          # system | on | off
    "cursor_color": "",            # "" = theme
    "padding": 12,
    "opacity": 1.0,                # 0.3 – 1.0 (needs a compositor)
    "starfield": True,             # animated stars behind the text
    "starfield_motion": "drift",   # drift | twinkle | still
    "starfield_density": 1.0,
    "background_image": "",
    "background_dim": 0.65,
    "ui_style": "glass",           # glass | solid | minimal | liquid
    # Liquid Glass (ui_style "liquid", or any Liquid theme) — ranges live in liquid.GLASS_KEYS
    "glass_mode": "wallpaper",     # wallpaper: refract what's behind (wallpaper + windows) | live: see-through
    "glass_windows": True,         # refract the windows behind too (Hyprland, needs python-pywayland)
    "glass_fps": 10,               # how often the windows behind are re-captured, per second
    "glass_quality": "balanced",   # fast | balanced | best (wallpaper mode blur samples)
    "glass_frost": 0.5,            # wallpaper-mode blur
    "glass_refraction": 1.0,       # how hard the curved rim bends the backdrop
    "glass_edge": 26,              # width of the curved rim, px
    "glass_dispersion": 1.0,       # rainbow split at the rim
    "glass_ior": 1.5,              # index of refraction
    "glass_tint": 0.45,            # theme-colour tint over the glass (readability)
    "glass_opacity": 0.55,         # see-through mode: how much the glass hides what's behind
    "glass_vibrancy": 1.3,         # backdrop saturation
    "glass_milk": 1.0,             # milky brightness lift
    "glass_rim": 0.7,              # specular edge highlight
    "glass_rim_width": 1.0,        # how far the highlight spreads in from the edge
    "glass_light_angle": 326,      # light direction, degrees clockwise from the top
    "glass_depth": 1.0,            # inner shadow / thickness toward the edges
    "glass_border": 1.0,           # thin bright border, px
    "glass_lens": 0.3,             # whole-window magnifying lens
    "glass_grain": 0.3,            # fine noise
    "glass_radius": 16,            # corner radius, px
    "glass_shadow": 0.5,           # drop shadow (floating windows)
    "glass_tone": "auto",          # auto | dark | light
    "glass_wallpaper": "",         # "" = detect (swww / awww / hyprpaper / waypaper / swaybg)
    "glass_stars": True,           # starfield on top of the glass
    "glass_follow": True,          # follow the window's position on screen (Hyprland)
    # tabs & window
    "tab_position": "top",         # top | bottom
    "hide_single_tab": False,
    "confirm_close": True,
    "new_tab_cwd": True,           # open new tabs/splits in the current folder
    "restore_session": True,
    "background": True,            # keep running after the last window closes: new windows open instantly
    "width": 1100, "height": 680,
    "quake_height": 0.45,
    # behaviour
    "scrollback": 10000,           # -1 = unlimited
    "scroll_on_output": False,
    "copy_on_select": False,
    "safe_paste": True,
    "bell": "visual",              # none | visual | audible
    "link_click": "ctrl",          # ctrl | click
    "editor_command": "",          # e.g. "aether {file}" — "" = auto
    "notify_finished": True,       # desktop notification when a background tab goes quiet
    "word_chars": "-A-Za-z0-9,./?%&#:_=+@~",
    # profiles
    "profiles": [{"name": "Default", "command": "", "cwd": "", "theme": "", "font": "", "env": {}}],
    "default_profile": "Default",
    "keybindings": {},
    "session": [],
    "custom_css": "",
}


class Settings:
    def __init__(self):
        self.d = copy.deepcopy(DEFAULTS)
        self.listeners = []
        try:
            with open(CFG_FILE) as f:
                user = json.load(f)
            if isinstance(user, dict):
                self.d.update(user)
        except (OSError, ValueError):
            pass

    def __getitem__(self, k):
        return self.d.get(k, DEFAULTS.get(k))

    def __setitem__(self, k, v):
        if self.d.get(k) == v:
            return
        self.d[k] = v
        self.save()
        for fn in list(self.listeners):
            fn(k)

    def set_quiet(self, k, v):
        self.d[k] = v
        self.save()

    def save(self):
        try:
            os.makedirs(CFG_DIR, exist_ok=True)
            tmp = CFG_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.d, f, indent=2)
            os.replace(tmp, CFG_FILE)
        except OSError:
            pass

    def profile(self, name=None):
        name = name or self["default_profile"]
        for p in self["profiles"]:
            if p.get("name") == name:
                return p
        return self["profiles"][0] if self["profiles"] else DEFAULTS["profiles"][0]

    def reset(self):
        keep = {k: self.d.get(k) for k in ("session", "profiles", "keybindings")}
        self.d = copy.deepcopy(DEFAULTS)
        self.d.update(keep)
        self.save()
        for fn in list(self.listeners):
            fn("*")

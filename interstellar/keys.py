"""Actions and their default shortcuts. Users override any of them in Preferences → Keys
(stored in settings["keybindings"] as {action: "<Ctrl><Shift>t"})."""

ACTIONS = [
    # (action, label, default accel)
    ("new-tab", "New tab", "<Ctrl><Shift>t"),
    ("close-pane", "Close pane / tab", "<Ctrl><Shift>w"),
    ("new-window", "New window", "<Ctrl><Shift>n"),
    ("split-right", "Split right", "<Ctrl><Shift>d"),
    ("split-down", "Split down", "<Ctrl><Shift>e"),
    ("focus-left", "Focus pane left", "<Alt>Left"),
    ("focus-right", "Focus pane right", "<Alt>Right"),
    ("focus-up", "Focus pane up", "<Alt>Up"),
    ("focus-down", "Focus pane down", "<Alt>Down"),
    ("zoom-pane", "Zoom pane (maximise)", "<Ctrl><Shift>z"),
    ("next-tab", "Next tab", "<Ctrl>Page_Down"),
    ("prev-tab", "Previous tab", "<Ctrl>Page_Up"),
    ("move-tab-left", "Move tab left", "<Ctrl><Shift>Page_Up"),
    ("move-tab-right", "Move tab right", "<Ctrl><Shift>Page_Down"),
    ("rename-tab", "Rename tab", "<Ctrl><Shift>r"),
    ("copy", "Copy", "<Ctrl><Shift>c"),
    ("paste", "Paste", "<Ctrl><Shift>v"),
    ("select-all", "Select all", "<Ctrl><Shift>a"),
    ("find", "Find", "<Ctrl><Shift>f"),
    ("zoom-in", "Bigger text", "<Ctrl>plus"),
    ("zoom-out", "Smaller text", "<Ctrl>minus"),
    ("zoom-reset", "Reset text size", "<Ctrl>0"),
    ("palette", "Command palette", "<Ctrl><Shift>p"),
    ("quick-select", "Quick select (hints)", "<Ctrl><Shift>space"),
    ("preferences", "Preferences", "<Ctrl>comma"),
    ("next-theme", "Next theme", "<Ctrl><Shift>F12"),
    ("toggle-starfield", "Toggle starfield", "<Ctrl><Shift>F11"),
    ("broadcast", "Type into all panes of this tab", "<Ctrl><Shift>i"),
    ("fullscreen", "Fullscreen", "F11"),
    ("clear", "Clear scrollback", "<Ctrl><Shift>k"),
    ("jump-prev-prompt", "Scroll to previous prompt", "<Ctrl><Shift>Up"),
    ("jump-next-prompt", "Scroll to next prompt", "<Ctrl><Shift>Down"),
    ("open-cwd", "Open current folder in file manager", "<Ctrl><Shift>o"),
    ("save-output", "Save scrollback to file", "<Ctrl><Shift>s"),
]
# Alt+1..9 → tab N
for _i in range(1, 10):
    ACTIONS.append((f"tab-{_i}", f"Go to tab {_i}", f"<Alt>{_i}"))

LABELS = {a: l for a, l, _ in ACTIONS}
DEFAULTS = {a: k for a, _, k in ACTIONS}


def accel(settings, action):
    return (settings["keybindings"] or {}).get(action, DEFAULTS.get(action, ""))


def all_accels(settings):
    return {a: accel(settings, a) for a, _, _ in ACTIONS}

<p align="center">
  <img src="data/icons/hicolor/256x256/apps/interstellar.png" width="120" alt="Interstellar logo">
</p>
<h1 align="center">Interstellar Terminal</h1>
<p align="center"><b>A terminal that's out of this world.</b><br>
Tabs, splits, 28 themes, Liquid Glass, an animated starfield, and a settings window for every option.</p>
<p align="center">
  <img alt="GTK 4" src="https://img.shields.io/badge/GTK-4-ffb347?style=flat-square">
  <img alt="VTE" src="https://img.shields.io/badge/engine-VTE-ffb347?style=flat-square">
  <img alt="Linux" src="https://img.shields.io/badge/Linux-any%20distro-ffb347?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-ffb347?style=flat-square">
</p>

![Interstellar with split panes, istl fetch and a build log](docs/hero.png)

Interstellar is written from scratch on GTK 4 and VTE, the same engine GNOME's terminals use, so it's fast and fully compatible: true colour, mouse, OSC 8 hyperlinks, sixel images (when your VTE build has them), bracketed paste and everything `vim`, `tmux` and `htop` expect.

Every option has a switch, slider or picker in **Preferences**, and changes apply to your open terminals as you make them. There's no config file to edit, though there is one if you want it.

## Install: one line, any distro

```bash
curl -fsSL https://raw.githubusercontent.com/rxvy-dev/interstellar/main/get.sh | bash
```

The script downloads Interstellar and installs GTK 4 and VTE with your distro's package manager (it asks once). It then adds Interstellar to your app menu. Start it from there, or type `interstellar` (or the short `istl`).

Update later with `interstellar --update`. Remove it with `interstellar --uninstall`.

<details>
<summary><b>Prefer to clone it yourself?</b></summary>

```bash
git clone https://github.com/rxvy-dev/interstellar.git
cd interstellar
./install.sh
```
</details>

| Distro | Package manager | What gets installed |
|---|---|---|
| Void (glibc and musl) | xbps | `gtk4 vte3-gtk4 python3-gobject python3-cairo` |
| Arch, Manjaro, EndeavourOS, CachyOS, Artix, Garuda | pacman | `gtk4 vte4 python-gobject python-cairo` |
| Debian 12+, Ubuntu 23.04+, Mint 22+, Pop!_OS 24+, Kali | apt | `gir1.2-gtk-4.0 gir1.2-vte-3.91 python3-gi python3-gi-cairo` |
| Fedora, RHEL / Alma / Rocky 9+ | dnf | `gtk4 vte291-gtk4 python3-gobject python3-cairo` |
| openSUSE Tumbleweed, Leap 15.6+ | zypper | `typelib-1_0-Gtk-4_0 typelib-1_0-Vte-3_91 python3-gobject` |
| Alpine, postmarketOS | apk | `gtk4.0 vte3-gtk4 py3-gobject3 py3-cairo` |
| Gentoo | emerge | `gui-libs/gtk x11-libs/vte` (the installer tells you the USE flags) |
| NixOS | — | `nix-shell --run ./bin/interstellar` (uses `shell.nix`) |
| Fedora Silverblue / Kinoite | rpm-ostree | layered packages (or run it in a toolbox) |

The installer also tries to add a nice font (JetBrains Mono or Fira Code) and the helpers for the drop-down terminal. These are optional, and nothing breaks if one isn't packaged on your distro.

Installer options (they work after `get.sh | bash -s --` too):

```bash
./install.sh -y              # no questions
./install.sh --user          # install to ~/.local (no sudo for Interstellar itself)
./install.sh --default       # also make it your default terminal
./install.sh --minimal       # only what's needed to start
./install.sh --no-deps       # don't touch the package manager
./install.sh --print-deps    # show the package command for your distro without running it
./install.sh --check         # what's installed / missing  (same as: interstellar --doctor)
./install.sh --uninstall     # remove it
```

If you don't want to install it, run it from the folder with `./bin/interstellar`.

**Requirements:** Python 3.9+, PyGObject with its cairo bridge, GTK 4.10+, and VTE for GTK 4 (`Vte-3.91` typelib).

## What makes it different

### Space, but useful
- **Animated starfield:** parallax stars drift behind your text, with the odd shooting star. It's drawn once behind the whole window, so it flows across split panes. You can set it to Drift, Twinkle or Still (Still uses no CPU), and choose the density. Toggle it with `Ctrl+Shift+F11`.
- **Space themes:** Event Horizon (the default), Nebula, Supernova, Red Giant, Deep Space, Andromeda, Pulsar and Aurora, plus the classics: Dracula, Catppuccin, Tokyo Night, Gruvbox, Nord, One Dark, Rosé Pine, Kanagawa, Everforest, Solarized, Monokai, GitHub, Matrix and Amber CRT.
- **Background images** with adjustable dimming, **window transparency**, and four window styles: Glass, Solid, Minimal and [Liquid Glass](#liquid-glass).
- **`istl fetch`** prints a space-themed system summary, so your screenshots look good too.

| Nebula | Aurora |
|---|---|
| ![Nebula theme](docs/nebula.png) | ![Aurora theme](docs/aurora.png) |

### Liquid Glass
![The Liquid Glass theme refracting a wallpaper](docs/liquid-glass.png)

The whole window becomes a slab of curved glass, lit along its rim, with the starfield drifting inside it. There are two modes:

- **See-through** (default): you see the real windows behind the terminal, blurred by your compositor (on Hyprland that's `decoration:blur`, which is on by default). Interstellar adds the tint, depth, rim light and border.
- **Wallpaper**: Interstellar refracts your wallpaper itself. The edge bends and splits the light like real glass and the middle frosts it. The wallpaper is found automatically from swww, awww, hyprpaper, waypaper or swaybg, or you can choose a picture. With none, a soft aurora in the theme's colours is used. On Hyprland the glass follows the window, so it bends the part of the wallpaper that's really behind it.

How to use it:
- **Themes:** pick **◈ Liquid Glass**, **◈ Liquid Glass Light** or **◈ Liquid Nebula**, or set *UI style → Liquid Glass* to turn any theme into glass (its background colour becomes the tint).
- **Settings for everything** in *Preferences → Liquid Glass*:
  - opacity, frost, tint, vibrancy, milkiness, depth, grain
  - edge width, refraction, index of refraction, chromatic dispersion, lens, border
  - rim light, highlight width, light direction, stars on the glass
  - corner radius, shadow, tone, quality
  - presets: *Clear*, *Liquid*, *Frosted* and *Smoked*

  Every control applies live.
- **Fast:** it's drawn with OpenGL and only re-renders when the window moves, resizes or a setting changes. The wallpaper is decoded on a background thread at the size it's needed and cached in `~/.cache/interstellar/glass`, so windows open without waiting for it. If OpenGL isn't available, a frosted-glass fallback is used.

On Hyprland, set *Corner radius* to your `decoration:rounding` so the corners line up.

![Liquid Glass preferences](docs/prefs-liquid-glass.png)

### Opens instantly
Interstellar keeps running in the background after you close the last window, so the next one opens straight away: the launcher asks the running copy for a window over D-Bus instead of starting Python and GTK again. Start it at login with `interstellar --daemon` and even the first window is instant. You can switch this off in *Preferences → Behaviour*, and *Menu → Quit* always quits.

```lua
-- Hyprland (Lua config)
hl.on("hyprland.start", function() hl.exec_cmd("interstellar --daemon") end)
```
```ini
# Hyprland (hyprland.conf)
exec-once = interstellar --daemon
```

### Small things that save time
![Command palette](docs/palette.png)

- **Command palette** (`Ctrl+Shift+P`): every action, theme (with live preview), profile, tab and setting, in one fuzzy search box. Type `theme:` to list only themes.
- **Quick select** (`Ctrl+Shift+Space`): every URL, path, `file:line`, git hash, IP address, UUID and e-mail on screen gets a letter. Type the letter to copy it, hold Shift to paste it, or hold Ctrl to open it. You don't need the mouse.

  ![Quick select hints](docs/quick-select.png)
- **Clickable links:** URLs, OSC 8 hyperlinks, paths and compiler errors like `src/main.c:42:7`. `Ctrl+Click` opens them (you can switch this to a plain click). Files open at the right line in `$EDITOR`, or in an editor command you choose (`code -g {file}:{line}`).
- **Safe paste:** Interstellar asks before pasting several lines, or anything containing `sudo`, `rm -rf`, `mkfs` or `curl … | sh`. It shows a preview and has a *Paste as one line* option.
- **Notifications:** when a command that ran for 8+ seconds finishes in a tab you aren't looking at, you get a desktop notification. Click it to jump to that tab.
- **Search the scrollback** (`Ctrl+Shift+F`) with match case, regex and a match count.
- **Jump between prompts** with `Ctrl+Shift+↑/↓`.
- **Save the output** to a file with `Ctrl+Shift+S`.
- **Drag files in** to paste their quoted paths.
- **Copy on select**, a visual bell, and per-pane zoom (`Ctrl+` / `Ctrl−`).
- **Drop-down (quake) terminal:** bind `interstellar --quake` to a key (F12 works well) in your desktop's keyboard settings. It slides down from the top of the screen and hides again. On Wayland it uses `gtk4-layer-shell` when that's installed; on X11 it uses `xdotool`/`wmctrl`.

## Keys

| | |
|---|---|
| New tab / window | `Ctrl+Shift+T` / `Ctrl+Shift+N` |
| Close pane | `Ctrl+Shift+W` |
| Split right / down | `Ctrl+Shift+D` / `Ctrl+Shift+E` |
| Move between panes | `Alt+←↑→↓` |
| Zoom pane | `Ctrl+Shift+Z` |
| Next / previous tab, tab N | `Ctrl+PgDn` / `Ctrl+PgUp`, `Alt+1…9` |
| Move tab | `Ctrl+Shift+PgUp` / `Ctrl+Shift+PgDn` |
| Rename tab | `Ctrl+Shift+R` (or double-click it) |
| Copy / paste | `Ctrl+Shift+C` / `Ctrl+Shift+V` |
| Find | `Ctrl+Shift+F` |
| Command palette | `Ctrl+Shift+P` |
| Quick select | `Ctrl+Shift+Space` |
| Broadcast to panes | `Ctrl+Shift+I` |
| Text size | `Ctrl+` / `Ctrl−` / `Ctrl+0` |
| Previous / next prompt | `Ctrl+Shift+↑` / `Ctrl+Shift+↓` |
| Clear scrollback | `Ctrl+Shift+K` |
| Save output | `Ctrl+Shift+S` |
| Open folder | `Ctrl+Shift+O` |
| Next theme / toggle starfield | `Ctrl+Shift+F12` / `Ctrl+Shift+F11` |
| Preferences / fullscreen | `Ctrl+,` / `F11` |

You can change any of these in Preferences → Keyboard.

## Command line

```bash
interstellar                         # opens a window and restores your last session
interstellar -e htop                 # run a program instead of the shell
interstellar -d ~/code --tab         # open a tab in the window that's already running
interstellar -p Python               # use a profile
interstellar --theme "Deep Space"    # switch theme (and keep it)
interstellar --list-themes
interstellar --import-theme ~/Downloads/gruvbox.toml
interstellar --quake                 # toggle the drop-down terminal
interstellar --daemon                # start in the background at login: every window opens instantly
interstellar --fetch                 # (or: istl fetch) space-themed system info
interstellar --doctor                # check dependencies
interstellar --update | --uninstall | --version | --help
```

It works as the default terminal for file managers and `xdg-terminal-exec`. Run `./install.sh --default` to set that up.

## Files

- `~/.config/interstellar/settings.json`: every setting (Preferences writes it, but you can edit it too)
- `~/.config/interstellar/themes/*.json`: your themes, in this format:
  ```json
  { "name": "My Theme", "fg": "#e6e1d6", "bg": "#050507", "cursor": "#ffb347",
    "selection": "#3a2a12", "accent": "#ffb347", "space": true,
    "palette": ["#14141a", "#ff5c57", "…16 colours: 8 normal then 8 bright…"] }
  ```

## Packages

| | Command |
|---|---|
| Debian / Ubuntu `.deb` | `make deb` → `dist/interstellar_1.0.0_all.deb` |
| Fedora / openSUSE `.rpm` | `make rpm` (uses `packaging/rpm/interstellar.spec`) |
| Arch | `make dist && cp dist/*.tar.gz packaging/ && cd packaging && makepkg -si` |
| Void | copy `packaging/void/template` to `void-packages/srcpkgs/interstellar/` and run `./xbps-src pkg interstellar` |
| Alpine | `packaging/alpine/APKBUILD` |
| Source tarball | `make dist` |

## Publishing your own copy

```bash
./publish.sh                    # creates github.com/<you>/interstellar, pushes, makes a v1.0.0 release (.deb + tarball)
./publish.sh --name myterm      # different repo name   ·   --private   ·   --no-release
```

The script installs and logs in to the GitHub CLI (`gh`) if needed. It also points every link (README, `get.sh`, packages, `interstellar --update`) at your repo.

## Development

```bash
./bin/interstellar --no-restore   # run from the source tree
make test                         # unit tests (themes, importers, settings, keys, palette, quick select)
make check                        # dependency doctor
python3 tools/make_icon.py        # re-render the app icon
```

Code map:

| File | What it does |
|---|---|
| `interstellar/app.py` | Application, command line, CSS, session and quake window |
| `window.py` | Tab bar, tabs, split tree and actions |
| `pane.py` | One terminal: VTE, links, search, paste and process tracking |
| `starfield.py` | The backdrop |
| `prefs.py` | Preferences |
| `palette.py` | Command palette |
| `quickselect.py` | Quick select hints |
| `themes.py` | Themes and importers |
| `chrome.py` | Window CSS |
| `icons.py` | Cairo-drawn icons |
| `fetch.py` | `istl fetch` |

## License
MIT

The Liquid Glass refraction shader (`interstellar/liquid.py`) is adapted from MacShell's Liquid Glass by Rickky, also MIT licensed.

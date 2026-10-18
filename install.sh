#!/usr/bin/env bash
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  Interstellar Terminal installer — any Linux distro                      │
# │                                                                          │
# │    ./install.sh               install everything (asks once)              │
# │    ./install.sh -y            same, no questions                          │
# │    ./install.sh --user        install to ~/.local (no sudo for the app)   │
# │    ./install.sh --no-deps     skip the package manager step               │
# │    ./install.sh --minimal     only what's needed to start                 │
# │    ./install.sh --check       show what's installed / missing             │
# │    ./install.sh --print-deps  show the package command, don't run it      │
# │    ./install.sh --default     also make it your default terminal          │
# │    ./install.sh --uninstall   remove it (add --user if needed)            │
# └──────────────────────────────────────────────────────────────────────────┘
set -euo pipefail
cd "$(dirname "$0")"

MODE=auto; DEPS=1; MINIMAL=0; ACTION=install; YES=0; MAKEDEFAULT=0
for a in "$@"; do
  case "$a" in
    --user) MODE=user ;;
    --system) MODE=system ;;
    --deps) DEPS=1 ;;
    --no-deps) DEPS=0 ;;
    --minimal) MINIMAL=1 ;;
    --default) MAKEDEFAULT=1 ;;
    -y|--yes) YES=1 ;;
    --check|--doctor) ACTION=check ;;
    --uninstall) ACTION=uninstall ;;
    --print-deps) ACTION=print ;;
    -h|--help) sed -n '3,14p' "$0" | sed 's/^# //'; exit 0 ;;
    *) echo "unknown option: $a (try --help)"; exit 2 ;;
  esac
done

# ---------------------------------------------------------------- pretty output
if [ -t 1 ]; then
  A=$'\e[38;5;215m'; P=$'\e[38;5;141m'; D=$'\e[2m'; B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; X=$'\e[0m'
else
  A=; P=; D=; B=; G=; Y=; R=; X=
fi
STEP=0; STEPS=4
banner() {
  printf '%s' "$D"
  printf '        ·    ✦        .        *         ·      .     ✦\n'
  printf '%s' "$A$B"
  cat <<'ART'
   _       _               _       _ _
  (_)_ __ | |_ ___ _ __ __| |_ ___| | | __ _ _ __
  | | '_ \| __/ _ \ '__/ __| __/ _ \ | |/ _` | '__|
  | | | | | ||  __/ |  \__ \ ||  __/ | | (_| | |
  |_|_| |_|\__\___|_|  |___/\__\___|_|_|\__,_|_|
ART
  printf '%s' "$X$D"
  printf '     .      *    ·        ✦      .         ·       *\n'
  printf '%s   T E R M I N A L  —  a terminal that'"'"'s out of this world%s\n\n' "$P" "$X"
}
step() { STEP=$((STEP+1)); printf '\n%s[%d/%d]%s %s%s%s\n' "$A" "$STEP" "$STEPS" "$X" "$B" "$*" "$X"; }
ok()   { printf '  %s✔%s %s\n' "$G" "$X" "$*"; }
info() { printf '  %s•%s %s\n' "$D" "$X" "$*"; }
warn() { printf '  %s!%s %s\n' "$Y" "$X" "$*"; }
die()  { printf '  %s✖ %s%s\n' "$R" "$*" "$X"; exit 1; }
ask() {   # ask "question" -> 0 for yes (default yes); reads the real terminal even under curl | bash
  [ "$YES" = 1 ] && return 0
  local ans=""
  if [ -r /dev/tty ]; then
    printf '  %s?%s %s %s[Y/n]%s ' "$A" "$X" "$1" "$D" "$X" >&2
    read -r ans < /dev/tty || ans=""
  fi
  case "$ans" in n|N|no|NO) return 1 ;; *) return 0 ;; esac
}
spin() {  # spin "label" cmd...  — run quietly with a spinner, show the log if it fails
  local label=$1; shift
  local log; log=$(mktemp)
  ( "$@" ) >"$log" 2>&1 &
  local pid=$! i=0 frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
  if [ -t 1 ]; then
    while kill -0 "$pid" 2>/dev/null; do
      printf '\r  %s%s%s %s' "$A" "${frames:i++%10:1}" "$X" "$label"; sleep 0.1
    done
    printf '\r\033[K'
  fi
  if wait "$pid"; then ok "$label"; rm -f "$log"; return 0; fi
  warn "$label failed — last lines:"; tail -n 15 "$log" | sed 's/^/      /'; rm -f "$log"; return 1
}

# ---------------------------------------------------------------- privileges
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null; then SUDO=sudo
  elif command -v doas >/dev/null; then SUDO=doas
  fi
fi
if [ "$MODE" = auto ]; then
  if [ "$(id -u)" -eq 0 ] || [ -n "$SUDO" ]; then MODE=system; else MODE=user; fi
fi
[ -n "$SUDO" ] && [ "$(id -u)" -ne 0 ] && SUDO_PROMPT="  password for %u (to install packages): " && export SUDO_PROMPT

# ---------------------------------------------------------------- distro detection
. /etc/os-release 2>/dev/null || true
IDS=" ${ID:-} ${ID_LIKE:-} "
detect_pm() {
  case "$IDS" in *" nixos "*) echo nix; return ;; esac
  if [ -e /run/ostree-booted ] && command -v rpm-ostree >/dev/null; then echo rpm-ostree; return; fi
  for pm in xbps-install pacman apt-get dnf zypper apk emerge eopkg urpmi swupd yum; do
    if command -v "$pm" >/dev/null; then echo "$pm"; return; fi
  done
  echo unknown
}
PM=$(detect_pm)

# CORE = needed to start. EXTRA = nice to have (a good monospace font, drop-down terminal helpers).
deps_for() {
  case "$1" in
    pacman)       CORE="python python-gobject python-cairo gtk4 vte4 make"
                  EXTRA="ttf-jetbrains-mono gtk4-layer-shell xdotool wmctrl python-pywayland" ;;
    apt-get)      CORE="python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-vte-3.91 make"
                  EXTRA="fonts-jetbrains-mono xdotool wmctrl python3-pywayland" ;;
    dnf|yum)      CORE="python3 python3-gobject python3-cairo gtk4 vte291-gtk4 make"
                  EXTRA="jetbrains-mono-fonts gtk4-layer-shell xdotool wmctrl python3-pywayland" ;;
    rpm-ostree)   CORE="python3-gobject python3-cairo gtk4 vte291-gtk4"
                  EXTRA="jetbrains-mono-fonts" ;;
    zypper)       CORE="python3 python3-gobject python3-gobject-cairo python3-gobject-Gdk typelib-1_0-Gtk-4_0 typelib-1_0-Vte-3_91 make"
                  EXTRA="jetbrains-mono-fonts xdotool wmctrl" ;;
    apk)          CORE="python3 py3-gobject3 py3-cairo gtk4.0 vte3-gtk4 make"
                  EXTRA="font-jetbrains-mono gtk4-layer-shell xdotool wmctrl" ;;
    xbps-install) CORE="python3 python3-gobject python3-cairo gtk4 vte3-gtk4 make"
                  EXTRA="font-firacode gtk4-layer-shell xdotool wmctrl" ;;
    emerge)       CORE="dev-python/pygobject dev-python/pycairo gui-libs/gtk x11-libs/vte"
                  EXTRA="media-fonts/jetbrains-mono x11-misc/xdotool" ;;
    eopkg)        CORE="python3 python-gobject python-cairo libgtk-4 vte-gtk4 make"
                  EXTRA="" ;;
    urpmi)        CORE="python3-gobject3 python3-cairo gtk4 make"
                  EXTRA="" ;;
    swupd)        CORE="desktop-dev python3-basic"
                  EXTRA="" ;;
    *)            CORE=""; EXTRA="" ;;
  esac
}

pkg_cmd() {   # pkg_cmd "packages"
  local PKGS=$1
  case "$PM" in
    pacman)       echo "$SUDO pacman -S --needed --noconfirm $PKGS" ;;
    apt-get)      echo "$SUDO apt-get update -qq && $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y $PKGS" ;;
    dnf)          echo "$SUDO dnf install -y $PKGS" ;;
    yum)          echo "$SUDO yum install -y $PKGS" ;;
    rpm-ostree)   echo "$SUDO rpm-ostree install --idempotent $PKGS" ;;
    zypper)       echo "$SUDO zypper --non-interactive install $PKGS" ;;
    apk)          echo "$SUDO apk add $PKGS" ;;
    xbps-install) echo "$SUDO xbps-install -Sy $PKGS" ;;
    emerge)       echo "$SUDO emerge --ask=n --noreplace $PKGS" ;;
    eopkg)        echo "$SUDO eopkg install -y $PKGS" ;;
    urpmi)        echo "$SUDO urpmi --auto $PKGS" ;;
    swupd)        echo "$SUDO swupd bundle-add $PKGS" ;;
    *)            echo "" ;;
  esac
}

pick_python() {
  for py in /usr/bin/python3 "$(command -v python3 2>/dev/null)" /usr/bin/python3.1[0-9] /usr/bin/python3.9; do
    [ -x "$py" ] && "$py" -c 'import gi' 2>/dev/null && { echo "$py"; return; }
  done
  command -v python3 2>/dev/null || echo python3
}
doctor() { PYTHONPATH="$PWD" "$(pick_python)" -c 'import sys; from interstellar.doctor import main; sys.exit(main())'; }
has_core() {
  "$(pick_python)" - <<'PY' 2>/dev/null
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Vte", "3.91"); gi.require_foreign("cairo")
from gi.repository import Gtk, Vte
assert (Gtk.get_major_version(), Gtk.get_minor_version()) >= (4, 10)
PY
}

# ---------------------------------------------------------------- simple actions
case "$ACTION" in
  print)
    deps_for "$PM"
    echo "${PRETTY_NAME:-unknown distro} · $PM"
    c=$(pkg_cmd "$CORE"); echo "  required: ${c:-(no automatic command for this system — see README)}"
    [ -n "$EXTRA" ] && echo "  optional: $(pkg_cmd "$EXTRA")"
    exit 0 ;;
  check) doctor; exit $? ;;
  uninstall)
    for p in "$HOME/.local" /usr/local /usr; do
      if [ -e "$p/bin/interstellar" ] && [ -d "$p/share/interstellar" ]; then
        if [ -w "$p/bin" ]; then make -s uninstall PREFIX="$p"; else $SUDO make -s uninstall PREFIX="$p"; fi
        ok "removed from $p"
      fi
    done
    info "settings kept in ~/.config/interstellar (delete it to reset)"; exit 0 ;;
esac

# ---------------------------------------------------------------- install
banner
step "Scanning your system"
ok "${PRETTY_NAME:-Linux} · package manager: $PM · install to: $([ "$MODE" = user ] && echo '~/.local' || echo /usr/local)"
[ "$MODE" = user ] && [ -z "$SUDO" ] && [ "$(id -u)" -ne 0 ] && info "no sudo/doas — Interstellar goes to ~/.local; system packages must already be installed"

step "Dependencies"
deps_for "$PM"
if [ "$DEPS" = 0 ]; then
  info "skipped (--no-deps)"
elif [ "$PM" = nix ]; then
  info "NixOS: run it with the bundled shell —  nix-shell --run ./bin/interstellar"
elif [ "$PM" = unknown ]; then
  warn "unknown package manager — install: Python 3.9+, PyGObject + pycairo, GTK 4.10+ and VTE for GTK 4 (vte-2.91-gtk4)"
elif [ "$MODE" = user ] && [ -z "$SUDO" ] && [ "$(id -u)" -ne 0 ]; then
  has_core && ok "GTK 4 and VTE are already installed" || warn "needs root to install packages — ask your admin, or run:  $(pkg_cmd "$CORE")"
else
  case "$PM" in
    emerge) info "Gentoo: x11-libs/vte needs USE=\"gtk4 introspection\"; gui-libs/gtk needs USE=\"introspection\"" ;;
    rpm-ostree) info "immutable system: packages are layered and need a reboot (or use: toolbox create && toolbox enter)" ;;
    urpmi|eopkg|swupd) info "package names for $PM are best-effort" ;;
  esac
  info "required: $D$CORE$X"
  [ "$MINIMAL" = 0 ] && [ -n "$EXTRA" ] && info "optional: $D$EXTRA$X"
  if ask "Install these packages?"; then
    if [ "$SUDO" = sudo ]; then sudo -v < /dev/tty 2>/dev/null || sudo -v || die "sudo failed"; fi
    run_pkgs() { if [ "$SUDO" = doas ]; then bash -c "$1"; else spin "$2" bash -c "$1"; fi; }
    if has_core; then ok "GTK 4 + VTE already installed"
    else run_pkgs "$(pkg_cmd "$CORE")" "installing GTK 4, VTE and Python bindings" || warn "package install failed — see the check below"
    fi
    if [ "$MINIMAL" = 0 ] && [ -n "$EXTRA" ]; then
      # optional packages one by one, so a name that doesn't exist on this distro can't block the rest
      OK_EXTRA=""
      for p in $EXTRA; do
        if bash -c "$(pkg_cmd "$p")" >/dev/null 2>&1; then OK_EXTRA="$OK_EXTRA $p"; fi
      done
      [ -n "$OK_EXTRA" ] && ok "extras:$OK_EXTRA" || info "no optional extras installed (that's fine)"
    fi
  else
    info "skipped"
  fi
fi

step "Installing Interstellar"
command -v make >/dev/null || die "'make' is missing — install it with your package manager and run this again"
if [ "$MODE" = user ]; then
  spin "copying files to ~/.local" make -s install PREFIX="$HOME/.local"
  LINE='export PATH="$HOME/.local/bin:$PATH"'
  for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
    [ -f "$rc" ] && ! grep -qs '\.local/bin' "$rc" && echo "$LINE" >> "$rc"
  done
  if [ -d "$HOME/.config/fish" ] && command -v fish >/dev/null; then fish -c 'fish_add_path -U $HOME/.local/bin' 2>/dev/null || true; fi
  case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) info "open a new terminal so ~/.local/bin is on your PATH" ;; esac
else
  [ "$SUDO" = sudo ] && { sudo -v < /dev/tty 2>/dev/null || sudo -v || die "sudo failed"; }
  if [ "$SUDO" = doas ]; then doas make -s install PREFIX=/usr/local && ok "copied files to /usr/local"
  else spin "copying files to /usr/local" $SUDO make -s install PREFIX=/usr/local; fi
fi
ok "app menu entry + icon installed · commands: interstellar, istl"

if [ "$MAKEDEFAULT" = 1 ]; then
  BIN=$([ "$MODE" = user ] && echo "$HOME/.local/bin/interstellar" || echo /usr/local/bin/interstellar)
  if command -v gsettings >/dev/null; then
    gsettings set org.gnome.desktop.default-applications.terminal exec "$BIN" 2>/dev/null && ok "default terminal for GNOME apps"
  fi
  mkdir -p "$HOME/.config"
  { echo "io.github.interstellar.Terminal.desktop"; grep -v -x "io.github.interstellar.Terminal.desktop" "$HOME/.config/xdg-terminals.list" 2>/dev/null || true; } > "$HOME/.config/xdg-terminals.list.new"
  mv "$HOME/.config/xdg-terminals.list.new" "$HOME/.config/xdg-terminals.list" && ok "default in xdg-terminals.list (xdg-terminal-exec)"
  if [ "$MODE" = system ] && command -v update-alternatives >/dev/null; then
    $SUDO update-alternatives --install /usr/bin/x-terminal-emulator x-terminal-emulator "$BIN" 60 >/dev/null 2>&1 && ok "x-terminal-emulator → interstellar"
  fi
fi

step "Final check"
TMPD=$(mktemp)
if doctor >"$TMPD" 2>&1; then
  grep -E "✔|•" "$TMPD" | sed 's/^ */  /'
  rm -f "$TMPD"
  printf '\n  %s%s✦ Interstellar is installed.%s  Start it from your app menu, or run:  %sinterstellar%s\n' "$G" "$B" "$X" "$B" "$X"
  printf '  %sDrop-down terminal: bind  interstellar --quake  to a key (e.g. F12) in your desktop settings.%s\n\n' "$D" "$X"
else
  cat "$TMPD"; rm -f "$TMPD"
  printf '\n  %sSomething required is missing.%s Re-run ./install.sh, or install the ✖ items with your package manager.\n\n' "$R" "$X"
  exit 1
fi

#!/bin/sh
# Build dist/interstellar_<ver>_all.deb (Debian 12+, Ubuntu 23.04+, Mint 22+, Pop!_OS 24+…). Needs dpkg-deb.
set -e
cd "$(dirname "$0")/.."
VER=$(sed -n 's/^VERSION := //p' Makefile)
ROOT=$(mktemp -d)
make -s install PREFIX=/usr DESTDIR="$ROOT"
mkdir -p "$ROOT/DEBIAN" dist
cat > "$ROOT/DEBIAN/control" <<CTL
Package: interstellar
Version: $VER
Section: x11
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0 (>= 4.10), gir1.2-vte-3.91
Recommends: fonts-jetbrains-mono
Suggests: xdotool, wmctrl
Provides: x-terminal-emulator
Maintainer: rxvy <https://github.com/rxvy-dev>
Homepage: https://github.com/rxvy-dev/interstellar
Description: Terminal emulator that's out of this world
 GTK 4 + VTE terminal with tabs, split panes, an animated starfield, Liquid Glass, 28 themes,
 a theme studio, a command palette, quick-select hints, safe paste, session
 restore, a drop-down mode and a GUI for every setting.
CTL
find "$ROOT/usr" -type d -exec chmod 755 {} +
dpkg-deb --root-owner-group --build "$ROOT" "dist/interstellar_${VER}_all.deb" >/dev/null
rm -rf "$ROOT"
echo "dist/interstellar_${VER}_all.deb"

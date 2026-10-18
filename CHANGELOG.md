# Changelog

## Unreleased
- **Liquid Glass:** a new window style that turns the window into curved glass with a rim highlight and the starfield drifting inside. *See-through* mode (default) shows the windows behind it through your compositor's blur; *Wallpaper* mode refracts your wallpaper
- Three Liquid themes: Liquid Glass, Liquid Glass Light and Liquid Nebula (◈ filter in the theme gallery)
- *Preferences → Liquid Glass*: mode, opacity, frost, tint, vibrancy, milkiness, depth, grain, edge width, refraction, index of refraction, chromatic dispersion, lens, border, rim light, highlight width, light direction, corner radius, shadow, tone, quality, stars on glass, wallpaper, and Clear / Liquid / Frosted / Smoked presets
- The wallpaper is decoded on a background thread at the size it's needed and cached on disk, so windows never wait for it
- Wallpaper auto-detection (swww, awww, hyprpaper, waypaper, swaybg) and live window tracking on Hyprland
- OpenGL rendering through libepoxy (no new dependencies) with a cairo fallback
- The refraction shader is adapted from MacShell's Liquid Glass by Rickky (MIT)
- **Instant windows:** Interstellar stays running in the background after the last window closes (*Preferences → Behaviour*), and the launcher asks the running copy for a window over D-Bus instead of starting Python and GTK again
- `interstellar --daemon` starts it at login without a window, so even the first window is instant

## 1.0.0
First release of Interstellar Terminal.

- GTK 4 + VTE terminal: true colour, mouse, OSC 8 hyperlinks, bracketed paste
- Animated parallax starfield with shooting stars (Drift / Twinkle / Still), background images, opacity, three window styles
- 25 themes, including 8 space originals (Event Horizon, Nebula, Supernova, Red Giant, Deep Space, Andromeda, Pulsar, Aurora)
- Preferences for every option, applied live: theme gallery with hover preview, Theme Studio, fonts, cursor, profiles, key rebinding, custom CSS, settings search, import/export
- Theme import from kitty, Alacritty (TOML/YAML) and base16
- Tabs (drag to reorder, rename, detach) and split panes with keyboard navigation, pane zoom and broadcast input
- Session restore (tabs, splits, folders, names)
- Command palette, quick select hints, clickable URLs / paths / `file:line` errors, scrollback search with regex
- Safe paste, finished-command notifications, activity dots, prompt jumping, save output
- Drop-down (quake) mode via `interstellar --quake`
- `istl fetch` system summary
- One-line installer for every major distro, `--doctor`, `--update`, `--uninstall`, packages for deb / rpm / Arch / Void / Alpine

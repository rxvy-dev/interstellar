# Changelog

## Unreleased
- **Liquid Glass:** a new window style that turns the window into curved, refracting glass over your wallpaper, with a rim highlight and the starfield drifting inside
- Three Liquid themes: Liquid Glass, Liquid Glass Light and Liquid Nebula (◈ filter in the theme gallery)
- *Preferences → Liquid Glass*: frost, refraction, edge width, chromatic dispersion, lens, tint, vibrancy, rim light, grain, corner radius, shadow, tone, stars on glass, wallpaper, and Crystal / Liquid / Frosted / Smoked presets
- Wallpaper auto-detection (swww, awww, hyprpaper, waypaper, swaybg) and live window tracking on Hyprland
- OpenGL rendering through libepoxy (no new dependencies) with a cairo fallback
- The refraction shader is adapted from MacShell's Liquid Glass by Rickky (MIT)

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

"""Builds the window CSS from the active theme + UI style (glass | solid | minimal)."""
from .themes import luminance


def _rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgba(h, a):
    r, g, b = _rgb(h)
    return f"rgba({r},{g},{b},{a:.3f})"


def mix(a, b, t):
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#%02x%02x%02x" % (round(ra + (rb - ra) * t), round(ga + (gb - ga) * t), round(ba + (bb - ba) * t))


def build_css(theme, style="glass", opacity=1.0, custom="", glass=None):
    """glass: {"radius": px, "shadow": 0..1} for the Liquid Glass style."""
    bg, fg, acc = theme["bg"], theme["fg"], theme["accent"]
    dark = luminance(bg) < 0.45
    lift = "#ffffff" if dark else "#000000"
    bar_a = {"glass": 0.72, "solid": 1.0, "minimal": 1.0, "liquid": 0.0}.get(style, 0.8) * max(opacity, 0.35)
    bar = mix(bg, lift, 0.035 if style != "minimal" else 0.0)
    soft = mix(bg, fg, 0.55)
    hover = rgba(fg, 0.07)
    radius = {"glass": 10, "solid": 6, "minimal": 4, "liquid": 12}.get(style, 8)
    acc_fg = "#000000" if luminance(acc) > 0.5 else "#ffffff"
    return f"""
window.istl, window.istl.background {{ background: transparent; color: {fg}; }}
.istl-bar {{ background-color: {rgba(bar, bar_a)}; color: {fg};
  border-bottom: 1px solid {rgba(fg, 0.07)}; min-height: 40px; padding: 0 4px; }}
.istl-bar.bottom {{ border-bottom: none; border-top: 1px solid {rgba(fg, 0.07)}; }}
.istl-bar button, .istl-pop button.flat {{ color: {soft}; background: none; border: none; box-shadow: none;
  border-radius: {radius - 2}px; min-height: 28px; min-width: 28px; padding: 0 6px; }}
.istl-bar button:hover {{ background: {hover}; color: {fg}; }}
.istl-bar windowcontrols button {{ min-height: 22px; min-width: 22px; padding: 2px; margin: 0 2px; }}
.istl-bar windowcontrols button image {{ background: {rgba(fg, 0.08)}; border-radius: 99px; padding: 3px; }}
.istl-bar windowcontrols button:hover image {{ background: {rgba(acc, 0.85)}; color: {acc_fg}; }}
.istl-brand {{ color: {acc}; font-weight: 800; letter-spacing: 1px; margin: 0 8px 0 6px; }}

.istl-tab {{ border-radius: {radius}px; padding: 0 4px 0 10px; margin: 6px 2px;
  min-height: 28px; color: {soft}; background: transparent; transition: all 160ms ease; }}
.istl-tab:hover {{ background: {hover}; color: {fg}; }}
.istl-tab.active {{ background: {rgba(acc, 0.16)}; color: {fg};
  box-shadow: inset 0 -2px {acc}; }}
.istl-tab label.title {{ font-weight: 500; }}
.istl-tab.active label.title {{ font-weight: 700; }}
.istl-tab button.close {{ min-width: 18px; min-height: 18px; padding: 0; margin-left: 4px;
  border-radius: 99px; opacity: 0.0; }}
.istl-tab:hover button.close, .istl-tab.active button.close {{ opacity: 0.75; }}
.istl-tab button.close:hover {{ background: {rgba(acc, 0.85)}; color: {acc_fg}; opacity: 1; }}
.istl-dot {{ min-width: 7px; min-height: 7px; border-radius: 99px; background: {acc}; margin-right: 2px; }}
.istl-dot.done {{ background: #5fd38d; }}
.istl-dot.bell {{ background: #ff5c57; }}
.istl-tab .icon {{ color: {acc}; }}
.istl-tab entry {{ min-height: 22px; padding: 0 4px; }}

stack.istl-pages, paned.istl, paned.istl > * {{ background: transparent; }}
paned.istl > separator {{ background: {rgba(fg, 0.10)}; min-width: 2px; min-height: 2px; }}
paned.istl > separator:hover {{ background: {acc}; }}
.istl-pane {{ border-radius: {0 if style == 'minimal' else 4}px; border: 1px solid transparent; }}
.istl-pane.split.focused {{ border-color: {rgba(acc, 0.55)}; }}
.istl-pane.split:not(.focused) vte-terminal {{ opacity: 0.82; }}
.istl-pane.flash {{ background: {rgba(acc, 0.18)}; }}
.istl-pane.broadcast {{ border-color: #ff5c57; }}
vte-terminal {{ background: transparent; }}
scrollbar.istl {{ background: transparent; border: none; }}
scrollbar.istl slider {{ background: {rgba(fg, 0.22)}; min-width: 4px; border-radius: 99px; }}
scrollbar.istl:hover slider {{ background: {rgba(acc, 0.7)}; min-width: 7px; }}

.istl-float {{ background: {rgba(mix(bg, lift, 0.06), 0.94)}; color: {fg};
  border: 1px solid {rgba(fg, 0.12)}; border-radius: {radius + 2}px; padding: 6px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.45); }}
.istl-float entry {{ background: {rgba(fg, 0.06)}; color: {fg}; border: 1px solid {rgba(fg, 0.10)};
  border-radius: {radius - 2}px; min-height: 30px; caret-color: {acc}; }}
.istl-float entry:focus-within {{ border-color: {acc}; outline: none; box-shadow: none; }}
.istl-float button {{ color: {soft}; background: none; border: none; box-shadow: none; min-height: 26px; min-width: 26px; padding: 0 6px; border-radius: {radius - 3}px; }}
.istl-float button:hover {{ background: {hover}; color: {fg}; }}
.istl-float button:checked {{ background: {rgba(acc, 0.25)}; color: {fg}; }}
.istl-float label.dim, .dim {{ color: {soft}; }}
.istl-float list, .istl-float listview {{ background: transparent; color: {fg}; }}
.istl-float row {{ border-radius: {radius - 3}px; padding: 6px 8px; }}
.istl-float row:selected {{ background: {rgba(acc, 0.22)}; color: {fg}; }}
.istl-float .kbd {{ font-family: monospace; font-size: 0.85em; color: {soft}; background: {rgba(fg, 0.07)};
  border-radius: 4px; padding: 1px 6px; }}
.istl-float .accent {{ color: {acc}; }}
.istl-banner {{ background: {rgba(mix(bg, lift, 0.08), 0.95)}; color: {fg}; border-radius: {radius}px;
  border: 1px solid {rgba(acc, 0.4)}; padding: 8px 12px; }}
.istl-banner button {{ background: {acc}; color: {acc_fg}; border: none; border-radius: {radius - 3}px; padding: 2px 12px; }}
.istl-toast {{ background: {rgba(mix(bg, lift, 0.1), 0.96)}; color: {fg}; border-radius: 99px;
  border: 1px solid {rgba(acc, 0.45)}; padding: 6px 16px; margin-bottom: 18px; }}
.istl-hint {{ background: {acc}; color: {acc_fg}; font-weight: 800; font-family: monospace; border-radius: 3px; padding: 0 3px; }}
popover.istl-pop > contents {{ background: {mix(bg, lift, 0.06)}; color: {fg}; border: 1px solid {rgba(fg, 0.12)}; }}
popover.istl-pop modelbutton:hover {{ background: {rgba(acc, 0.2)}; }}
{_liquid_css(theme, glass or {}) if style == "liquid" else ""}
{custom or ''}
"""


def _liquid_css(theme, glass):
    """The window itself is the glass slab (drawn by glass.py): everything on it stays see-through."""
    fg, acc = theme["fg"], theme["accent"]
    r = int(glass.get("radius", 16))
    sh = max(0.0, min(1.0, float(glass.get("shadow", 0.5))))
    hi = rgba("#ffffff", 0.16 if luminance(theme["bg"]) < 0.45 else 0.55)
    return f"""
window.istl.liquid, window.istl.liquid.background {{ background: transparent; }}
window.istl.liquid.csd {{ border-radius: {r}px;
  box-shadow: 0 18px 46px rgba(0,0,0,{0.55 * sh:.3f}), 0 4px 12px rgba(0,0,0,{0.30 * sh:.3f}); }}
window.istl.liquid.csd.maximized, window.istl.liquid.csd.fullscreen,
window.istl.liquid.csd.tiled, window.istl.liquid.csd.tiled-top, window.istl.liquid.csd.tiled-bottom,
window.istl.liquid.csd.tiled-left, window.istl.liquid.csd.tiled-right {{ border-radius: 0; box-shadow: none; }}
window.istl.liquid .istl-bar, window.istl.liquid headerbar.istl-bar {{ background: transparent; box-shadow: none;
  border-bottom: 1px solid {rgba(fg, 0.08)}; }}
window.istl.liquid .istl-bar.bottom {{ border-bottom: none; border-top: 1px solid {rgba(fg, 0.08)}; }}
window.istl.liquid .istl-tab.active {{ background: {rgba("#ffffff", 0.10)}; box-shadow: inset 0 1px {hi},
  inset 0 0 0 1px {rgba(fg, 0.10)}; }}
window.istl.liquid .istl-tab.active label.title {{ color: {fg}; }}
window.istl.liquid .istl-tab .icon, window.istl.liquid .istl-brand {{ color: {acc}; }}
window.istl.liquid paned.istl > separator {{ background: {rgba(fg, 0.12)}; }}
"""


PREFS_CSS = """
.prefs-side { background: alpha(currentColor, 0.03); }
.prefs-side row { padding: 8px 12px; border-radius: 8px; margin: 2px 6px; }
.prefs-title { font-size: 1.5em; font-weight: 800; margin-bottom: 4px; }
.prefs-sub { opacity: 0.65; margin-bottom: 14px; }
.prefs-group { font-weight: 700; opacity: 0.75; margin-top: 14px; margin-bottom: 4px; font-size: 0.9em; letter-spacing: 1px; }
.prefs-card { background: alpha(currentColor, 0.04); border-radius: 12px; padding: 4px 0; }
.prefs-row { padding: 10px 14px; min-height: 34px; }
.prefs-row + .prefs-row { border-top: 1px solid alpha(currentColor, 0.06); }
.prefs-row .desc { opacity: 0.6; font-size: 0.88em; }
.theme-tile { border-radius: 12px; padding: 0; border: 2px solid transparent; background: none; }
.theme-tile.active { border-color: @accent_color; }
.theme-tile label { font-size: 0.88em; }
.swatch-btn { min-width: 30px; min-height: 30px; padding: 0; }
.kbd-btn { font-family: monospace; min-width: 150px; }
"""

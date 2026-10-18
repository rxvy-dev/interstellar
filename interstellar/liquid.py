"""Liquid Glass: the pure (no GTK) half. Settings → shader parameters, the GLSL itself, wallpaper
detection output parsing and Hyprland monitor maths. The widget that draws it lives in glass.py.

The refraction shader is adapted from MacShell's Liquid Glass by Rickky (MIT License):
a rounded-rect SDF gives the distance to the edge, a convex "squircle" bezel turns that into a surface
normal, Snell's law bends the view ray through it, and the backdrop is sampled per colour channel
(dispersion) through a mip-level disk blur, then graded (vibrancy, tint, milky lift) and lit
(specular rim, meniscus, inner depth).
"""
import os

from .themes import luminance

STYLE = "liquid"

# setting key -> (default, min, max). Kept here so Preferences, tests and the shader agree.
GLASS_KEYS = {
    "glass_frost": (0.5, 0.0, 1.0),        # backdrop blur
    "glass_refraction": (1.0, 0.0, 3.0),   # how hard the rim bends the backdrop
    "glass_edge": (26, 6, 80),             # width of the curved rim, px
    "glass_dispersion": (1.0, 0.0, 4.0),   # chromatic split at the rim
    "glass_tint": (0.45, 0.0, 1.0),        # flat theme-colour tint (readability)
    "glass_vibrancy": (1.3, 0.0, 2.5),     # backdrop saturation
    "glass_rim": (0.7, 0.0, 2.0),          # specular edge highlight
    "glass_lens": (0.3, 0.0, 1.0),         # whole-slab magnifying lens
    "glass_grain": (0.3, 0.0, 1.0),        # fine noise
    "glass_radius": (16, 0, 40),           # corner radius, px
    "glass_shadow": (0.5, 0.0, 1.0),       # drop shadow under the window (floating windows)
}
GLASS_DEFAULTS = {k: v[0] for k, v in GLASS_KEYS.items()}
GLASS_DEFAULTS.update({
    "glass_tone": "auto",                  # auto | dark | light
    "glass_wallpaper": "",                 # "" = detect from swww / awww / hyprpaper / waypaper / swaybg
    "glass_stars": True,                   # keep the starfield drifting on top of the glass
    "glass_follow": True,                  # track the window's position on screen (Hyprland)
})


def is_liquid(style, theme):
    """Liquid themes switch the window to Liquid Glass; any theme can use it via the UI style."""
    return style == STYLE or bool(theme and theme.get("liquid"))


def effective_style(style, theme):
    return STYLE if is_liquid(style, theme) else style


def _num(s, k):
    d, lo, hi = GLASS_KEYS[k]
    try:
        v = float(s[k])
    except (TypeError, ValueError, KeyError):
        v = float(d)
    return max(lo, min(hi, v))


def is_dark(s, theme):
    tone = s["glass_tone"] or "auto"
    if tone == "dark":
        return True
    if tone == "light":
        return False
    return luminance(theme["bg"]) < 0.5


def _rgbf(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def shader_params(s, theme, maximized=False):
    """Settings → the uniforms the shader takes (all sizes in logical px)."""
    refr = _num(s, "glass_refraction")
    return {
        "radius": 0.0 if maximized else _num(s, "glass_radius"),
        "bezel": _num(s, "glass_edge"),
        "thickness": 24.0 * refr * 1.6,
        "dispersion": 0.078 * _num(s, "glass_dispersion") * (0.4 + 0.6 * min(refr, 1.5)),
        "blurPx": 1.5 + _num(s, "glass_frost") * 34.0,
        "tintMix": _num(s, "glass_tint") * 0.8,
        "tintColor": _rgbf(theme["bg"]),
        "saturation": _num(s, "glass_vibrancy"),
        "dark": 1.0 if is_dark(s, theme) else 0.0,
        "rim": _num(s, "glass_rim"),
        "grain": 0.02 * _num(s, "glass_grain"),
        "magnify": 0.06 * _num(s, "glass_lens"),
        "ringW": 0.0 if maximized else 1.0,
    }


# ----------------------------------------------------------------------------------- shader
VERTEX = """
out vec2 vPos;
void main() {
    vec2 v = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    gl_Position = vec4(v * 2.0 - 1.0, 0.0, 1.0);
}
"""

FRAGMENT = """
out vec4 fragColor;

uniform sampler2D src;
uniform vec2  glassSize;   // the glass slab (= the widget), logical px
uniform vec2  srcSize;     // the monitor the backdrop texture covers, logical px
uniform vec2  srcOffset;   // the widget's top-left on that monitor, logical px
uniform float fbHeight;    // framebuffer height, device px
uniform float scale;       // device px per logical px
uniform float radius;
uniform float bezel;
uniform float thickness;
uniform float dispersion;
uniform float blurPx;
uniform float tintMix;
uniform vec3  tintColor;
uniform float saturation;
uniform float dark;
uniform float rim;
uniform float grain;
uniform float magnify;
uniform float ringW;

const int   TAPS   = 24;
const float GOLDEN = 2.39996323;

vec3 backdropLod(vec2 p, float lod) {
    vec2 uv = (p + srcOffset) / srcSize;
    return textureLod(src, clamp(uv, vec2(0.001), vec2(0.999)), lod).rgb;
}

float ign(vec2 p) { return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }

vec3 blurredDisp(vec2 p, vec2 disp, float disperse, float rad) {
    float R   = max(rad, 0.5) * 1.5;
    float gap = R * sqrt(3.14159265 / float(TAPS));
    float lod = clamp(log2(max(gap, 1.0)) + 0.35, 0.0, 8.0);
    float rot = ign(gl_FragCoord.xy) * 6.2831853;
    vec3  acc = vec3(0.0);
    float wsum = 0.0;
    for (int i = 0; i < TAPS; ++i) {
        float fi = float(i) + 0.5;
        float r  = sqrt(fi / float(TAPS));
        float a  = fi * GOLDEN + rot;
        float w  = exp(-2.2 * r * r);
        vec2  o  = vec2(cos(a), sin(a)) * r * R;
        vec3  c;
        c.r = backdropLod(p + o + disp * (1.0 + disperse), lod).r;
        c.g = backdropLod(p + o + disp,                    lod).g;
        c.b = backdropLod(p + o + disp * (1.0 - disperse), lod).b;
        acc  += c * w;
        wsum += w;
    }
    return acc / wsum;
}

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float roundBox(vec2 q, vec2 hs, float r) {
    vec2 d = abs(q) - (hs - r);
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r;
}

void main() {
    vec2 p  = vec2(gl_FragCoord.x, fbHeight - gl_FragCoord.y) / scale;
    vec2 hs = glassSize * 0.5;
    vec2 q  = p - hs;
    float r = min(radius, min(hs.x, hs.y));

    float sd  = roundBox(q, hs, r);
    float cov = clamp(0.5 - sd * scale, 0.0, 1.0);
    if (cov <= 0.0) { fragColor = vec4(0.0); return; }

    // distance to the edge + outward edge direction
    float t = max(-sd, 0.0);
    vec2 d2 = abs(q) - (hs - r);
    vec2 sg = vec2(q.x >= 0.0 ? 1.0 : -1.0, q.y >= 0.0 ? 1.0 : -1.0);
    vec2 m  = max(d2, 0.0);
    vec2 g  = (length(m) > 1e-4) ? normalize(m) * sg
                                 : ((d2.x > d2.y) ? vec2(sg.x, 0.0) : vec2(0.0, sg.y));

    // convex squircle bezel -> surface normal
    float bz    = max(bezel, 1.0) * 1.45;
    float u     = clamp(t / bz, 0.0, 1.0);
    float om    = 1.0 - u;
    float om4   = om * om * om * om;
    float slope = (om * om * om) / pow(max(1.0 - om4, 1e-3), 0.75);
    slope = min(slope, 7.0);
    vec3 n = normalize(vec3(g * slope, 1.0));

    // refraction: glass n ~ 1.5, the ray enters straight down
    vec3 rd   = refract(vec3(0.0, 0.0, -1.0), n, 1.0 / 1.5);
    vec2 disp = rd.xy / max(-rd.z, 0.2) * thickness * 1.35;

    // the slab is a gentle vertical lens; the blur is crisper right at the curved rim
    vec2 ps = vec2(p.x, (p.y - hs.y) * (1.0 - magnify * 1.5) + hs.y);
    float rad = blurPx * mix(0.45, 1.0, smoothstep(0.0, bz, t));
    vec3 col = blurredDisp(ps, disp, dispersion * 0.6, rad);

    // colour: vibrancy, theme tint, milky lift
    float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
    col = mix(vec3(l), col, saturation);
    col = mix(col, tintColor, tintMix);
    col += mix(0.055, 0.020, dark);

    // depth: soft top sheen, darker lower inner edge, thick glass absorbs toward the edge
    float ty = clamp(p.y / glassSize.y, 0.0, 1.0);
    col += (1.0 - ty) * mix(0.040, 0.030, dark);
    col *= 1.0 - 0.12 * exp(-t / 6.0) * clamp(g.y, 0.0, 1.0);
    col *= 1.0 - 0.10 * exp(-t / (bz * 0.45));

    vec3 rimCol = vec3(0.96, 0.98, 1.0);

    // specular rim, light from the top-left
    vec2  L      = normalize(vec2(-0.55, -0.83));
    float facing = dot(g, L);
    float spec   = pow(max(facing, 0.0), 1.6) + 0.55 * pow(max(-facing, 0.0), 2.2);
    float hair   = exp(-t / 1.1);
    float wide   = exp(-t / 5.0);
    float edgeHi = hair * (0.18 + 0.78 * spec) + wide * 0.10 * (0.30 + spec);
    edgeHi *= rim * mix(0.85, 1.0, dark);
    col += edgeHi * rimCol;

    // meniscus: a soft second highlight inside the rim
    float mx  = (t - bz * 0.5) / (bz * 0.2 + 1.0);
    float men = exp(-mx * mx);
    col += men * 0.07 * (0.35 + spec) * rim * rimCol;

    if (ringW > 0.0) {
        float ring = 1.0 - smoothstep(ringW * 0.5, ringW * 0.5 + 1.0, t);
        col = mix(col, rimCol, ring * (0.55 + 0.35 * clamp(facing * 0.5 + 0.5, 0.0, 1.0)) * min(rim, 1.0));
    }

    float gn = hash12(gl_FragCoord.xy) + hash12(gl_FragCoord.xy * 1.7 + 17.0) - 1.0;
    col += gn * grain;

    col = clamp(col, 0.0, 1.0);
    fragColor = vec4(col * cov, cov);    // premultiplied
}
"""


def shader_sources(es):
    """(vertex, fragment) GLSL for a desktop GL 3.3 core or a GLES 3.0 context."""
    head = "#version 300 es\nprecision highp float;\nprecision highp int;\n" if es else "#version 330 core\n"
    return head + VERTEX, head + FRAGMENT


# ----------------------------------------------------------------------------------- wallpaper
# Prints "monitor<TAB>path" for whatever wallpaper daemon is running ("*" = any monitor).
WALLPAPER_SCRIPT = r"""
for q in swww awww; do
  command -v "$q" >/dev/null 2>&1 || continue
  "$q" query 2>/dev/null | sed 's/^[: ]*//' | while IFS= read -r l; do
    m=${l%%:*}
    p=$(printf '%s\n' "$l" | sed -n 's/.*image: //p')
    [ -n "$p" ] && printf '%s\t%s\n' "$m" "$p"
  done
done
if command -v hyprctl >/dev/null 2>&1; then
  hyprctl hyprpaper listactive 2>/dev/null | while IFS= read -r l; do
    case "$l" in *" = "*) printf '%s\t%s\n' "${l%% = *}" "${l#* = }";; esac
  done
fi
f="$HOME/.config/hypr/hyprpaper.conf"
if [ -f "$f" ]; then
  sed -n 's/^[[:space:]]*wallpaper[[:space:]]*=[[:space:]]*//p' "$f" | while IFS= read -r v; do
    m=${v%%,*}; p=${v#*,}; [ -z "$m" ] && m='*'
    case "$p" in contain:*|tile:*|cover:*) p=${p#*:};; esac
    printf '%s\t%s\n' "$m" "$p"
  done
  sed -n 's/^[[:space:]]*path[[:space:]]*=[[:space:]]*//p' "$f" | head -n1 | while IFS= read -r p; do
    printf '*\t%s\n' "$p"
  done
fi
f="$HOME/.config/waypaper/config.ini"
[ -f "$f" ] && sed -n 's/^wallpaper[[:space:]]*=[[:space:]]*//p' "$f" | head -n1 | while IFS= read -r p; do printf '*\t%s\n' "$p"; done
pgrep -a swaybg 2>/dev/null | sed -n 's/.* -i \([^ ]*\).*/*\t\1/p' | head -n1
"""


def parse_wallpapers(text, exists=os.path.isfile):
    """Script output → {monitor: path}; the first usable path also becomes "*"."""
    out = {}
    for line in (text or "").splitlines():
        if "\t" not in line:
            continue
        mon, path = (x.strip() for x in line.split("\t", 1))
        if path.startswith("~/"):
            path = os.path.expanduser(path)
        if not path or not exists(path):
            continue
        out.setdefault(mon or "*", path)
        out.setdefault("*", path)
    return out


def monitor_logical(mon):
    """A `hyprctl -j monitors` entry → (name, x, y, logical width, logical height)."""
    sc = float(mon.get("scale") or 1.0) or 1.0
    w, h = float(mon.get("width", 0)) / sc, float(mon.get("height", 0)) / sc
    if int(mon.get("transform", 0)) % 2 == 1:
        w, h = h, w
    return mon.get("name", ""), float(mon.get("x", 0)), float(mon.get("y", 0)), w, h


def cover_rect(iw, ih, w, h):
    """Crop (x, y, cw, ch) of an iw×ih image that fills w×h like a wallpaper daemon's "cover"."""
    sc = max(w / iw, h / ih)
    cw, ch = w / sc, h / sc
    return (iw - cw) / 2, (ih - ch) / 2, cw, ch

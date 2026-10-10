"""Unit tests that need no display:  make test"""
import os, re, sys, tempfile, unittest

TMP = tempfile.mkdtemp()
os.environ["XDG_CONFIG_HOME"] = TMP
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from interstellar import themes, keys, settings  # noqa: E402
from interstellar.chrome import build_css, mix  # noqa: E402

HEX = re.compile(r"^#[0-9a-f]{6}$")


class Themes(unittest.TestCase):
    def test_builtin_valid(self):
        names = set()
        for t in themes.BUILTIN:
            self.assertNotIn(t["name"], names)
            names.add(t["name"])
            self.assertEqual(len(t["palette"]), 16, t["name"])
            for k in ("fg", "bg", "cursor", "selection", "accent"):
                self.assertRegex(t[k], HEX, f"{t['name']} {k}")
            for c in t["palette"]:
                self.assertRegex(c, HEX, t["name"])
        self.assertGreaterEqual(len(themes.BUILTIN), 25)
        self.assertEqual(themes.BUILTIN[0]["name"], "Event Horizon")

    def test_get_fallback(self):
        self.assertEqual(themes.get("does not exist")["name"], "Event Horizon")

    def test_kitty(self):
        txt = "foreground #c0c0c0\nbackground #101010\ncursor #ff0000\n" + "\n".join(
            f"color{i} #{i:02x}{i:02x}{i:02x}" for i in range(16))
        t = themes.parse_kitty(txt)
        self.assertEqual(t["bg"], "#101010")
        self.assertEqual(t["cursor"], "#ff0000")
        self.assertEqual(t["palette"][15], "#0f0f0f")

    def test_alacritty_toml_and_yaml(self):
        names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
        toml = "[colors.primary]\nbackground = '#000001'\nforeground = '#fffffe'\n[colors.normal]\n" + \
            "\n".join(f"{n} = '#1111{i:02x}'" for i, n in enumerate(names)) + "\n[colors.bright]\n" + \
            "\n".join(f"{n} = '#2222{i:02x}'" for i, n in enumerate(names))
        t = themes.parse_alacritty(toml)
        self.assertEqual(t["bg"], "#000001")
        self.assertEqual(t["palette"][9], "#222201")
        yaml = "colors:\n  primary:\n    background: '0x000002'\n    foreground: '0xfffffd'\n  normal:\n" + \
            "\n".join(f"    {n}: '0x3333{i:02x}'" for i, n in enumerate(names)) + "\n  bright:\n" + \
            "\n".join(f"    {n}: '0x4444{i:02x}'" for i, n in enumerate(names))
        t = themes.parse_alacritty(yaml)
        self.assertEqual(t["fg"], "#fffffd")
        self.assertEqual(t["palette"][0], "#333300")

    def test_base16_and_import_file(self):
        txt = 'scheme: "Test Scheme"\n' + "\n".join(f'base0{h}: "{h * 6}"' for h in "0123456789ABCDEF")
        t = themes.parse_base16(txt)
        self.assertEqual(t["bg"], "#000000")
        p = os.path.join(TMP, "x.yaml")
        with open(p, "w") as f:
            f.write(txt)
        t = themes.import_file(p)
        self.assertEqual(t["name"], "Test Scheme")
        themes.save_custom(t)
        self.assertTrue(any(x["name"] == "Test Scheme" and x.get("custom") for x in themes.all_themes()))

    def test_bad_import(self):
        p = os.path.join(TMP, "bad.conf")
        with open(p, "w") as f:
            f.write("hello world")
        with self.assertRaises(ValueError):
            themes.import_file(p)


class SettingsTest(unittest.TestCase):
    def test_roundtrip_and_listeners(self):
        s = settings.Settings()
        seen = []
        s.listeners.append(seen.append)
        s["theme"] = "Nord"
        s["theme"] = "Nord"          # unchanged → no second event
        self.assertEqual(seen, ["theme"])
        s2 = settings.Settings()
        self.assertEqual(s2["theme"], "Nord")
        self.assertEqual(s2["padding"], settings.DEFAULTS["padding"])
        s.reset()
        self.assertEqual(s["theme"], "Event Horizon")

    def test_profile_lookup(self):
        s = settings.Settings()
        self.assertEqual(s.profile("nope")["name"], "Default")


class KeysTest(unittest.TestCase):
    def test_defaults_unique(self):
        accels = [k for _, _, k in keys.ACTIONS]
        self.assertEqual(len(accels), len(set(accels)), "duplicate default shortcut")

    def test_override(self):
        s = settings.Settings()
        s["keybindings"] = {"new-tab": "<Ctrl>t"}
        self.assertEqual(keys.accel(s, "new-tab"), "<Ctrl>t")
        self.assertEqual(keys.accel(s, "split-right"), "<Ctrl><Shift>d")
        s["keybindings"] = {}


class CssTest(unittest.TestCase):
    def test_builds_for_every_theme_and_style(self):
        for t in themes.BUILTIN:
            for style in ("glass", "solid", "minimal"):
                css = build_css(t, style, 0.9)
                self.assertIn(".istl-tab", css)
                self.assertEqual(css.count("{"), css.count("}"))

    def test_mix(self):
        self.assertEqual(mix("#000000", "#ffffff", 0.5), "#808080")


class PureLogic(unittest.TestCase):
    """Bits that import GTK modules but need no display."""

    @classmethod
    def setUpClass(cls):
        try:
            import gi
            gi.require_version("Gtk", "4.0")
            gi.require_version("Vte", "3.91")
            from interstellar import palette, quickselect, pane
            cls.palette, cls.qs, cls.pane = palette, quickselect, pane
        except (ImportError, ValueError) as e:
            raise unittest.SkipTest(f"GTK/VTE not available: {e}")

    def test_fuzzy(self):
        f = self.palette.fuzzy
        self.assertIsNotNone(f("spr", "Split right"))
        self.assertIsNone(f("xyz", "Split right"))
        self.assertGreater(f("split", "Split right"), f("srt", "Split right"))

    def test_hints(self):
        h = self.qs.make_hints(5)
        self.assertEqual(h, list("asdfg"))
        h = self.qs.make_hints(60)
        self.assertEqual(len(set(h)), 60)

    def test_patterns(self):
        pats = dict(self.qs.PATTERNS)
        text = "see https://example.com/a?b=1, src/main.c:42:7 and 10.0.0.1:8080 commit 3f2a9c1d"
        self.assertEqual(re.search(pats["url"], text).group(), "https://example.com/a?b=1")
        self.assertEqual(re.search(pats["fileline"], text).group(), "src/main.c:42:7")
        self.assertEqual(re.search(pats["ip"], text).group(), "10.0.0.1:8080")
        self.assertEqual(re.search(pats["hash"], text).group(), "3f2a9c1d")

    def test_link_regexes_compile_as_python(self):
        for r in (self.pane.URL_RE, self.pane.FILELINE_RE, self.pane.PATH_RE):
            re.compile(r)

    def test_cell_width(self):
        self.assertEqual(self.pane.cell_width("a"), 1)
        self.assertEqual(self.pane.cell_width("界"), 2)


if __name__ == "__main__":
    unittest.main()

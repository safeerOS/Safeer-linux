"""Ploscica bliznjice (ui/splet.js in core/config):
Ime za »http://x@evil.com/« mora biti pravi gostitelj (evil.com), brez userinfo (ne »x« ali »x@evil.com«).
Enako v Pythonu (core/config.gostitelj_bliznjice)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core.config import ConfigManager, gostitelj_bliznjice  # noqa: E402


class TestBliznjicaGostiteljPython(unittest.TestCase):
    def test_gostitelj_bliznjice(self):
        for url, pricakovano in (
            ("http://x@evil.com/", "evil.com"),
            ("http://user:geslo@evil.com/pot", "evil.com"),
            ("https://admin:geslo@192.168.1.1:8080/", "192.168.1.1"),
            ("https://user@www.safeer.si/", "safeer.si"),
            ("http://x@evil.com:8080/", "evil.com"),
            ("https://sub.domain.si/", "sub.domain.si"),
        ):
            with self.subTest(url=url):
                self.assertEqual(gostitelj_bliznjice(url), pricakovano)

    def test_config_portals_naslov_je_pravi_gostitelj(self):
        """Portal brez podanega imena dobi pravi gostitelj, brez userinfo."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = ConfigManager()
            cfg.config_dir = tmp
            cfg.config_file = os.path.join(tmp, "settings.json")
            # Shranimo portal brez naslova z userinfo
            portals = [{"id": "p1", "title": "", "url": "http://x@evil.com/"}]
            cfg.save_portals(portals)
            nalozeno = cfg.get_portals()
            self.assertEqual(nalozeno[0]["title"], "evil.com")


class TestBliznjicaGostiteljJS(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node ni namescen")
    def test_splet_js_narisi_bliznjice_brez_userinfo(self):
        """ui/splet.js narisiBliznjice: ime za http://x@evil.com/ je evil.com (ne x ali x@evil.com)."""
        pot_js = os.path.join(KOREN, "ui", "splet.js")
        with open(pot_js, "r", encoding="utf-8") as f:
            js_koda = f.read()

        skripta = f"""
const assert = require("assert");

// Mock minimalnega DOM in okolja splet.js
var elementi = {{}};
var document = {{
  body: {{ classList: {{ toggle: function() {{}} }} }},
  documentElement: {{ lang: "", setAttribute: function() {{}} }},
  getElementById: function(id) {{
    if (!elementi[id]) {{
      var el = {{ children: [] }};
      Object.defineProperty(el, "innerHTML", {{ set: function() {{ this.children = []; }}, get: function() {{ return ""; }} }});
      el.setAttribute = function() {{}};
      el.appendChild = function(c) {{ this.children.push(c); }};
      el.addEventListener = function() {{}};
      elementi[id] = el;
    }}
    return elementi[id];
  }},
  createElement: function(tag) {{
    var el = {{ tagName: tag, style: {{}}, children: [] }};
    el.setAttribute = function(k, v) {{ el[k] = v; }};
    el.appendChild = function(child) {{ el.children.push(child); }};
    el.addEventListener = function() {{}};
    el.querySelector = function() {{ return {{ textContent: "" }}; }};
    return el;
  }}
}};
var window = {{ prompt: function() {{}} }};
var location = {{ search: "" }};

// Izrezemo del splet.js od zacetka do konca narisiBliznjice
{js_koda}

// Preverimo zagon s ploscico z userinfo
var p = {{ url: "http://x@evil.com/", title: "" }};
window.safeerSpletInit({{ portals: [p], no_defaults: true }});

var cilj = document.getElementById("bliznjice");
assert.ok(cilj.children && cilj.children.length > 0, "bliznjica mora biti ustvarjena");
var a = cilj.children[0];
var imeSpan = a.children.find(function(c) {{ return c.className === "ime"; }});
var znakSpan = a.children.find(function(c) {{ return c.className === "znak"; }});

assert.strictEqual(imeSpan.textContent, "evil.com", "ime ploscice mora biti pravi gostitelj evil.com, ne " + imeSpan.textContent);
assert.strictEqual(znakSpan.textContent, "E", "crka ikone mora biti E (za evil.com), ne " + znakSpan.textContent);
"""
        res = subprocess.run(["node", "-e", skripta], capture_output=True, text=True)
        if res.returncode != 0:
            self.fail(f"JS preizkus padel:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")


if __name__ == "__main__":
    unittest.main()

"""Dock iz Safeer OS (core/os_dock.py): dodaj, odstrani, razvrsti - brez pravega dconf in Planka."""
import os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_dock

class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.cfg = {}
        # Vrednost samo zamenjamo in po preizkusu vrnemo (AGENTS.md: okolje procesa z nitmi) - prej je ostala za
        # vse nadaljnje preizkuse (test_izolacija_okolja v CI 40193737914).
        prej = os.environ.get("XDG_CONFIG_HOME")     # pod pytest vedno nastavljena (korenski conftest.py)
        self.addCleanup(lambda: os.environ.pop("XDG_CONFIG_HOME", None) if prej is None
                        else os.environ.__setitem__("XDG_CONFIG_HOME", prej))
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.d, "cfg")
        self.app = os.path.join(self.d, "apps"); os.makedirs(self.app)
        for n in ("a", "b", "c"):
            open(os.path.join(self.app, n + ".desktop"), "w").write("[Desktop Entry]\nType=Application\nName=%s\n" % n)
        mock.patch.object(os_dock, "_dconf_beri", lambda k: self.cfg.get(k, "")).start()
        mock.patch.object(os_dock, "_dconf_pisi", lambda k, v: self.cfg.__setitem__(k, v) or True).start()
        mock.patch.object(os_dock, "osvezi", lambda: None).start()
    def tearDown(self): mock.patch.stopall()
    def ids(self): return [e["id"] for e in os_dock.elementi()]
    def test_vse(self):
        p = lambda n: os.path.join(self.app, n + ".desktop")
        self.assertTrue(os_dock.dodaj(p("a"))["ok"]); os_dock.dodaj(p("b")); os_dock.dodaj(p("c"))
        self.assertEqual(self.ids(), ["a.desktop", "b.desktop", "c.desktop"])
        self.assertTrue(os_dock.dodaj(p("a")).get("ze"))
        os_dock.razvrsti(["c.desktop", "a.dockitem"])
        self.assertEqual(self.ids(), ["c.desktop", "a.desktop", "b.desktop"])
        self.assertEqual(self.cfg["dock-items"], "['c.dockitem', 'a.dockitem', 'b.dockitem']")
        os_dock.odstrani("a.desktop")
        self.assertEqual(self.ids(), ["c.desktop", "b.desktop"])
        self.assertFalse(os_dock.dodaj("/nic.desktop")["ok"])
        self.assertFalse(os_dock.dodaj("relativno.desktop")["ok"])
    def test_razcleni(self):
        self.assertEqual(os_dock.razcleni_seznam("@as []"), [])
        self.assertEqual(os_dock.razcleni_seznam("['x.dockitem', 'y.dockitem']"), ["x.dockitem", "y.dockitem"])
        self.assertEqual(os_dock.razcleni_seznam("smeti("), [])
if __name__ == "__main__":
    unittest.main()


class PaketVsebujeModule(unittest.TestCase):
    def test_vsi_moduli_safeer_os_so_v_paketu(self):
        """Vsak modul core, ki ga safeer_os.py uvozi, mora biti v install_os_payload.sh (11. 10. 2026 je os_dock
        manjkal in namescena delovna povrsina se ni zagnala)."""
        import re
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        py = open(os.path.join(koren, "safeer_os.py"), encoding="utf-8").read()
        paket = open(os.path.join(koren, "packaging", "install_os_payload.sh"), encoding="utf-8").read()
        uvozi = set()
        for blok in re.findall(r"^from core import \(?([^)\n]*(?:\n[^)\n]*)*?)\)?\s*(?:#.*)?$", py, re.M):
            uvozi.update(x.strip() for x in re.sub(r"#.*", "", blok).replace("\n", ",").split(",") if x.strip())
        manjka = sorted(m for m in uvozi if not re.search(r"(?<![\w])%s(?![\w])" % re.escape(m), paket))
        self.assertEqual(manjka, [])


class StranBrezPodvojenihSpremenljivk(unittest.TestCase):
    def test_delovna_js_brez_podvojenega_var(self):
        """Dve spremenljivki z istim imenom na vrhu delovna.js se prepiseta (11. 10. 2026: stanje docka »D« je
        prepisalo stanje Datotek - Programi in Datoteke so ostali prazni)."""
        import re
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        js = open(os.path.join(koren, "assets", "os", "delovna.js"), encoding="utf-8").read()
        imena = re.findall(r"^  var ([A-Za-z_$][\w$]*) = ", js, re.M)
        podvojena = sorted({i for i in imena if imena.count(i) > 1})
        self.assertEqual(podvojena, [])


class ControlPaketVsebujeModule(unittest.TestCase):
    def test_vsi_moduli_safeer_control_so_v_paketu(self):
        import re
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        py = open(os.path.join(koren, "safeer_control.py"), encoding="utf-8").read()
        paket = open(os.path.join(koren, "packaging", "install_control_payload.sh"), encoding="utf-8").read()
        uvozi = set(re.findall(r"^from core import (\w+)", py, re.M))
        manjka = sorted(m for m in uvozi if not re.search(r"(?<![\w])%s(?![\w])" % re.escape(m), paket))
        self.assertEqual(manjka, [])


def test_dock_v_flatpaku(monkeypatch):
    """Flatpak: dconf/plank/kill na racunalniku, launcherji v ~/.config racunalnika, pot brez /run/host (14. 10. 2026)."""
    from core import os_dock
    monkeypatch.setenv("FLATPAK_ID", "io.github.memelandfaner.SafeerOS")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/u/.var/app/io.github.memelandfaner.SafeerOS/config")
    monkeypatch.setenv("HOME", "/home/u")
    monkeypatch.setenv("DISPLAY", ":0")
    u = os_dock._gostitelj(["dconf", "read", "x"])
    assert u[:2] == ["flatpak-spawn", "--host"] and "--env=DISPLAY=:0" in u and u[-3:] == ["dconf", "read", "x"]
    assert os_dock.mapa_launcherjev() == "/home/u/.config/plank/dock1/launchers"
    assert os_dock.pot_za_gostitelja("/run/host/usr/share/applications/a.desktop") == "/usr/share/applications/a.desktop"
    assert os_dock.pot_za_gostitelja("/var/lib/flatpak/exports/share/applications/b.desktop").startswith("/var/lib")
    monkeypatch.delenv("FLATPAK_ID")
    assert os_dock._gostitelj(["dconf"]) == ["dconf"]

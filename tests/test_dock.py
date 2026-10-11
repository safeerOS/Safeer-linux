"""Dock iz Safeer OS (core/os_dock.py): dodaj, odstrani, razvrsti - brez pravega dconf in Planka."""
import os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_dock

class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.cfg = {}
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

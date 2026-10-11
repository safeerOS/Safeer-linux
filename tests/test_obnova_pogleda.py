"""Padec spletnega procesa (stresni preizkus #77, 12. 10. 2026: OOM je ubil WebKitWebProcess namizja, namizje je
ostalo prazno): pogled se nalozi znova, najvec NAJVEC_OBNOV-krat v oknu, in ne ob koncu procesa iz programa."""
import os
import tempfile
import unittest
from unittest import mock

from core import os_stabilnost as s


class Razlog:
    CRASHED, EXCEEDED_MEMORY_LIMIT, TERMINATED_BY_API = 0, 1, 2


class W:
    WebProcessTerminationReason = Razlog


class GLib:
    def __init__(self):
        self.cakajoce = []

    def timeout_add(self, ms, fn):
        self.cakajoce.append(fn)
        return len(self.cakajoce)

    def pozeni(self):
        c, self.cakajoce = self.cakajoce, []
        for fn in c:
            fn()


class Pogled:
    def __init__(self):
        self.rokovalniki, self.nalozeno = {}, 0

    def connect(self, ime, fn):
        self.rokovalniki[ime] = fn

    def reload(self):
        self.nalozeno += 1

    def padec(self, razlog):
        self.rokovalniki["web-process-terminated"](self, razlog)


class TestObnova(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = mock.patch.dict(os.environ, {"XDG_CACHE_HOME": self.tmp.name})
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.tmp.cleanup()

    def _dnevnik(self):
        with open(os.path.join(self.tmp.name, "safeer-os", "dnevnik.log"), encoding="utf-8") as f:
            return f.read()

    def test_oom_nalozi_znova_in_zabelezi(self):
        g, p = GLib(), Pogled()
        self.assertIsNotNone(s.obnovi_ob_padcu(W, g, p, "safeer-os", "delovna.html"))
        p.padec(Razlog.EXCEEDED_MEMORY_LIMIT)
        self.assertEqual(p.nalozeno, 0)          # z zamikom, ne v rokovalniku signala
        g.pozeni()
        self.assertEqual(p.nalozeno, 1)
        self.assertIn("delovna.html", self._dnevnik())
        self.assertIn("pomnilnik", self._dnevnik())

    def test_sesutje(self):
        g, p = GLib(), Pogled()
        s.obnovi_ob_padcu(W, g, p, "safeer-os", "splet")
        p.padec(Razlog.CRASHED)
        g.pozeni()
        self.assertEqual(p.nalozeno, 1)
        self.assertIn("sesutje", self._dnevnik())

    def test_konec_iz_programa_ni_napaka(self):
        g, p = GLib(), Pogled()
        s.obnovi_ob_padcu(W, g, p, "safeer-os", "splet")
        p.padec(Razlog.TERMINATED_BY_API)
        g.pozeni()
        self.assertEqual(p.nalozeno, 0)

    def test_zanka_sesutij_se_ustavi(self):
        g, p = GLib(), Pogled()
        s.obnovi_ob_padcu(W, g, p, "safeer-os", "delovna.html")
        for _ in range(s.NAJVEC_OBNOV + 2):
            p.padec(Razlog.CRASHED)
            g.pozeni()
        self.assertEqual(p.nalozeno, s.NAJVEC_OBNOV)
        self.assertIn("prevec obnov", self._dnevnik())

    def test_po_oknu_spet_dovoljeno(self):
        cas = [0.0]
        o = s.ObnovaPogleda("safeer-os", "x", ura=lambda: cas[0])
        for _ in range(s.NAJVEC_OBNOV):
            self.assertTrue(o.odlocitev("sesutje"))
        self.assertFalse(o.odlocitev("sesutje"))
        cas[0] += s.OKNO_SESUTIJ_S + 1
        self.assertTrue(o.odlocitev("sesutje"))

    def test_vsi_pogledi_imajo_obnovo(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for dat, niz in (("safeer_os.py", '"safeer-os", stran.split'), ("core/os_splet.py", '"safeer-os", "splet"'),
                         ("safeer_control.py", '"safeer-control", "gledalec"')):
            with open(os.path.join(koren, dat), encoding="utf-8") as f:
                self.assertIn("obnovi_ob_padcu(", f.read().split(niz)[0][-200:], dat)


if __name__ == "__main__":
    unittest.main()

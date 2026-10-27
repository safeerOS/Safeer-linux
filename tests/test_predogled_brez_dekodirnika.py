"""Predogled (preslednica v Datotekah) za HEIC/AVIF/JPEG XL/RAW: Qt v Safeerju (PySide6 Essentials) zanje nima
dekodirnika. Brez tega popravka HEIC dobi nacin »slika« in QML Image konca z Image.Error (splosno »Predogleda ni mogoce
pokazati«), DNG pa samo ikono brez razloga. Zdaj: nacin »podatki«, brezDekodirnika in jasen razlog."""
import os
import tempfile
import unittest

from core import os_datoteke
from tests.test_qml_dodatki import Osnova


class PredogledBrezDekodirnikaJedro(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.mapa = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _pot(self, ime, vsebina=b"\0\0\0\x18ftypheic"):
        p = os.path.join(self.mapa, ime)
        with open(p, "wb") as f:
            f.write(vsebina)
        return p

    def test_heic_raw_avif_jxl_brez_dekodirnika(self):
        for ime in ("foto.heic", "FOTO.HEIF", "s.hif", "s.avif", "s.jxl", "surovo.dng", "s.CR3", "s.nef", "s.arw",
                    "s.raf", "s.orf", "s.rw2"):
            r = os_datoteke.predogled(self._pot(ime))
            self.assertTrue(r["ok"], ime)
            self.assertEqual(r["nacin"], "podatki", ime)          # nikoli »slika«: QML bi koncal z Image.Error
            self.assertTrue(r.get("brezDekodirnika"), ime)

    def test_obicajne_slike_ostanejo_slike(self):
        for ime in ("s.png", "s.jpg", "s.webp", "s.gif"):
            r = os_datoteke.predogled(self._pot(ime, b"\x89PNG"))
            self.assertEqual(r["nacin"], "slika", ime)
            self.assertNotIn("brezDekodirnika", r)


class PredogledBrezDekodirnikaQml(Osnova):
    def test_heic_pove_razlog(self):
        from PySide6.QtCore import Qt
        with open(os.path.join(self.dok, "pocitnice.heic"), "wb") as f:
            f.write(b"\0\0\0\x18ftypheic" + b"\0" * 64)
        self._namizje()
        self._js('datoteke.odpriLokalno("%s")' % self.dok)
        self.assertTrue(self._pocakaj(lambda: any(e["ime"] == "pocitnice.heic" for e in self._js("datoteke.prikazani"))))
        imena = [e["ime"] for e in self._js("datoteke.prikazani")]
        self._obj("seznamDatotek").forceActiveFocus()
        self._klik_vrstice(imena.index("pocitnice.heic"))
        self._tipka(Qt.Key.Key_Space)
        p = self._obj("predogled")
        self.assertTrue(self._pocakaj(lambda: p.property("visible") and not p.property("nalagam")))
        self.assertEqual(p.property("nacin"), "podatki")
        razlog = self._obj("predogledRazlog")
        pricakovano = self._js('koren.t("predogledBrezDekodirnika")')
        self.assertIn("HEIC", pricakovano)
        self.assertTrue(self._pocakaj(lambda: razlog.property("text") == pricakovano))
        self.assertTrue(self._obj("predogledOdpri").property("visible"))     # »Odpri« ostane (zunanji ogled)


if __name__ == "__main__":
    unittest.main()

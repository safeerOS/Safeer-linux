"""Flatpak + .deb (hibrid): posodobitev namesti oba paketa, .deb na racunalniku prek pkexec, Flatpak za uporabnika."""
import os
import unittest
from unittest import mock

from core import os_posodobitve as P

D = {"url": "https://github.com/safeerOS/Safeer-linux/releases/download/v1/x.deb", "sha256": "a" * 64, "velikost": 10}
F = {"url": "https://github.com/safeerOS/Safeer-linux/releases/download/v1/x.flatpak", "sha256": "b" * 64, "velikost": 10}


class Hibrid(unittest.TestCase):
    def test_nacin(self):
        with mock.patch.dict(os.environ, {"FLATPAK_ID": "io.github.memelandfaner.SafeerOS"}), \
             mock.patch.object(P, "gostitelj_ima_deb", return_value=True):
            self.assertEqual(P.nacin_namestitve(), "flatpak+deb")
        with mock.patch.dict(os.environ, {"FLATPAK_ID": "io.github.memelandfaner.SafeerOS"}), \
             mock.patch.object(P, "gostitelj_ima_deb", return_value=False):
            self.assertEqual(P.nacin_namestitve(), "flatpak")

    def test_preveri_doda_deb(self):
        m = {"linux": {"safeer-os": {"razlicica": "9.0.0", "deb": D, "flatpak": F}}}
        with mock.patch.object(P, "veljavna_datoteka", side_effect=lambda d: isinstance(d, dict) and bool(d.get("url"))):
            izid = P.preveri("linux", {"safeer-os": "0.1.0"}, manifest=m, nacin="flatpak+deb")
        n = izid["nove"][0]
        self.assertEqual(n["datoteka"], F)
        self.assertEqual(n["deb"], D)

    def test_brez_deb_samo_stran(self):
        m = {"linux": {"safeer-os": {"razlicica": "9.0.0", "flatpak": F}}}
        with mock.patch.object(P, "veljavna_datoteka", side_effect=lambda d: isinstance(d, dict) and bool(d.get("url"))):
            izid = P.preveri("linux", {"safeer-os": "0.1.0"}, manifest=m, nacin="flatpak+deb")
        self.assertIsNone(izid["nove"][0]["datoteka"])

    def test_namesti_najprej_deb_na_racunalniku(self):
        klici = []
        def run(ukaz, **k):
            klici.append(ukaz)
            return mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(P.subprocess, "run", side_effect=run):
            P.namesti_linux("flatpak+deb", ["/home/u/.cache/a.flatpak", "/home/u/.cache/a.deb"], ["f" * 64, "d" * 64])
        # .deb kot root iz preverjene kopije (P.NAMESTI_DEB_KOT_ROOT), z vsoto .deb, ne Flatpaka; pkexec in sh z
        # absolutno potjo na gostitelju (core/root_ukaz.py: pkexec isce program po PATH klicatelja).
        self.assertEqual(klici[0][:7], ["flatpak-spawn", "--host", "/usr/bin/pkexec", "/bin/sh", "-c", P.NAMESTI_DEB_KOT_ROOT,
                                        "safeer-posodobitev"])
        self.assertEqual(klici[0][7:], ["d" * 64, "/home/u/.cache/a.deb"])
        self.assertEqual(klici[1][:3], ["flatpak", "install", "--user"])
        self.assertIn("/home/u/.cache/a.flatpak", klici[1])

    def test_neuspel_deb_ustavi(self):
        with mock.patch.object(P.subprocess, "run", return_value=mock.Mock(returncode=126, stdout="", stderr="preklicano")) as run:
            r = P.namesti_linux("flatpak+deb", ["/x.flatpak", "/x.deb"], ["f" * 64, "d" * 64])
        self.assertEqual(r.returncode, 126)
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()


class PonudbaFlatpak(unittest.TestCase):
    def _m(self, razlicica="0.4.85"):
        return {"linux": {"safeer-os": {"razlicica": razlicica, "deb": D, "flatpak": F}}}

    def _preveri(self, m, nasa, nacin):
        with mock.patch.object(P, "veljavna_datoteka", side_effect=lambda d: isinstance(d, dict) and bool(d.get("url"))):
            return P.preveri("linux", {"safeer-os": nasa}, manifest=m, nacin=nacin)

    def test_deb_ni_ponudbe(self):
        """Od 1.0.127 ima .deb isti WebKit kot Flatpak (in BOLT): ponudba »hitrejsi Splet« bi bila neresnicna."""
        self.assertIsNone(self._preveri(self._m(), "0.4.85", "deb")["flatpak_preklop"])

    def test_starejsi_flatpak_ni_ponudbe(self):
        self.assertIsNone(self._preveri(self._m("0.4.84"), "0.4.85", "deb")["flatpak_preklop"])

    def test_flatpak_ni_ponudbe(self):
        self.assertIsNone(self._preveri(self._m(), "0.4.85", "flatpak")["flatpak_preklop"])

    def test_namesti_flatpak_za_uporabnika(self):
        with mock.patch.object(P.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            P.namesti_flatpak("/home/u/.cache/x.flatpak")
        self.assertEqual(run.call_args[0][0][:3], ["flatpak", "install", "--user"])


class VmesnikFlatpak(unittest.TestCase):
    def test_gumb_in_most(self):
        from pathlib import Path
        k = Path(__file__).resolve().parents[1]
        self.assertIn('id="gumbFlatpak"', (k / "assets" / "os" / "index.html").read_text(encoding="utf-8"))
        self.assertIn('klic("flatpakPreklop")', (k / "assets" / "os" / "os.js").read_text(encoding="utf-8"))
        self.assertIn('"flatpakPreklop": self._flatpak_preklop', (k / "safeer_os.py").read_text(encoding="utf-8"))

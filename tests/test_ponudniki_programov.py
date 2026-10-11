"""Ponudniki programov (core/os_ponudniki_programov.py): nevtralen seznam, nespremenljivi ukazi, Snap se ne vklaplja."""
import re
import unittest
from pathlib import Path

from core import os_ponudniki_programov as p

KOREN = Path(__file__).resolve().parent.parent


class Zapis:
    def __init__(self, odgovori=None):
        self.ukazi = []
        self.odgovori = odgovori or {}

    def __call__(self, ukaz, cas):
        self.ukazi.append(list(ukaz))
        for zacetek, odg in self.odgovori.items():
            if " ".join(ukaz).startswith(zacetek):
                return odg
        return (1, "")


def vse_je(ime):
    return "/usr/bin/" + ime


def nic(ime):
    return None


class Pravila(unittest.TestCase):
    def test_seznam_brez_privzetega_in_enolicen(self):
        ids = [x["id"] for x in p.PONUDNIKI]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(x["vrsta"] in ("flatpak", "apt", "snap") for x in p.PONUDNIKI))
        self.assertFalse(any("privzet" in x for x in p.PONUDNIKI))

    def test_stanje_namescen_in_namestljiv(self):
        tek = Zapis({"flatpak info it.mijorus.gearlever": (0, ""),
                     "dpkg-query -W -f=${Status} mintinstall": (0, "install ok installed")})
        s = {x["id"]: x for x in p.stanje(tek, vse_je, nosnap=True)}
        self.assertTrue(s["gearlever"]["namescen"])
        self.assertFalse(s["gearlever"]["namestljiv"])
        self.assertTrue(s["mintinstall"]["namescen"])
        self.assertTrue(s["bazaar"]["namestljiv"])
        self.assertFalse(s["snap-store"]["namestljiv"])
        self.assertTrue(s["snap-store"]["snap_blokiran"])

    def test_brez_flatpak_in_pkexec_ni_namestljivo(self):
        s = {x["id"]: x for x in p.stanje(Zapis(), nic, nosnap=False)}
        self.assertFalse(any(x["namestljiv"] or x["namescen"] for x in s.values()))

    def test_flatpak_za_uporabnika_iz_flathuba(self):
        tek = Zapis({"flatpak remote-add": (0, ""), "flatpak install": (0, "")})
        self.assertTrue(p.namesti("bazaar", tek, vse_je)["ok"])
        self.assertEqual(tek.ukazi[0], ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
                                        "https://dl.flathub.org/repo/flathub.flatpakrepo"])
        self.assertEqual(tek.ukazi[1], ["flatpak", "install", "--user", "--noninteractive", "-y", "flathub", "io.github.kolunmi.Bazaar"])

    def test_apt_prek_pkexec_in_preklic(self):
        tek = Zapis({"pkexec apt-get install": (0, "")})
        self.assertTrue(p.namesti("gnome-software", tek, vse_je)["ok"])
        self.assertEqual(tek.ukazi[0], ["pkexec", "apt-get", "install", "-y", "gnome-software", "gnome-software-plugin-flatpak"])
        self.assertEqual(p.namesti("gnome-software", Zapis({"pkexec": (126, "")}), vse_je)["napaka"], "preklicano")

    def test_snap_in_neznan_se_ne_namestita(self):
        tek = Zapis()
        self.assertEqual(p.namesti("snap-store", tek, vse_je)["napaka"], "snap")
        self.assertEqual(p.namesti("rm -rf /", tek, vse_je)["napaka"], "ni_ponudnika")
        self.assertEqual(tek.ukazi, [])

    def test_odpri(self):
        zagnano = []
        self.assertTrue(p.odpri("gearlever", lambda u, **k: zagnano.append(u)))
        self.assertTrue(p.odpri("mintinstall", lambda u, **k: zagnano.append(u)))
        self.assertFalse(p.odpri("snap-store", lambda u, **k: zagnano.append(u)))
        self.assertEqual(zagnano, [["flatpak", "run", "it.mijorus.gearlever"], ["mintinstall"]])

    def test_podrobnosti_flatpak_z_okoljem(self):
        info = (0, "Bazaar\n\n        ID: io.github.kolunmi.Bazaar\n   Version: 0.9.7\n   License: GPL-3.0-or-later\n"
                   "  Download: 11.9 MB\n Installed: 24.2 MB\n   Runtime: org.gnome.Platform/x86_64/51\n")
        okolje = (0, "   Version: 51.1\n  Download: 432.2 MB\n")
        tek = Zapis({"flatpak remote-info --system flathub io.github.kolunmi.Bazaar": info,
                     "flatpak remote-info --system flathub org.gnome.Platform//51": okolje,
                     "gsettings get": (0, "true\n")})
        d = p.podrobnosti("bazaar", tek, vse_je, obstaja=lambda pot: True)
        self.assertEqual([x["ime"] for x in d["paketi"]], ["io.github.kolunmi.Bazaar", "org.gnome.Platform/x86_64/51"])
        self.assertTrue(d["paketi"][1]["okolje"])
        self.assertEqual(d["prenos_mb"], 444.1)
        self.assertTrue(d["samodejno"])
        self.assertFalse(any(u[:2] == ["flatpak", "install"] for u in tek.ukazi), "podrobnosti ne smejo namescati")

    def test_podrobnosti_apt_simulacija(self):
        sim = (0, "Inst gnome-software-common (46.0-1ubuntu2 Ubuntu:24.04/noble [all])\nInst gnome-software (46.0-1ubuntu2 Ubuntu:24.04/noble [amd64])\n")
        uri = (0, "'http://x/a.deb' a.deb 1048576 MD5Sum:1\n'http://x/b.deb' b.deb 524288 MD5Sum:2\n")
        tek = Zapis({"env LANG=C apt-get -s install": sim, "env LANG=C apt-get install --print-uris": uri})
        d = p.podrobnosti("gnome-software", tek, vse_je, obstaja=lambda pot: False)
        self.assertEqual([x["ime"] for x in d["paketi"]], ["gnome-software-common", "gnome-software"])
        self.assertEqual(d["prenos_mb"], 1.5)
        self.assertTrue(d["geslo"])
        self.assertFalse(d["samodejno"])
        self.assertFalse(any("pkexec" in u for u in tek.ukazi))

    def test_samodejne_posodobitve_samo_ce_jih_je_vklopil_uporabnik(self):
        self.assertFalse(p.samodejne_posodobitve("flatpak", Zapis({"gsettings": (0, "true")}), obstaja=lambda pot: False))
        self.assertFalse(p.samodejne_posodobitve("flatpak", Zapis({"gsettings": (0, "false")}), obstaja=lambda pot: True))
        self.assertTrue(p.samodejne_posodobitve("apt", Zapis(), obstaja=lambda pot: True))

    def test_namestitev_sele_po_podrobnostih(self):
        js = (KOREN / "assets/os/delovna.js").read_text(encoding="utf-8")
        i, j = js.index('klic("ponudnikPodrobnosti", [p.id])'), js.index('klic("ponudnikNamesti", [p.id])')
        self.assertLess(i, j)
        self.assertIn("function namestiPotrjeno()", js)
        self.assertEqual(js.count("namestiPotrjeno()"), 2, "namestitev samo iz gumba potrditve")

    def test_stran_in_paket(self):
        js = (KOREN / "assets/os/delovna.js").read_text(encoding="utf-8")
        for x in p.PONUDNIKI:
            self.assertEqual(js.count("ppOpis_" + x["id"].replace("-", "_") + ":"), 2, x["id"])
        for k in ("ppGumb", "ppNaslov", "ppUvod", "ppNamesti", "ppOdpri", "ppVec", "ppPreklicano"):
            self.assertEqual(js.count(k + ":"), 2, k)
        self.assertIn('klic("ponudnikNamesti", [p.id])', js)
        self.assertIn('id="prgNamesti"', (KOREN / "assets/os/delovna.html").read_text(encoding="utf-8"))
        py = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        for k in ('"ponudnikiProgramov"', '"ponudnikNamesti"', '"ponudnikOdpri"'):
            self.assertIn(k, py)
        self.assertIn("os_ponudniki_programov", (KOREN / "packaging/install_os_payload.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

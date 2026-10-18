"""Vsako okno Safeer OS ima v pultu in docku svoj vnos, svoj razred okna in svojo ikono.

Lastnik, 16. 10. 2026: »na stranskem docku imata Sporocila in Splet enako ikono - to se ne sme zgoditi, uporabnik se
zmede« (testni PC: Mint 22.3, Safeer OS 0.4.84 Flatpak, Plank). Vzrok: vsa okna so imela razred »safeer-os« in ikono
Safeer OS, Safeer Control pa isti PNG »S« kot Safeer OS. Preizkus preveri, da nobeni dve okni (vlogi) oziroma nobena
dva vnosa nimata istega razreda ali iste ikone - za .deb in Flatpak.
"""
import configparser
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import safeer_os  # noqa: E402

APP_ID = "io.github.memelandfaner.SafeerOS"


def _beri(*deli) -> str:
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def _vnos(pot) -> dict:
    razclen = configparser.RawConfigParser(strict=True)
    razclen.optionxform = str
    razclen.read(pot, encoding="utf-8")
    return dict(razclen["Desktop Entry"])


def _namesti(mapa, *id_) -> Path:
    prefix = Path(mapa) / "usr"
    for skripta in ("install_os_payload.sh", "install_control_payload.sh"):
        subprocess.run(["bash", os.path.join(KOREN, "packaging", skripta), str(prefix), *id_],
                       check=True, capture_output=True)
    return prefix


def _vloge_v_kodi() -> list:
    """Vse vloge, s katerimi safeer_os.py klice _razred_okna (dobesedno ali razdelke iz RAZDELKI_V_SVOJEM_OKNU)."""
    vir = _beri("safeer_os.py")
    vloge = set(re.findall(r'_razred_okna\(\w+, "([^"]*)"\)', vir))
    if re.search(r"_razred_okna\(okno\)", vir):
        vloge.add("")
    if "_razred_okna(okno, ime)" in vir:
        vloge.update(safeer_os.RAZDELKI_V_SVOJEM_OKNU)
    return sorted(vloge)


class VlogeOken(unittest.TestCase):
    def test_vse_vloge_iz_kode_so_znane(self):
        vloge = _vloge_v_kodi()
        for nujna in ("", "Splet", "Sporocila", "Dialog", "sporocila", "zapiski", "nastavitve"):
            self.assertIn(nujna, vloge)
        znane = set(safeer_os.OKNA_V_PULTU) | set(safeer_os._OKNA_PREDVAJALNIKA) | {""}
        for vloga in vloge:
            self.assertIn(vloga.lower() if vloga not in safeer_os._OKNA_PREDVAJALNIKA else vloga, znane, vloga)

    def test_razlicni_programi_razlicen_razred_in_ikona(self):
        """Program = (razred, ikona). Razlicni programi nimajo skupnega razreda ne ikone; Sporocila (plosca in okno
        razdelka) sta en program, Medijski center in njegov dialog sodita k Safeer Playerju."""
        programi = {}
        for vloga in _vloge_v_kodi():
            ime, razred, pripona = safeer_os.razred_in_ikona(vloga)
            programi.setdefault(razred, set()).add((ime, pripona))
        for razred, ikone in programi.items():
            self.assertEqual(len(ikone), 1, (razred, ikone))
        pripone = [next(iter(v))[1] for v in programi.values()]
        self.assertEqual(len(pripone), len(set(pripone)), programi)
        # Control (v istem procesu) in delovna povrsina imata svoja razreda.
        razredi = set(programi) | {"safeer-control", "safeer-cinnamon"}
        self.assertEqual(len(razredi), len(programi) + 2)
        self.assertEqual(safeer_os.razred_in_ikona("Splet")[1], "safeer-os.splet")
        self.assertEqual(safeer_os.razred_in_ikona("Sporocila"), safeer_os.razred_in_ikona("sporocila"))
        self.assertNotEqual(safeer_os.razred_in_ikona("Splet"), safeer_os.razred_in_ikona("Sporocila"))
        self.assertEqual(safeer_os.razred_in_ikona("Medijski")[:2], safeer_os.WMCLASS_PREDVAJALNIKA)
        self.assertEqual(safeer_os.razred_in_ikona(""), ("safeer-os", "safeer-os", ""))

    def test_razred_z_malimi_crkami(self):
        """Plank (bamf) razred okna spremeni v male crke in ga isce med imeni vnosov: ime vnosa mora biti enako."""
        for vloga in safeer_os.OKNA_V_PULTU:
            ime, razred, pripona = safeer_os.razred_in_ikona(vloga)
            self.assertEqual(razred, razred.lower())
            self.assertEqual(ime, razred)
            self.assertEqual(razred, "safeer-os" + pripona)

    def test_razred_okna_nastavi_ikono_vloge(self):
        okno = mock.MagicMock()
        with mock.patch.object(safeer_os.x11, "nastavi_razred") as razred, \
                mock.patch.object(safeer_os, "_ime_ikone", side_effect=lambda imena, slika="": imena[0]):
            safeer_os._razred_okna(okno, "Sporocila")
            razred.assert_called_once_with(okno, "safeer-os.sporocila", "safeer-os.sporocila")
            okno.set_icon_name.assert_called_with("safeer-os.sporocila")
            safeer_os._razred_okna(okno, "Splet")
            okno.set_icon_name.assert_called_with("safeer-os.splet")
            safeer_os._razred_okna(okno, "Medijski")
            okno.set_icon_name.assert_called_with("safeer-os.Player")

    def test_ikona_brez_paketa_iz_assets(self):
        """Zagon iz izvorne mape: ikona okna je slika iz assets/os (ime slike), ne skupna ikona Safeer OS."""
        tema = mock.MagicMock()
        tema.get_search_path.return_value = []
        tema.has_icon.side_effect = lambda ime: ime == "splet"
        with mock.patch.object(safeer_os.Gtk.IconTheme, "get_for_display", return_value=tema), \
                mock.patch.object(safeer_os.Gdk.Display, "get_default", return_value=None):
            self.assertEqual(safeer_os._ikona_safeer_os(".splet"), "splet")
        tema.add_search_path.assert_called_once_with(os.path.join(KOREN, "assets", "os"))

    def test_delovna_povrsina_ne_kaze_ikone_brskalnika(self):
        vir = _beri("safeer_os.py")
        telo = vir[vir.index('okno = Gtk.ApplicationWindow(application=self, title="Safeer Cinnamon")'):]
        telo = telo[:telo.index("x11.nastavi_vrsto(okno, \"DESKTOP\")")]
        self.assertNotIn('"safeer-browser"', telo)


class Slike(unittest.TestCase):
    def test_slike_ikon_so_razlicne(self):
        slike = {ime: os.path.join(KOREN, "assets", "os", ime + ".svg") for ime in safeer_os.OKNA_V_PULTU}
        slike["safeer-os"] = os.path.join(KOREN, "assets", "os", "znak.svg")
        slike["player"] = os.path.join(KOREN, "assets", "os", "predvajalnik.svg")
        slike["control"] = os.path.join(KOREN, "assets", "link", "control.svg")
        vsebine = {}
        for ime, pot in slike.items():
            with open(pot, "rb") as f:
                podatki = f.read()
            self.assertIn(b"<svg", podatki, pot)
            vsebine.setdefault(hashlib.sha256(podatki).hexdigest(), []).append(ime)
        self.assertEqual(len(vsebine), len(slike), vsebine)
        # Splet je globus, Sporocila kuverta (opis v SVG).
        self.assertIn("globus", _beri("assets", "os", "splet.svg"))
        self.assertIn("kuverta", _beri("assets", "os", "sporocila.svg"))


class Paketi(unittest.TestCase):
    """Namesceni vnosi (.deb in Flatpak): vsak razred okna ima natanko en vnos, vsak vnos svojo ikono."""

    def _preveri(self, prefix: Path, id_: str):
        aplikacije = prefix / "share" / "applications"
        ikone = prefix / "share" / "icons" / "hicolor"
        razredi, imena_ikon, vsebine = {}, {}, {}
        for pot in sorted(aplikacije.glob("*.desktop")):
            v = _vnos(pot)
            razred = v.get("StartupWMClass")
            if not razred:
                continue          # Magnet, Stremio: odpirata Safeer Player, nista okni
            self.assertNotIn(razred, razredi, (pot.name, razredi.get(razred)))
            razredi[razred] = pot.name
            ikona = v["Icon"]
            self.assertNotIn(ikona, imena_ikon, (pot.name, imena_ikon.get(ikona)))
            imena_ikon[ikona] = pot.name
            datoteke = sorted(ikone.glob("*/apps/%s.*" % ikona))
            self.assertTrue(datoteke, ikona)
            if pot.name.startswith(id_ + ".") or pot.name == id_ + ".desktop":
                # Vsebina ikone (vse velikosti skupaj) se ne ponovi pri nobenem drugem oknu.
                odtis = hashlib.sha256(b"".join(d.read_bytes() for d in datoteke if d.suffix == ".svg")).hexdigest()
                self.assertNotIn(odtis, vsebine, (pot.name, vsebine.get(odtis)))
                vsebine[odtis] = pot.name
        # Vsako okno iz kode ima vnos z enakim StartupWMClass.
        for vloga in _vloge_v_kodi():
            self.assertIn(safeer_os.razred_in_ikona(vloga)[0], razredi, vloga)
        self.assertIn("safeer-control", razredi)
        return razredi

    def test_deb(self):
        with tempfile.TemporaryDirectory() as mapa:
            prefix = _namesti(mapa)
            razredi = self._preveri(prefix, "safeer-os")
            for vloga in safeer_os.OKNA_V_PULTU:
                razred = safeer_os.razred_in_ikona(vloga)[1]
                self.assertEqual(razredi[razred], razred + ".desktop")   # bamf: ime vnosa = razred
                v = _vnos(prefix / "share/applications" / (razred + ".desktop"))
                # Safeer Scit je svoj program (lastnik, 18. 10. 2026): v meniju viden, z varnostno kategorijo.
                if vloga == "scit":
                    self.assertNotEqual(v.get("NoDisplay"), "true")
                    self.assertIn("Security", v["Categories"])
                else:
                    self.assertEqual(v["NoDisplay"], "true")
                self.assertEqual(v["Exec"].split(), ["safeer-os", "--razdelek", vloga])
                for jezik in ("sl", "de", "es", "fr", "it"):
                    self.assertIn("Name[%s]" % jezik, v)
            # Control ima svojo ikono: SVG in PNG na starih poteh paketa safeer-control (Replaces mora prevzeti vse
            # njegove datoteke), PNG narisan iz iste control.svg - nikoli zeleni »S« Safeer OS (bi prehitel SVG).
            control = sorted((prefix / "share/icons/hicolor").glob("*/apps/safeer-control.*"))
            self.assertIn("safeer-control.svg", [p.name for p in control])
            for png in (p for p in control if p.suffix == ".png"):
                velikost = png.parent.parent.name
                s_ikona = Path(KOREN, "packaging", "icons", "os", "hicolor", velikost, "apps", "safeer-os.png")
                self.assertNotEqual(png.read_bytes(), s_ikona.read_bytes() if s_ikona.exists() else b"", png)

    def test_flatpak(self):
        with tempfile.TemporaryDirectory() as mapa:
            prefix = Path(mapa) / "usr"
            subprocess.run(["bash", os.path.join(KOREN, "packaging", "install_control_payload.sh"), str(prefix)],
                           check=True, capture_output=True)
            subprocess.run(["bash", os.path.join(KOREN, "packaging", "install_os_payload.sh"), str(prefix), APP_ID],
                           check=True, capture_output=True)
            # Kot io.github.memelandfaner.SafeerOS.yml: vnos Controla brez ID-ja Flatpak ne izvozi.
            (prefix / "share/applications/safeer-control.desktop").unlink()
            self._preveri(prefix, APP_ID)
            for ime in os.listdir(prefix / "share/applications"):
                self.assertTrue(ime.startswith(APP_ID + "."), ime)
            for pot in (prefix / "share/icons").rglob("*.svg"):
                if not pot.name.startswith("safeer-control"):
                    self.assertTrue(pot.name.startswith(APP_ID), pot.name)
            v = _vnos(prefix / "share/applications" / (APP_ID + ".Control.desktop"))
            self.assertEqual((v["StartupWMClass"], v["NoDisplay"], v["Icon"]),
                             ("safeer-control", "true", APP_ID + ".Control"))

    def test_deb_pot_do_ukaza(self):
        deb = _beri("build_os_deb.sh")
        self.assertIn("safeer-os.{splet,sporocila,zapiski,nastavitve,scit}.desktop", deb)


class Razdelek(unittest.TestCase):
    def test_samo_okna_iz_seznama(self):
        lazni = mock.MagicMock()
        safeer_os.SafeerOS._razdelek_od_drugod(lazni, "sporocila")
        lazni._odpri_razdelek.assert_called_once_with("sporocila")
        lazni.reset_mock()
        for slabo in ("", "naprave", "pogovor:x", "../x", "splet; rm"):
            safeer_os.SafeerOS._razdelek_od_drugod(lazni, slabo)
        lazni._odpri_razdelek.assert_not_called()


if __name__ == "__main__":
    unittest.main()

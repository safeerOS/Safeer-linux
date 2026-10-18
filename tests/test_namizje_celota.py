"""Celovitost namizja (lastnik: »vse je en proces, vsi nasi dodatki delujejo kot del namiznega okolja«) - pregled
15. 10. 2026:

* jeziki: namizje QML in delovna povrsina WebKit imata EN slovar (assets/os/besedila-namizja.js) v sl, en, de, es, fr,
  it - prej samo sl/en (QML je vse druge jezike prisilil v anglescino);
* videz: barve iz enega vira (assets/os/tokens.css) za strani WebKit in namizje QML (prej zelena #54d6a5 v QML, modra
  drugod); kontrast in velikost besedila sistema dosezeta tudi QML;
* tipkovnica: Gumb, Escape zapre vrhnji sloj, puscice v Datotekah in Programih, nacin za kavc na delovni povrsini;
* okna: vsako okno Safeer OS ima svoj razred (StartupWMClass) in svojo ikono (16. 10. 2026, tests/test_okna_ikone.py);
* zaslon: namizje QML ob spremembi locljivosti znova postavi dock (kot delovna povrsina WebKit).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)
JEZIKI = ("sl", "en", "de", "es", "fr", "it")
QML = os.path.join(KOREN, "assets", "os", "qml")


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def _slovar() -> dict:
    """BESEDILA_NAMIZJA prek Node (ce je na voljo), sicer razclenjeno kot v tools/preveri-prevode.py."""
    pot = os.path.join(KOREN, "assets", "os", "besedila-namizja.js")
    try:
        izid = subprocess.run(["node", "-e", "const fs=require('fs');process.stdout.write(JSON.stringify(new Function("
                               "fs.readFileSync(process.argv[1],'utf8')+';return BESEDILA_NAMIZJA')()))", pot],
                              capture_output=True, text=True, timeout=30)
        if izid.returncode == 0:
            return json.loads(izid.stdout)
    except (OSError, subprocess.TimeoutExpired):
        pass
    vsebina = _beri("assets", "os", "besedila-namizja.js")
    izid = {}
    for m in re.finditer(r"^  (\w+): \{\n(.*?)^  \}", vsebina, re.M | re.S):
        izid[m.group(1)] = {k: json.loads(v) for k, v in re.findall(r'^    "?([\w$]+)"?: ("(?:[^"\\]|\\.)*")', m.group(2), re.M)}
    return izid


def _orodje_prevodov():
    spec = importlib.util.spec_from_file_location("preveri_prevode", os.path.join(KOREN, "tools", "preveri-prevode.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class Jeziki(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = _slovar()

    def test_vseh_sest_jezikov_z_istimi_kljuci_in_zamenjavami(self):
        self.assertEqual(sorted(self.b), sorted(JEZIKI))
        for j in JEZIKI:
            self.assertEqual(set(self.b[j]), set(self.b["sl"]), j)
            for k, v in self.b[j].items():
                self.assertTrue(v, "%s.%s je prazen" % (j, k))
                self.assertEqual(sorted(re.findall(r"\{\w+\}", v)), sorted(re.findall(r"\{\w+\}", self.b["sl"][k])), "%s.%s" % (j, k))
        # Nemscina, spanscina, francoscina in italijanscina niso kopija anglescine.
        for j in ("de", "es", "fr", "it"):
            enako = [k for k in self.b[j] if self.b[j][k] == self.b["en"][k] and re.search(r"[a-z]{4}", self.b["en"][k])]
            self.assertLess(len(enako), 25, (j, enako[:10]))

    def test_vsak_uporabljen_kljuc_obstaja(self):
        kljuci = set(self.b["sl"])
        for ime in os.listdir(QML):
            # Sestavljeni kljuci (»ppIme_" + id«) se preverijo kot v delovna.js: samo celi nizi.
            for k in re.findall(r'koren\.t\("(\w+)"(?!\s*\+)', _beri("assets", "os", "qml", ime)):
                self.assertTrue(k in kljuci or ("qml_" + k) in kljuci, "%s: %s" % (ime, k))
        js = _beri("assets", "os", "delovna.js")
        for k in set(re.findall(r'\bt\("([A-Za-z0-9_]+)"(?!\s*\+)', js)):
            self.assertIn(k, kljuci, "delovna.js: " + k)
        html = _beri("assets", "os", "delovna.html")
        for k in re.findall(r'data-(?:t|ph)="([^"]+)"', html):
            self.assertIn(k, kljuci, "delovna.html: " + k)

    def test_en_vir_za_qml_in_webkit(self):
        nam = _beri("assets", "os", "qml", "Namizje.qml")
        self.assertIn('import "../besedila-namizja.js" as Besedila', nam)
        self.assertIn("readonly property var besedila: Besedila.BESEDILA_NAMIZJA", nam)
        self.assertNotRegex(nam, r"\bsl: \{ ")                          # nobenega lastnega slovarja vec
        self.assertNotIn('z.jezik === "sl" || z.jezik === "en"', nam)   # drugi jeziki niso vec prisiljeni v en
        js = _beri("assets", "os", "delovna.js")
        self.assertIn("var BESEDILA = window.BESEDILA_NAMIZJA;", js)
        self.assertNotIn("    sl: {", js)
        html = _beri("assets", "os", "delovna.html")
        self.assertLess(html.index('src="besedila-namizja.js"'), html.index('src="delovna.js"'))

    def test_orodje_preveri_tudi_namizje(self):
        orodje = _orodje_prevodov()
        jeziki, napake = orodje.zberi_besedila_namizja(KOREN)
        self.assertEqual(sorted(jeziki), sorted(JEZIKI))
        self.assertEqual(napake, [])
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "assets", "os"))
            with open(os.path.join(d, "assets", "os", "besedila-namizja.js"), "w", encoding="utf-8") as f:
                f.write('var BESEDILA_NAMIZJA = {\n  sl: {\n    a: "Ime {ime}",\n    b: "B"\n  },\n'
                        '  de: {\n    a: "Name {name}"\n  }\n};\n')
            jeziki, napake = orodje.zberi_besedila_namizja(d)
            self.assertEqual(jeziki["de"], {"a"})
            self.assertEqual(len(napake), 1)                             # {name} namesto {ime}
            self.assertNotEqual(orodje.primerjaj("x", jeziki, "sl"), [])  # manjka b

    def test_besedila_python_v_vseh_jezikih(self):
        from core import adblock, os_media_besedila, processes_page
        for slovar in (processes_page._TEXT, adblock.FAKE_BANK_TEXTS):
            self.assertEqual(sorted(slovar), sorted(JEZIKI))
            for j in JEZIKI:
                self.assertEqual(set(slovar[j]), set(slovar["en"]), j)
        for j in JEZIKI:
            for k in ("medijski_center", "tok_naslov", "tok_ime", "tok_tv", "tok_radio", "shrani_predvajaj", "izberi"):
                self.assertIn(k, os_media_besedila.BESEDILA[j], (j, k))
        # Obvestilo »pripravljam predvajalnik (enkrat)« je odpadlo z 1.0.127: Safeer DRM je v paketu, nic se ne prenasa.
        self.assertNotIn("def _drm_obvestilo", _beri("core", "os_splet.py"))
        os_ = _beri("safeer_os.py")
        self.assertNotIn('Gtk.Window(title="Dodaj TV ali radijski tok"', os_)
        self.assertNotIn('title="Medijski center"', os_)
        self.assertNotIn('set_title("Medijski center")', os_)


class Videz(unittest.TestCase):
    def test_paleta_iz_tokens(self):
        from core import os_lupina
        t = os_lupina.tokeni()
        p = os_lupina.paleta()
        self.assertEqual(p["poudarek"], "#8ac7ff")
        self.assertEqual(p["poudarek"], os_lupina._qml_barva(t["zelena"]))
        self.assertEqual(p["besedilo"], os_lupina._qml_barva(t["besedilo"]))
        self.assertEqual(p["karticaRgb"], os_lupina._rgb(t["kartica"]))
        self.assertEqual(set(p["vrste"]), set(os_lupina.VRSTE_DATOTEK))
        self.assertFalse(p["kontrast"])
        k = os_lupina.paleta(kontrast=True)
        self.assertTrue(k["kontrast"])
        self.assertGreater(k["robA"], p["robA"])                         # blok .kontrast iz tokens.css
        self.assertEqual(os_lupina._qml_barva((16, 26, 43, 0.8)), "#cc101a2b")

    def test_rezerva_qml_je_ista_kot_tokens(self):
        from core import os_lupina
        p = os_lupina.paleta()
        nam = _beri("assets", "os", "qml", "Namizje.qml")
        rezerva = nam[nam.index("property var paleta: ({"):nam.index("property real zameglitev")]
        for k in ("poudarek", "poudarekTemna", "besedilo", "medlo", "tise", "vnos", "ozadje", "ozadje2", "fokus"):
            self.assertIn('%s: "%s"' % (k, p[k]), rezerva, k)
        self.assertNotIn("#54d6a5", nam)

    def test_merilo_besedila(self):
        from core import os_lupina
        self.assertEqual(os_lupina.merilo_besedila(100), 1.0)
        self.assertEqual(os_lupina.merilo_besedila(150), 1.5)
        self.assertEqual(os_lupina.merilo_besedila(250), 2.0)
        self.assertEqual(os_lupina.merilo_besedila(125, 1.25), 1.0)      # Qt je povecal ze sam (Xft.dpi)
        self.assertEqual(os_lupina.merilo_besedila(150, 2.0), 1.5)       # HiDPI zaslon ni povecava besedila
        self.assertEqual(os_lupina.merilo_besedila("x"), 1.0)

    def test_qml_brez_trdo_kodiranih_barv(self):
        for ime in os.listdir(QML):
            vir = _beri("assets", "os", "qml", ime)
            self.assertNotRegex(vir, r'"#[0-9a-fA-F]{6}"' if ime != "Namizje.qml" else r'color: "#[0-9a-fA-F]{6}"', ime)
            self.assertNotIn("Qt.rgba(1, 1, 1", vir, ime)
            self.assertNotIn('"white"', vir, ime)
            self.assertNotRegex(vir, r"font\.pixelSize: \d", ime)        # velikost besedila sistema (koren.px)

    def test_strani_iz_tokens(self):
        tokeni = _beri("assets", "os", "tokens.css")
        self.assertIn(":root {", tokeni)
        self.assertIn(".kontrast, body.manj-prosojnosti {", tokeni)
        for css in ("os.css", "delovna.css", "sporocila-plosca.css", "vrstica.css"):
            vir = re.sub(r"/\*.*?\*/", "", _beri("assets", "os", css), flags=re.S)
            koren = re.search(r":root\s*\{([^}]*)\}", vir)
            if koren:
                self.assertNotRegex(koren.group(1), r"#[0-9a-fA-F]{3,6}|rgba?\(", css)   # barve niso vec v :root strani
        self.assertNotRegex(_beri("assets", "os", "vrstica.css"), r"#[0-9a-fA-F]{3,6}\b|rgba?\(")
        for html, css in (("index.html", "os.css"), ("delovna.html", "delovna.css"),
                          ("sporocila-plosca.html", "sporocila-plosca.css"), ("vrstica.html", "vrstica.css")):
            h = _beri("assets", "os", html)
            self.assertLess(h.index('href="tokens.css"'), h.index('href="%s"' % css), html)


class Tipkovnica(unittest.TestCase):
    def test_gumb_tipkovnica_in_fokus(self):
        g = _beri("assets", "os", "qml", "Gumb.qml")
        for niz in ("activeFocusOnTab: enabled && visible", "Keys.onReturnPressed", "Keys.onSpacePressed",
                    "Accessible.role: Accessible.Button", "border.width: activeFocus ? 2 : 1", "implicitWidth:"):
            self.assertIn(niz, g)

    def test_escape_zapre_vrhnji_sloj(self):
        nam = _beri("assets", "os", "qml", "Namizje.qml")
        self.assertIn("Keys.onEscapePressed: koren.zapriVrhnje()", nam)
        self.assertIn("sequences: [StandardKey.Cancel, \"Back\"]", nam)
        pri = _beri("assets", "os", "qml", "Prilagodi.qml")
        self.assertIn("Keys.onEscapePressed: zapri()", pri)
        # Okna Datotek, Programov in iskanja so Okno.qml (Popup: modalno, fokus, Escape zapre - CloseOnEscape privzeto);
        # okni z napredkom (Shrani na napravo, Pretvori za TV) zapre samo Escape, Uredi dock vrne Escape na seznam.
        self.assertIn("modal: true; focus: true", _beri("assets", "os", "qml", "Okno.qml"))
        dat = _beri("assets", "os", "qml", "Datoteke.qml")
        self.assertGreaterEqual(len(re.findall(r"^    Okno \{", dat, re.M)), 2)
        for ime in ("NovoIme.qml", "Lastnosti.qml", "ShraniNaNapravo.qml", "PretvoriZaTv.qml", "UrediDock.qml", "PonudnikiProgramov.qml"):
            self.assertRegex(_beri("assets", "os", "qml", ime), r"(?m)^Okno \{", ime)
        self.assertIn("closePolicy: Popup.CloseOnEscape", _beri("assets", "os", "qml", "ShraniNaNapravo.qml"))
        self.assertIn("Keys.onEscapePressed: function (d) { if (okno.izbiram)", _beri("assets", "os", "qml", "UrediDock.qml"))

    def test_kavc_na_delovni_povrsini(self):
        html = _beri("assets", "os", "delovna.html")
        self.assertIn('<html lang="sl" data-kavc="namizje">', html)
        self.assertLess(html.index('src="delovna.js"'), html.index('src="kavc.js"'))
        kavc = _beri("assets", "os", "kavc.js")
        self.assertIn('html.getAttribute("data-kavc") === "namizje"', kavc)
        self.assertIn("!e.defaultPrevented && (e.key === \"BrowserBack\"", kavc)


class Okna(unittest.TestCase):
    def test_razred_okna_safeer_os(self):
        vir = _beri("safeer_os.py")
        namizni = _beri("packaging", "safeer-os.desktop")
        self.assertIn("StartupWMClass=safeer-os\n", namizni)
        self.assertIn('RAZRED_SAFEER_OS = "safeer-os"', vir)
        for vloga in ('_razred_okna(okno, "Sporocila")', "_razred_okna(okno, ime)", '_razred_okna(okno, "Splet")',
                      '_razred_okna(dialog, "Dialog")', "_razred_okna(okno)"):
            self.assertIn(vloga, vir)
        for star in ('"safeer-os." + ime, _naslov_razdelka(ime)', '"Safeer Splet"', '"safeer-os.Sporocila", "Safeer"'):
            self.assertNotIn(star, vir)

    def test_razred_in_ikona(self):
        import safeer_os as so
        okno = mock.MagicMock()
        with mock.patch.object(so.x11, "nastavi_razred") as razred, mock.patch.object(so, "_ikona_safeer_os", return_value="safeer-os"):
            so._razred_okna(okno, "Splet")
        # Od 16. 10. 2026 ima Splet svoj razred in ikono (prej skupna »safeer-os« - Splet in Sporocila enaka v docku).
        razred.assert_called_once_with(okno, "safeer-os.splet", "safeer-os.splet")
        self.assertEqual(okno.set_icon_name.call_count, 1)


class NamizjeQmlZivo(unittest.TestCase):
    """Namizje QML (offscreen) z laznim SafeerOS: jezik, paleta, kontrast, velikost besedila, Escape, dock."""

    @classmethod
    def setUpClass(cls):
        try:
            import PySide6  # noqa: F401 - preveri, ali je namescen
        except ImportError:
            raise unittest.SkipTest("PySide6 ni namescen")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["test"])

    def _pocakaj(self, pogoj, cas=4.0):
        import time
        from gi.repository import GLib
        from PySide6.QtCore import QCoreApplication
        konec = time.monotonic() + cas
        while time.monotonic() < konec:
            QCoreApplication.processEvents()
            GLib.MainContext.default().iteration(False)
            if pogoj():
                return True
            time.sleep(0.02)
        return pogoj()

    def _namizje(self, jezik):
        import safeer_os as so
        from core import os_lupina

        class Os:
            shramba = {}

            def _zacetek(self):
                return {"jezik": jezik, "platforma": "linux", "mape": []}

            def _obdelaj_klic(self, pogled, klic_id, metoda, a):
                pogled.qml_odgovor(klic_id, True, {"predvajalnikStanje": {}}.get(metoda, []))
        zaplate = [mock.patch.object(so, "_jezik", return_value=jezik),
                   mock.patch.object(so, "videz_cinnamon", return_value={"naVoljo": True, "kontrast": False, "tekstOdstotek": 100})]
        for z in zaplate:
            z.start()
            self.addCleanup(z.stop)
        n = os_lupina.Namizje(Os(), v_oknu=True)
        self.addCleanup(n.okno.close)
        self.assertEqual(n.okno.errors(), [])
        return n

    def test_nemscina_in_modra_paleta(self):
        from PySide6.QtCore import QObject
        n = self._namizje("de")
        koren = n.okno.rootObject()
        naslov = koren.findChild(QObject, "medijNaslov")
        self.assertTrue(self._pocakaj(lambda: naslov.property("text") == "Es wird nichts abgespielt"))
        self.assertEqual(koren.property("jezik"), "de")
        paleta = koren.property("paleta")
        paleta = paleta.toVariant() if hasattr(paleta, "toVariant") else paleta
        self.assertEqual(paleta["poudarek"], "#8ac7ff")

    def test_kontrast_in_vecje_besedilo_iz_dogodka(self):
        from core import os_lupina
        n = self._namizje("sl")
        koren = n.okno.rootObject()
        # »sl« je privzeti jezik: na odgovor »zacetek« pocakamo po platformi, sicer bi njegov videz (merilo 1) prisel
        # za dogodkom spodaj in ga prepisal (obcasen padec, tudi na gtk4 pred 15. 10. 2026).
        self.assertTrue(self._pocakaj(lambda: koren.property("jezik") == "sl" and koren.property("platforma") == "linux"))
        self.assertAlmostEqual(koren.property("merilo"), 1.0)
        n.dogodek("videz", {"paleta": os_lupina.paleta(kontrast=True, merilo=1.5), "kontrast": True})
        self.assertTrue(self._pocakaj(lambda: abs(koren.property("merilo") - 1.5) < 1e-6))
        self.assertTrue(koren.property("kontrast"))
        self.assertGreaterEqual(koren.property("prosojnostPlosc"), 0.94)
        self.assertEqual(koren.property("zameglitevPlosc"), 0)
        # Delni dogodek ne pobrise seznama ozadij (Prilagodi namizje).
        self.assertIn("ozadja", (koren.property("videz").toVariant() if hasattr(koren.property("videz"), "toVariant")
                                 else koren.property("videz")))

    def test_escape_zapre_prilagodi(self):
        from PySide6.QtCore import QMetaObject, QObject, Qt
        from PySide6.QtTest import QTest
        n = self._namizje("sl")
        n.okno.show()
        koren = n.okno.rootObject()
        prilagodi = koren.findChild(QObject, "prilagodi")
        QMetaObject.invokeMethod(prilagodi, "odpri")
        self.assertTrue(self._pocakaj(lambda: prilagodi.property("visible")))
        QTest.keyClick(n.okno, Qt.Key.Key_Escape)
        self.assertTrue(self._pocakaj(lambda: not prilagodi.property("visible")))

    def test_sprememba_zaslona_postavi_dock(self):
        from core import os_lupina
        n = self._namizje("sl")
        with mock.patch("shutil.which", return_value="/usr/bin/safeer-cinnamon"), \
                mock.patch("subprocess.Popen") as popen:
            os_lupina.Namizje._postavi_dock(n)
        self.assertEqual(popen.call_args[0][0], ["safeer-cinnamon", "--dock"])
        vir = _beri("core", "os_lupina.py")
        # Sprememba geometrije trenutnega zaslona in zamenjava primarnega zaslona (HDMI na TV) postavita dock na novo.
        self.assertIn("zaslon.geometryChanged.connect(lambda *_: self._zaslon_spremenjen()", vir)
        self.assertIn("aplikacija.primaryScreenChanged.connect(lambda *_: self._zaslon_spremenjen())", vir)


if __name__ == "__main__":
    unittest.main()

"""»Predvaja se« na namizju QML in »Predvajaj na …« (lastnik, 14. 10. 2026: med glasbo je pripomocek kazal
»Ni predvajanja«; glasbo hoce poslati na zvocnik v domacem omrezju).

* izhod.js: ena logika izbire izhoda (ta racunalnik, Safeer Link, zvocnik DLNA) s privolitvijo za zaseden zvocnik -
  pozenemo jo z node, z laznim mostom;
* Medijski center (os.js), delovna povrsina (delovna.js) in namizje QML imajo gumb »Predvajaj na …«;
* pripomocek Medijski center v Namizje.qml bere predvajalnikStanje in ima tri tipke z dostopnimi imeni.
Izris je bil preverjen z WebKitGTK 6.0 in Qt Quick (xcb) pod xvfb, 1440 x 900."""
import json
import os
import re
import shutil
import subprocess
import unittest
from besedila_namizja import besedila, stevilo  # noqa: E402 - skupni slovar namizja

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEZIKI = ("sl", "en", "de", "es", "fr", "it")


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


ZVOK = {"izhodi": [{"id": "a", "ime": "Vgrajeni zvočniki", "privzeti": True}],
        "link": {"povezan": True, "naprave": [{"id": "tv1", "ime": "TV", "platforma": "tv"}], "zvok": {"naprava": "", "stanje": ""},
                 "zvocniki": [{"id": "dlna:1", "ime": "Zvočnik dnevna soba", "model": "JBL Bar 500"}], "zvocnik": {"naprava": "", "stanje": ""}}}

OGRODJE = r"""
var fs = require("fs");
eval(fs.readFileSync(process.argv[1], "utf8"));
var koraki = JSON.parse(process.argv[2]), z = JSON.parse(process.argv[3]);
var klici = [], obvestila = [], odgovori = koraki.odgovori || {};
var st = SafeerIzhod.novoStanje();
var o = { klic: function (m, a, ok) { klici.push([m, a]); ok(odgovori[m] === undefined ? true : odgovori[m]); },
          obvesti: function (k, zam) { obvestila.push([k, zam || null]); }, osvezi: function () {}, narisi: function () {},
          pozneje: function (ms, fn) { fn(); } };
var izid = { moznosti: SafeerIzhod.moznosti(z), aktivna: SafeerIzhod.aktivna(z), imaDruge: SafeerIzhod.imaDruge(z) };
(koraki.izberi || []).forEach(function (i) { SafeerIzhod.izberi(st, SafeerIzhod.moznosti(z)[i], z, o); });
izid.klici = klici; izid.obvestila = obvestila; izid.st = st;
console.log(JSON.stringify(izid));
"""


@unittest.skipUnless(shutil.which("node"), "node ni namescen")
class SkupnaLogika(unittest.TestCase):
    def _pozeni(self, z, **koraki):
        r = subprocess.run([shutil.which("node"), "-e", OGRODJE, os.path.join(KOREN, "assets", "os", "izhod.js"),
                            json.dumps(koraki), json.dumps(z)], capture_output=True, text=True, timeout=30, check=True)
        return json.loads(r.stdout)

    def test_moznosti(self):
        r = self._pozeni(ZVOK)
        self.assertEqual([(m["vrsta"], m["id"], m["aktiven"]) for m in r["moznosti"]],
                         [("racunalnik", "", True), ("naprava", "tv1", False), ("zvocnik", "dlna:1", False)])
        self.assertEqual(r["moznosti"][0]["pod"], "Vgrajeni zvočniki")
        self.assertEqual(r["moznosti"][2]["model"], "JBL Bar 500")
        self.assertTrue(r["imaDruge"])
        prazno = self._pozeni({"izhodi": [], "link": {}})
        self.assertFalse(prazno["imaDruge"])
        self.assertEqual(prazno["aktivna"]["vrsta"], "racunalnik")

    def test_aktiven_zvocnik_in_vrnitev(self):
        z = json.loads(json.dumps(ZVOK))
        z["link"]["zvocnik"] = {"naprava": "dlna:1", "stanje": "tece"}
        r = self._pozeni(z, izberi=[0])
        self.assertEqual(r["aktivna"]["id"], "dlna:1")
        self.assertEqual(r["aktivna"]["stanje"], "tece")
        self.assertEqual(r["klici"], [["zvokUstaviZvocnik", []]])          # ta racunalnik = zvok nazaj
        self.assertEqual(r["obvestila"], [["zvokNazaj", None]])
        z["link"]["zvocnik"] = {"naprava": ""}
        z["link"]["zvok"] = {"naprava": "tv1", "stanje": "tece"}
        self.assertEqual(self._pozeni(z, izberi=[0])["klici"], [["zvokUstavi", []]])
        self.assertEqual(self._pozeni(z, izberi=[1])["klici"], [])          # aktivne izbire ne ponovimo

    def test_zaseden_zvocnik_sele_po_drugem_pritisku(self):
        r = self._pozeni(ZVOK, izberi=[2], odgovori={"zvokNaZvocnik": {"ok": False, "vir": "HDMI"}})
        self.assertEqual(r["klici"], [["zvokNaZvocnik", ["dlna:1", False]]])
        self.assertEqual(r["st"]["potrdi"], {"dlna:1": "HDMI"})
        self.assertEqual(r["obvestila"][0][0], "zvokZvocnikZaseden")
        r = self._pozeni(ZVOK, izberi=[2, 2], odgovori={"zvokNaZvocnik": {"ok": False, "vir": "HDMI"}})
        self.assertEqual(r["klici"][1], ["zvokNaZvocnik", ["dlna:1", True]])    # privolitev ob drugem pritisku

    def test_naprava_v_linku(self):
        r = self._pozeni(ZVOK, izberi=[1])
        self.assertEqual(r["klici"], [["zvokNaNapravo", ["tv1"]]])
        self.assertEqual(r["obvestila"], [["zvokNaNapravoZacet", {"ime": "TV"}]])
        self.assertEqual(r["st"]["caka"], "")
        r = self._pozeni(ZVOK, izberi=[1], odgovori={"zvokNaNapravo": False})
        self.assertEqual(r["obvestila"], [["niUspelo", None]])

    def test_brez_dom_in_casovnikov(self):
        # QML jo uvozi kot knjiznico JavaScript: ne sme uporabljati okna, dokumenta ali setTimeout.
        js = re.sub(r"/\*.*?\*/|//[^\n]*", "", _beri("assets", "os", "izhod.js"), flags=re.S)
        for prepovedano in ("document", "window", "setTimeout", "setInterval", "localStorage"):
            self.assertNotIn(prepovedano, js)


class Stran(unittest.TestCase):
    def test_skripta_je_nalozena_pred_stranjo(self):
        for html, js in (("index.html", "os.js"), ("delovna.html", "delovna.js")):
            h = _beri("assets", "os", html)
            self.assertLess(h.index('<script src="izhod.js"></script>'), h.index('<script src="%s"></script>' % js), html)
        self.assertIn('import "../izhod.js" as Izhod', _beri("assets", "os", "qml", "Namizje.qml"))

    def test_gumb_in_plosca_medijskega_centra(self):
        h, js = _beri("assets", "os", "index.html"), _beri("assets", "os", "os.js")
        self.assertIn('id="mediaBarIzhod" type="button" data-naslov="predvajajNa" aria-haspopup="dialog" aria-expanded="false" '
                      'aria-controls="mediaIzhodPlosca"', h)
        self.assertIn('id="mediaIzhodPlosca" role="dialog"', h)   # nacin za kavc ujame izbor v odprtem oknu (kavc.js)
        self.assertIn('if (e.key === "Escape" && zapriIzhode(true)) { e.preventDefault(); e.stopImmediatePropagation(); }', js)
        self.assertIn('e.key === "ArrowDown" ? i + 1 : e.key === "ArrowUp" ? i - 1', js)
        # Hitre nastavitve zvoka in Medijski center uporabljata isto logiko (brez podvojenih klicev mostu).
        self.assertEqual(js.count('klic("zvokNaZvocnik"'), 0)
        self.assertEqual(js.count("SafeerIzhod.izberi("), 2)

    def test_delovna_povrsina(self):
        h, js = _beri("assets", "os", "delovna.html"), _beri("assets", "os", "delovna.js")
        self.assertIn('id="gumbIzhod" data-naslov="predvajajNa" aria-haspopup="dialog"', h)
        self.assertIn('id="meniIzhod" role="dialog"', h)
        self.assertIn("SafeerIzhod.izberi(st, m, z, izhodGost())", js)
        # Brez praznega drsnika, ko predvajalnik polozaja ne pozna (YouTube, tok v zivo).
        self.assertIn('$("medijNapredek").parentNode.style.visibility = ima && p.trajanje > 0 ? "" : "hidden";', js)

    def test_besedila(self):
        bes = _beri("assets", "os", "besedila.js")
        for kljuc in ("predvajajNa", "predvajajNaNaslov", "predvajaNa", "zvokIsci", "zvokIscem", "zvokNiIzhodov", "izhodNalagam"):
            self.assertEqual(bes.count('"%s":' % kljuc), 6, kljuc)
            self.assertEqual(stevilo(kljuc), 6, kljuc)      # delovna povrsina in namizje QML: skupni slovar
        for j in JEZIKI:
            self.assertIn('Object.assign(BESEDILA_OS.%s, {"predvajajNa"' % j, bes)


class NamizjeQmlStaticno(unittest.TestCase):
    def setUp(self):
        self.q = _beri("assets", "os", "qml", "Namizje.qml")

    def test_ni_vec_nadomestka(self):
        # Prej: vedno »Ni predvajanja« brez stanja in tipk (pravilo: brez nadomestkov v vmesniku).
        self.assertIn('koren.klic("predvajalnikStanje"', self.q)
        self.assertIn('koren.klic("predvajalnikUkaz", [u]', self.q)
        self.assertIn('interval: koren.medij.stanje === "predvaja" ? 1000 : 3000', self.q)
        self.assertIn('if (vrsta === "predvajalnik" && p) koren.medij = p', self.q)
        self.assertIn('text: koren.medijIgra ? koren.medij.naslov : koren.t("niPredvajanja")', self.q)

    def test_tri_tipke_z_imeni(self):
        for ime, ukaz, napis in (("medijPrejsnja", "prejsnja", 'koren.t("prejsnja")'), ("medijPremor", "premor", None),
                                 ("medijNaslednja", "naslednja", 'koren.t("naslednja")')):
            del_ = self.q.split('objectName: "%s"' % ime, 1)[1].split("GumbIkona {", 1)[0]
            self.assertIn('onKlik: koren.medijUkaz("%s")' % ukaz, del_)
            self.assertIn(napis or 'koren.t("premor") : koren.t("nadaljuj")', del_)
        g = _beri("assets", "os", "qml", "GumbIkona.qml")
        for niz in ("Accessible.role: Accessible.Button", "Accessible.name: ime", "activeFocusOnTab: enabled",
                    "Keys.onReturnPressed", "Keys.onSpacePressed", "border.width: activeFocus ? 2 : 0"):
            self.assertIn(niz, g)

    def test_polozaj_samo_ko_je_znan(self):
        self.assertIn("visible: koren.medijIgra && Number(koren.medij.trajanje) > 0", self.q)

    def test_velikost_pripomocka_ostane(self):
        self.assertIn("width: (koren.width - koren.robLevo - koren.robDesno - 3 * koren.rob) * 0.44; height: Math.max(150, medijVsebina.implicitHeight + 36)", self.q)


class NamizjeQmlZivo(unittest.TestCase):
    """Namizje QML (offscreen) z laznim SafeerOS: kaj se predvaja, tipke, prazno stanje."""

    @classmethod
    def setUpClass(cls):
        try:
            import PySide6  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("PySide6 ni namescen")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["test"])

    def _pocakaj(self, pogoj, cas=4.0):
        import time
        from PySide6.QtCore import QCoreApplication
        konec = time.monotonic() + cas
        while time.monotonic() < konec:
            QCoreApplication.processEvents()
            from gi.repository import GLib
            GLib.MainContext.default().iteration(False)
            if pogoj():
                return True
            time.sleep(0.02)
        return pogoj()

    def test_predvaja_in_tipke(self):
        from PySide6.QtCore import QObject
        from core import os_lupina
        klici, stanje = [], {"p": {"stanje": "predvaja", "naslov": "Modra reka", "izvajalec": "Ana Kos", "izvor": "YouTube",
                                    "trajanje": 0, "vrstaStrani": True}}

        class Os:
            shramba = {}

            def _zacetek(self):
                return {"jezik": "sl", "platforma": "linux", "mape": []}

            def _obdelaj_klic(self, pogled, klic_id, metoda, a):
                klici.append((metoda, a))
                pogled.qml_odgovor(klic_id, True, {"predvajalnikStanje": stanje["p"], "predvajalnikUkaz": True}.get(metoda, []))
        n = os_lupina.Namizje(Os(), v_oknu=True)
        self.assertEqual(n.okno.errors(), [])
        koren = n.okno.rootObject()
        naslov = koren.findChild(QObject, "medijNaslov")
        self.assertTrue(self._pocakaj(lambda: naslov.property("text") == "Modra reka"))
        self.assertIn("Ana Kos · YouTube", koren.findChild(QObject, "medijOpis").property("text"))
        self.assertFalse(koren.findChild(QObject, "medijNapredek").property("visible"))
        for ime, napis in (("medijPrejsnja", "Prejšnja"), ("medijPremor", "Premor"), ("medijNaslednja", "Naslednja")):
            g = koren.findChild(QObject, ime)
            self.assertEqual(g.property("ime"), napis)
            self.assertTrue(g.property("enabled"))           # vrsto vodi stran: naslednja je na voljo
        koren.findChild(QObject, "medijNaslednja").klik.emit()
        self.assertTrue(self._pocakaj(lambda: ("predvajalnikUkaz", ["naslednja"]) in klici))
        stanje["p"] = {"stanje": "ustavljeno", "naslov": ""}
        self.assertTrue(self._pocakaj(lambda: naslov.property("text") == "Ni predvajanja", 6.0))


if __name__ == "__main__":
    unittest.main()

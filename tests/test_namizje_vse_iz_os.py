"""Namizje Safeer = vse iz aplikacije Safeer OS (cilj 3.1, lastnik 18. 10. 2026; popis docs/NAMIZJE-POPIS.md).

* Z namizja se staro glavno okno Safeer OS ne odpre vec: Omrezje in Zvok sta podstrani okna Nastavitve, Datoteke in
  Programi plosci namizja, neznan razdelek nicesar (prej: _ustvari_okno - cela stara lupina).
* Pripomocek Medijski center: premik po posnetku, cas, Ustavi, glasnost, cakalna vrsta, odprtje predvajanja.
* Gumb Sporocila s stevilom neprebranih (isto kot kuverta), opomba o posodobitvi, spletne aplikacije (dodaj, odstrani,
  privzete kot na Domov aplikacije)."""
import json
import os
import re
import subprocess
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class _Os:
    def __init__(self):
        self.okno = None
        self.okno_delovna = object()
        self.klici = []

    def _odpri_okno_razdelka(self, ime, cilj=""):
        self.klici.append(("okno", ime, cilj)); return True

    def _pokazi_na_namizju(self, razdelek, pot=""):
        self.klici.append(("namizje", razdelek, pot)); return True

    def _prijava(self):
        self.klici.append(("control",)); return True

    def _splet_na_namizju(self, niz, vrh=0, domov=False):
        self.klici.append(("splet", niz, domov)); return True

    def _odpri_predvajalnik(self, iskanje=""):
        self.klici.append(("player", iskanje)); return True

    def _ustvari_okno(self):
        self.klici.append(("lupina",))

    def _domov(self, razdelek=""):
        self.klici.append(("domov", razdelek)); return True


class StaroOknoNikoli(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.so = safeer_os

    def _odpri(self, razdelek):
        o = _Os()
        with mock.patch.object(self.so.GLib, "timeout_add", lambda *a, **k: 0):
            izid = self.so.SafeerOS._odpri_razdelek(o, razdelek)
        return izid, o.klici

    def test_omrezje_in_zvok_v_oknu_nastavitve(self):
        # Prej: ploscica Omrezje ali Zvok v oknu Nastavitve -> odpriRazdelek -> _ustvari_okno (stara lupina).
        self.assertEqual(self._odpri("omrezje"), (True, [("okno", "nastavitve", "omrezje")]))
        self.assertEqual(self._odpri("zvok"), (True, [("okno", "nastavitve", "zvok")]))
        # Vodnik ob prvem zagonu: prej ga je pokazalo samo staro glavno okno.
        self.assertEqual(self._odpri("vodnik"), (True, [("okno", "nastavitve", "vodnik")]))

    def test_datoteke_in_programi_na_namizju(self):
        self.assertEqual(self._odpri("datoteke")[1], [("namizje", "datoteke", "")])
        self.assertEqual(self._odpri("datoteke:/home/u/Dokumenti")[1], [("namizje", "datoteke", "/home/u/Dokumenti")])
        self.assertEqual(self._odpri("programi")[1], [("namizje", "programi", "")])

    def test_noben_razdelek_ne_odpre_stare_lupine(self):
        for r in ("domov", "media", "mediji:x", "naprave", "sporocila", "pogovor:a:b", "kanal:k", "zapiski", "zapisek:1",
                  "splet", "programi", "datoteke", "nastavitve", "nastavitve#blokPosodobitve", "omrezje", "zvok", "scit",
                  "hitro", "neznano"):
            with mock.patch.object(self.so.sporocila_vklop, "sporocila_vklopljena", lambda: True):
                self.assertNotIn(("lupina",), self._odpri(r)[1], r)
        self.assertEqual(self._odpri("neznano"), (False, []))

    def test_podstrani_so_isti_seznam_v_strani(self):
        js = _beri("assets", "os", "os.js")
        m = re.search(r"var PODSTRANI_OKNA = \{ nastavitve: \[([^\]]*)\] \};", js)
        self.assertIsNotNone(m)
        self.assertEqual(tuple(json.loads("[" + m.group(1) + "]")), self.so.PODSTRANI_NASTAVITEV)
        self.assertIn("if (!vTemOknu(razdelek)) {", js)
        # Gumb Nazaj na podstrani gre v Nastavitve (isto okno), sidro Posodobitev obstaja.
        html = _beri("assets", "os", "index.html")
        self.assertIn('id="gumbOmrezjeNazaj"', html)
        self.assertIn('id="blokPosodobitve"', html)

    def test_okno_nastavitve_pokaze_podstran_samo(self):
        """vTemOknu iz os.js: v oknu Nastavitve sta Omrezje in Zvok lokalna, drugo gre Safeer OS; glavno okno vse."""
        js = _beri("assets", "os", "os.js")
        zac = js.index("  var PODSTRANI_OKNA")
        kon = js.index("\n  }\n", js.index("function vTemOknu")) + 4
        koda = js[zac:kon]
        prog = ("var EN_RAZDELEK = process.argv[1];" + koda +
                "console.log(JSON.stringify(['omrezje','zvok','nastavitve','datoteke','zapiski'].map(vTemOknu)));")
        try:
            izhod = subprocess.run(["node", "-e", prog, "nastavitve"], capture_output=True, text=True, timeout=20)
        except FileNotFoundError:
            self.skipTest("node ni namescen")
        self.assertEqual(json.loads(izhod.stdout), [True, True, True, False, False])
        izhod = subprocess.run(["node", "-e", prog, "zapiski"], capture_output=True, text=True, timeout=20)
        self.assertEqual(json.loads(izhod.stdout), [False, False, False, False, True])
        izhod = subprocess.run(["node", "-e", prog, ""], capture_output=True, text=True, timeout=20)
        self.assertEqual(json.loads(izhod.stdout), [True] * 5)

    def test_pokazi_na_namizju_poslje_dogodek_lupini(self):
        poslano = []
        o = mock.Mock(lupina=None, _qml_pogled="qml", pogled_delovna="qml")
        o._dogodek = lambda v, p, pogled=None: poslano.append((v, p, pogled))
        self.assertTrue(self.so.SafeerOS._pokazi_na_namizju(o, "datoteke", "/x"))
        self.assertEqual(poslano, [("pokaziNaNamizju", {"razdelek": "datoteke", "pot": "/x"}, "qml")])
        o = mock.Mock(lupina=None, _qml_pogled=None, pogled_delovna=None)
        self.assertFalse(self.so.SafeerOS._pokazi_na_namizju(o, "programi"))

    def test_delovna_povrsina_webkit_pozna_dogodek(self):
        js = _beri("assets", "os", "delovna.js")
        self.assertIn('vrsta === "pokaziNaNamizju"', js)
        self.assertIn('if (z.vodnik) klic("odpriRazdelek", ["vodnik"])', js)

    def test_vodnik_v_oknu_nastavitve(self):
        js = _beri("assets", "os", "os.js")
        self.assertIn('if (kam === "vodnik") {', js)
        self.assertIn("if (S.vodnikPoZacetku) { S.vodnikPoZacetku = false; odpriVodnik(); }", js)
        # Glavno okno ga se vedno odpre samo (zacetek), okno razdelka samo na ukaz z namizja.
        self.assertIn("if (z.vodnik) odpriVodnik(); else if (z.vrnitev) odpriVrnitev();", js)


class SpletneAplikacije(unittest.TestCase):
    def test_privzete_iste_kot_v_aplikaciji(self):
        from core import os_spletne
        js = _beri("assets", "os", "os.js")
        blok = js[js.index("var PRIVZETE_SPLETNE = ["):js.index("];", js.index("var PRIVZETE_SPLETNE = ["))]
        v_js = re.findall(r'\{ ime: "([^"]+)", url: "([^"]+)" \}', blok)
        self.assertEqual(tuple(v_js), os_spletne.PRIVZETE)

    def test_dodaj_odstrani(self):
        from core import os_spletne as s
        self.assertEqual(len(s.vidne(None)), 4)
        self.assertEqual(s.vidne([]), [], "uporabnik je odstranil vse: privzetih ne vrnemo")
        seznam, napaka = s.dodaj(None, "", "www.example.org/")
        self.assertEqual(napaka, "")
        self.assertEqual(seznam[-1], {"ime": "example.org", "url": "https://www.example.org"})
        self.assertEqual(s.dodaj(seznam, "x", "https://www.example.org")[1], "ze")
        for slab in ("", "localhost", "javascript:alert(1)", "ftp://example.org", "file:///etc/passwd"):
            self.assertEqual(s.dodaj(None, "x", slab)[1], "naslov", slab)
        self.assertEqual(s.iz_vnosa("http://localhost:8080/"), "http://localhost:8080")
        polno = [{"ime": "a%d" % i, "url": "https://a%d.si" % i} for i in range(s.MEJA)]
        self.assertEqual(s.dodaj(polno, "x", "b.si")[1], "polno")
        self.assertEqual([a["ime"] for a in s.odstrani(None, "https://www.youtube.com/")], ["RTV 365", "Gmail", "Wikipedia"])


class NamizjeQmlVseIzOs(unittest.TestCase):
    """Namizje QML (offscreen) z laznim SafeerOS - kot test_qml_enakost.NamizjeQml."""

    DOM = "/home/uporabnik"

    @classmethod
    def setUpClass(cls):
        try:
            import PySide6  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("PySide6 ni namescen")
        os.environ["QT_QPA_PLATFORM"] = os.environ.get("QT_QPA_PLATFORM") or "offscreen"  # rezervacija "" (okolje_procesa)
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["test"])

    def setUp(self):
        D = self.DOM
        self.odgovori = {
            "mapa": {"pot": D + "/Dokumenti", "stars": D, "elementi": []},
            "programiNamizja": [{"id": "gimp.desktop", "ime": "GIMP", "skupina": "ustvarjanje"}],
            "napraveNamizja": [],
            "povezava": {"control": True, "stanje": "povezan"},
            "predvajalnikStanje": {},
            "predvajalnikUkaz": True,
            "glasnost": True,
            "utisaj": True,
        }
        self.klici = []
        self.kuverta = []
        self.shranjeno = {}
        self.vodnik = False

    def _namizje(self):
        import safeer_os as so
        from core import os_lupina
        test = self

        class Os:
            shramba = test.shranjeno

            def _zacetek(self):
                return {"jezik": "sl", "platforma": "linux", "spletne": test.shranjeno.get("spletne"), "vodnik": test.vodnik,
                        "mape": [{"vrsta": "HOME", "ime": "Domov", "pot": test.DOM}]}

            def _seznam_programov(self):
                return test.odgovori["programiNamizja"]

            def _shrani_spletne(self, seznam):
                from core import os_spletne
                test.shranjeno["spletne"] = os_spletne.pocisti(seznam)
                return test.shranjeno["spletne"]

            def _osvezi_kuverto(self):
                test.kuverta.append(1)

            def _obdelaj_klic(self, pogled, klic_id, metoda, a):
                test.klici.append((metoda, a))
                if metoda == "shraniSpletne":
                    pogled.qml_odgovor(klic_id, True, self._shrani_spletne(a[0]))
                    return
                pogled.qml_odgovor(klic_id, True, test.odgovori.get(metoda, []))
        prava = os_lupina.Namizje._lastna

        def lastna(n, i, m, a):
            if m == "napraveNamizja":
                n.pogled.qml_odgovor(i, True, test.odgovori[m])
                return True
            return prava(n, i, m, a)
        for z in (mock.patch.object(so, "_jezik", return_value="sl"),
                  mock.patch.object(so, "videz_cinnamon", return_value={"naVoljo": True, "kontrast": False, "tekstOdstotek": 100}),
                  mock.patch("core.os_sistem.zvok", return_value={"glasnost": 40, "utisan": False}),
                  mock.patch.object(os_lupina.Namizje, "_lastna", lastna)):
            z.start()
            self.addCleanup(z.stop)
        n = os_lupina.Namizje(Os(), v_oknu=True)
        self.assertEqual(n.okno.errors(), [])
        self.n = n
        self.koren = n.okno.rootObject()
        self.assertTrue(self._pocakaj(lambda: self.koren.property("platforma") == "linux"))
        return n

    def tearDown(self):
        import gc
        n = getattr(self, "n", None)
        if n is not None:
            n.okno.close()
            n.okno.deleteLater()
        self.n = self.koren = None
        self._pocakaj(lambda: False, 0.1)
        gc.collect()

    def _pocakaj(self, pogoj, cas=4.0):
        from gi.repository import GLib
        from PySide6.QtCore import QCoreApplication
        konec = time.monotonic() + cas
        while time.monotonic() < konec:
            QCoreApplication.processEvents()
            GLib.MainContext.default().iteration(False)
            if pogoj():
                return True
            time.sleep(0.01)
        return pogoj()

    def _js(self, koda, objekt=None):
        from PySide6.QtQml import QQmlEngine, QQmlExpression
        o = objekt or self.koren
        e = QQmlExpression(QQmlEngine.contextForObject(o), o, koda)
        v = e.evaluate()
        self.assertFalse(e.hasError(), e.error().toString() if e.hasError() else "")
        if isinstance(v, tuple):
            v = v[0]
        return v.toVariant() if hasattr(v, "toVariant") else v

    def _obj(self, ime):
        from PySide6.QtCore import QObject
        o = self.koren.findChild(QObject, ime)
        self.assertIsNotNone(o, ime)
        return o

    def _klicano(self, metoda, a=None, cas=3.0):
        return self._pocakaj(lambda: any(m == metoda and (a is None or x == a) for m, x in self.klici), cas)

    def _predvaja(self, **dodatno):
        medij = {"stanje": "predvaja", "naslov": "Reka", "vrsta": "zvok", "indeks": 1, "zacetniIndeks": 0, "skupaj": 3,
                 "vrstaSeznam": [{"naslov": "Gora", "vrsta": "zvok", "izvor": ""}, {"naslov": "Reka", "vrsta": "zvok", "izvor": ""},
                                 {"naslov": "Morje", "vrsta": "zvok", "izvor": ""}],
                 "pozicija": 50, "trajanje": 200, "zivo": False}
        medij.update(dodatno)
        self.odgovori["predvajalnikStanje"] = medij
        self.n.dogodek("predvajalnik", medij)
        self.assertTrue(self._pocakaj(lambda: self._js("koren.medijIgra") is True))

    # ------------------------------------------------------------------ Medijski center
    def test_premik_cas_ustavi(self):
        self._namizje()
        self._predvaja()
        drsnik = self._obj("medijDrsnik")
        self.assertTrue(self._pocakaj(lambda: drsnik.property("enabled") is True and drsnik.property("value") == 50))
        self.assertEqual(self._obj("medijCas").property("text"), "0:50")
        self.assertEqual(self._obj("medijTrajanje").property("text"), "3:20")
        # Tipkovnica: puscica desno = +10 s, premik takoj.
        self._js("drsnikMedija.increase(); drsnikMedija.moved()")
        self.assertTrue(self._klicano("predvajalnikUkaz", ["skok", 60]))
        self._js("koren.medijUkaz('ustavi')")
        self.assertTrue(self._obj("medijUstavi").property("visible"))
        self.assertTrue(self._klicano("predvajalnikUkaz", ["ustavi"]))
        self.assertEqual(self._js("koren.casMedija(3725)"), "1:02:05")

    def test_v_zivo_brez_premika(self):
        self._namizje()
        self._predvaja(zivo=True, trajanje=0, vrsta="radio", skupaj=1)
        self.assertFalse(self._js("koren.medijPremik"))
        self.assertFalse(self._obj("medijNapredek").property("visible"))
        self.assertFalse(self._obj("medijVrsta").property("visible"), "ena postaja: brez cakalne vrste")

    def test_cakalna_vrsta(self):
        self._namizje()
        self._predvaja()
        self.assertTrue(self._pocakaj(lambda: self._obj("medijVrsta").property("visible")))
        self._js("vrstaPopup.open()")
        popup = self._obj("vrstaPopup")
        self.assertTrue(self._pocakaj(lambda: popup.property("visible")))
        self.assertEqual(self._js("seznamVrste.count"), 3)
        self.assertEqual(self._js("seznamVrste.currentIndex"), 1, "izbrana je skladba, ki igra")
        self._js("vrstaPopup.izberi(2)")
        self.assertTrue(self._klicano("predvajalnikUkaz", ["predvajaj", 2]))

    def test_glasnost(self):
        self._namizje()
        self._predvaja()
        self._js("glasnostPopup.open()")
        self.assertTrue(self._pocakaj(lambda: self._obj("drsnikGlasnosti").property("value") == 40))
        self.assertEqual(self._obj("glasnostOdstotek").property("text"), "40 %")
        self._js("drsnikGlasnosti.increase(); drsnikGlasnosti.moved()")
        self.assertTrue(self._klicano("glasnost", [45]))
        self._js("koren.klic('utisaj', [])")
        self.assertTrue(self._klicano("utisaj"))

    def test_ovitek_odpre_predvajanje(self):
        self._namizje()
        self._predvaja()
        self.odgovori["predvajalnikUkaz"] = False       # glasba nima okna: odpre se Medijski center
        self._js("koren.odpriPredvajanje()")
        self.assertTrue(self._klicano("predvajalnikUkaz", ["odpri"]))
        self.assertTrue(self._klicano("odpriRazdelek", ["media"]))

    # ------------------------------------------------------------------ Sporocila, posodobitev, razdelki
    def test_gumb_sporocila(self):
        self._namizje()
        gumb = self._obj("gumbSporocila")
        self.assertTrue(self._pocakaj(lambda: len(self.kuverta) > 0, 6), "3 s po zagonu namizje vprasa za stevilo")
        self.n.dogodek("sporocilaStevilo", {"n": 3})
        self.assertTrue(self._pocakaj(lambda: gumb.property("stevilo") == 3))
        self.assertTrue(gumb.property("visible"))
        self.assertEqual(gumb.property("ime"), "Neprebrana sporočila: 3")
        self._js("sporocilaGumb.klik()")
        self.assertTrue(self._klicano("odpriRazdelek", ["sporocila"]))
        self.n.dogodek("videz", {"sporocila": False})
        self.assertTrue(self._pocakaj(lambda: not gumb.property("visible")), "izklopljena Sporocila: gumba ni")

    def test_opomba_posodobitve(self):
        self._namizje()
        gumb = self._obj("gumbPosodobitev")
        self.assertFalse(gumb.property("visible"))
        self.n.dogodek("posodobitev", {"nove": ["safeer-os"], "opis": "Safeer OS 0.4.86"})
        self.assertTrue(self._pocakaj(lambda: gumb.property("visible")))
        self.assertEqual(gumb.property("besedilo"), "Na voljo je posodobitev: Safeer OS 0.4.86")
        self._js("posodobitevGumb.klik()")
        self.assertTrue(self._klicano("odpriRazdelek", ["nastavitve#blokPosodobitve"]))

    def test_razdelek_datoteke_in_programi_na_namizju(self):
        self._namizje()
        self.n.dogodek("pokaziNaNamizju", {"razdelek": "datoteke", "pot": self.DOM + "/Dokumenti"})
        self.assertTrue(self._klicano("mapa", [self.DOM + "/Dokumenti"]))
        self.n.dogodek("pokaziNaNamizju", {"razdelek": "programi", "pot": ""})
        self.assertTrue(self._pocakaj(lambda: self._obj("poljeProgramov").property("activeFocus")))

    def test_vodnik_ob_prvem_zagonu(self):
        self.vodnik = True
        self._namizje()
        self.assertTrue(self._klicano("odpriRazdelek", ["vodnik"]))

    def test_brez_vodnika_ce_ni_nova_namestitev(self):
        self._namizje()
        self._pocakaj(lambda: False, 0.5)
        self.assertFalse(any(m == "odpriRazdelek" for m, _a in self.klici))

    def test_iskanje_sporocil(self):
        self.odgovori["sporocilaSeznam"] = {"skupine": [
            {"oseba": {"ime": "Ana Novak", "identitete": [["email", "ana@example.org"]]},
             "pogovori": [{"id": "p1", "kanal_id": "k1", "zadeva": "", "zadnje_sporocilo": "Se vidiva jutri"}]},
            {"oseba": {"ime": "Bor", "identitete": []}, "pogovori": [{"id": "p2", "kanal_id": "k2", "zadeva": "Racun", "zadnje_sporocilo": ""}]}]}
        self._namizje()
        self._obj("iskalnoPolje").setProperty("text", "ana")
        najdi = "(function(){for (var i=0;i<zadetkiModel.count;i++) if (zadetkiModel.get(i).vrsta==='pogovor') return i; return -1})()"
        self.assertTrue(self._pocakaj(lambda: self._js(najdi) >= 0))
        i = int(self._js(najdi))
        self.assertEqual(self._js("zadetkiModel.get(%d).ime" % i), "Ana Novak")
        self.assertEqual(self._js("zadetkiModel.get(%d).opis" % i), "Se vidiva jutri")
        self.assertEqual(self._js("zadetkiModel.get(zadetki.trenutni).vrsta"), "pogovor", "Enter odpre pogovor osebe po imenu")
        self._js("zadetki.izberi(%d)" % i)
        self.assertTrue(self._klicano("odpriRazdelek", ["pogovor:k1:p1"]))
        # Po e-naslovu in zadevi tudi; seznam se ne bere ob vsaki crki (30 s), po novem sporocilu znova.
        stevilo = sum(1 for m, _a in self.klici if m == "sporocilaSeznam")
        self._obj("iskalnoPolje").setProperty("text", "racun")
        self.assertTrue(self._pocakaj(lambda: self._js("(function(){for (var i=0;i<zadetkiModel.count;i++) if (zadetkiModel.get(i).ime==='Bor') return true; return false})()")))
        self.assertEqual(sum(1 for m, _a in self.klici if m == "sporocilaSeznam"), stevilo)
        self.n.dogodek("sporocilaStevilo", {"n": 1})
        self.assertTrue(self._pocakaj(lambda: self._js("zadetki.sporocilaCas") == 0))

    # ------------------------------------------------------------------ spletne aplikacije
    def test_spletne_aplikacije(self):
        self._namizje()
        self.assertTrue(self._pocakaj(lambda: self._js("programi.spletne.length") == 4), "privzete kot na Domov aplikacije")
        self.assertIn("YouTube", self._js("programi.seznam.map(function (p) { return p.ime }).join(',')"))
        v_programih = self._obj("gumbDodajSpletno")         # id dodajSpletno je v kontekstu Programi.qml
        self._js("dodajSpletno.odpri()", v_programih)
        okno = self._obj("oknoSpletna")
        self.assertTrue(self._pocakaj(lambda: okno.property("visible")))
        self._obj("spletnaNaslov").setProperty("text", "localhost")
        self._js("dodajSpletno.potrdi()", v_programih)
        self.assertTrue(self._pocakaj(lambda: self._js("dodajSpletno.napaka", v_programih) == "To ni veljaven spletni naslov (http ali https)."))
        self._obj("spletnaNaslov").setProperty("text", "www.example.org")
        self._js("dodajSpletno.potrdi()", v_programih)
        self.assertTrue(self._pocakaj(lambda: self._js("programi.spletne.length") == 5))
        self.assertFalse(okno.property("visible"))
        self.assertEqual(self.shranjeno["spletne"][-1], {"ime": "example.org", "url": "https://www.example.org"})
        self._js("programi.odstraniSpletno({ ime: 'YouTube', url: 'https://www.youtube.com' })")
        self.assertTrue(self._pocakaj(lambda: self._js("programi.spletne.length") == 4))
        # Razveljavi: prejsnji seznam v istem vrstnem redu.
        self._js("obvestilo.ob()")
        self.assertTrue(self._pocakaj(lambda: self._js("programi.spletne.length") == 5))
        self.assertEqual(self.shranjeno["spletne"][0]["ime"], "YouTube")

    def test_besedila_v_vseh_jezikih(self):
        from besedila_namizja import stevilo
        for k in ("ustaviMedij", "glasnost", "utisaj", "vklopiZvok", "cakalnaVrsta", "polozajPredvajanja", "odpriPredvajanje",
                  "sporocilaGumb", "sporocilaNeprebrana", "posodobitevNaVoljo", "posodobitevOdpri", "spletnaDodaj", "spletnaIme",
                  "spletnaNaslov", "spletnaNapacenNaslov", "spletnaZeDodana", "spletnaPolno", "spletnaOdstrani", "spletnaDodana",
                  "spletnaOdstranjena", "dodaj", "skSporocila"):
            self.assertEqual(stevilo(k), 6, k)


if __name__ == "__main__":
    unittest.main()

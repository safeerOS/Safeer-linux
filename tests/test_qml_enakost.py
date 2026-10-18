"""Enakost namizja QML z delovno povrsino WebKit (pregled celovitosti 15. 10. 2026, lastnik: »vse je en proces, vsi nasi
dodatki delujejo kot del namiznega okolja«).

Namizje QML je privzeto, kadar je PySide6 na voljo, delovna povrsina WebKit (delovna.js) pa je uporabljala ~60 metod
mostu, ki jih QML ni. Preizkusi:
* vsaka metoda, ki jo klice QML, ima pot v SafeerOS._obdelaj_klic (ali v lupini os_lupina._lastna, katalogu);
* vsaka metoda delovne povrsine je v QML ali je zapisano, zakaj ne (ali s cim je nadomescena) - nova metoda v
  delovna.js brez odlocitve preizkus podre;
* klici gredo iz lupine QML (QmlPogled) skozi _obdelaj_klic do istih funkcij kot iz strani WebKit;
* namizje QML (offscreen, lazni SafeerOS): Datoteke (Najvecje, prostor, Lastnosti, Novo, Razveljavi, Prilepi, spust,
  Izvrzi, Nadaljuj tukaj, predvajanje z naprave), Programi (dock, ponudniki, igre v oblaku), iskanje (zapiski, mediji,
  »Prikazi na …«, glas)."""
import json
import os
import re
import threading
import time
import unittest
from unittest import mock

from besedila_namizja import stevilo

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QML = os.path.join(KOREN, "assets", "os", "qml")


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def _vsi_qml() -> str:
    return "\n".join(_beri("assets", "os", "qml", ime) for ime in sorted(os.listdir(QML)) if ime.endswith(".qml"))


def _metode(js: str, klicne=("klic", "pocakaj")) -> set:
    """Imena metod mostu: klic("x", …), klic(a ? "x" : "y", …), pocakaj("x", …) in metoda = "x"."""
    imena = set()
    for m in re.finditer(r"\b(?:%s)\(([^,()]*?)," % "|".join(klicne), js):
        imena.update(re.findall(r'"([A-Za-z]+)"', m.group(1)))
    imena.update(re.findall(r'\bklic\("([A-Za-z]+)"\)', js))
    imena.update(re.findall(r'\bmetoda = "([A-Za-z]+)"', js))
    return imena


#: Metode delovne povrsine, ki jih namizje QML doseze drugace (ista zmoznost za uporabnika).
NADOMESCENO = {
    "zacniVlecenje": "vlecenje Qt (Drag.Automatic, samo text/uri-list) - zacniVlecenje potrebuje okno GTK",
    "spusceneDatoteke": "spust Qt (DropArea, drop.urls -> Most.datotekaPot) - WebKitGTK poti ne pove, Qt jih",
    "programi": "programiNamizja (isti seznam, ikone kot URL)",
    "napraveZDatotekami": "napraveNamizja (ena vrstica na napravo)",
    "napraveSProgrami": "napraveNamizja",
    "programiNaprave": "programiNapraveNamizja (izbira naprave v plosci Programi)",
    "nadaljujTukaj": "prenesiDatotekoNaprave -> safeer_os.nadaljuj_tukaj (isti prenos razlik in Teamwork)",
    "nastavitveOzadja": "Prilagodi namizje (ozadja) in »Sistemska ozadja …« (sistemskeNastavitve backgrounds)",
    "priljubljenoPreseli": "QML nima localStorage: enkratni prenos starih priljubljenih potrebuje samo delovna povrsina",
}
#: Metode, ki jih namizje QML (se) nima - zavestno, z razlogom.
NI_PRENESENO = {
    "mediaKatalog": "iskanje radia in kataloga v pripomocku Medijski center (QML ima samo »Odpri Medijski center«)",
    "mediaTokovi": "isto (izbira toka zadetka iz kataloga v pripomocku)",
}


class Pokritost(unittest.TestCase):
    def test_vse_metode_qml_imajo_pot_v_safeer_os(self):
        # core/lupina_proces.py: lupina v svojem procesu streze sama varuhZnova (gumb »Zazeni znova«) in zazeni brez OS.
        vir = _beri("safeer_os.py") + _beri("core", "os_lupina.py") + _beri("core", "os_katalog.py") + \
            _beri("core", "lupina_proces.py")
        manjka = sorted(m for m in _metode(_vsi_qml()) if '"%s"' % m not in vir)
        self.assertEqual(manjka, [], "QML klice metode, ki je most ne pozna")

    def test_vsaka_metoda_delovne_povrsine_je_v_qml_ali_odlocena(self):
        webkit = _metode(_beri("assets", "os", "delovna.js"))
        qml = _metode(_vsi_qml())
        brez = sorted(webkit - qml - set(NADOMESCENO) - set(NI_PRENESENO))
        self.assertEqual(brez, [], "metoda delovne povrsine brez QML in brez odlocitve")
        # Nadomescene res niso vec potrebne; seznam ne sme zastarati.
        self.assertFalse(set(NADOMESCENO) & qml, "metoda je ze v QML - odstrani jo iz NADOMESCENO")
        self.assertFalse(set(NI_PRENESENO) & qml, "metoda je ze v QML - odstrani jo iz NI_PRENESENO")

    def test_prej_manjkajoce_so_v_qml(self):
        qml = _metode(_vsi_qml())
        for m in ("najvecjeDatoteke", "prostorDiska", "lastnostiDatoteke", "novaDatoteka", "predlogeDatotek", "razveljaviDatoteke",
                  "prilepiDatoteke", "izvrziNosilec", "sliciceDatotek", "programiZaOdpiranje", "izberiMapo", "shraniNaNapravo",
                  "shrambaStanje", "shrambaIzbrisi", "shrambaObdrzi", "pretvoriVideo", "pretvorbaStanje", "pretvorbaPrenesi",
                  "pretvorbaPusti", "pretvoriVec", "pretvorbaSkupina", "pretvorbaPrenesiSkupino", "pretvorbaPustiSkupino",
                  "predvajajZNaprave", "odpriLokalniMedij", "napraveZaMedij", "odpriMedijNa", "zapiskiSeznam", "knjiznicaMedijev",
                  "mediaIsciPredpomnilnik", "mediaPredvajaj", "isciDatoteke", "govorStanje", "govorNamesti", "govorPoslusaj",
                  "govorUstavi", "govorPreklici", "govorPrekliciNamestitev", "odpriVBrskalniku", "iskanjeSplet", "splet",
                  "dockRazvrsti", "nastavitveDocka", "igreOblak", "igreOblakNamesti", "ponudnikiProgramov", "ponudnikPodrobnosti",
                  "ponudnikNamesti", "ponudnikOdpri", "viriProgramov", "virPodrobnosti", "dodajVir", "githubIsci", "githubIzdaje",
                  "githubShrani", "githubStanje", "povezava", "videzCinnamonNastavi", "sistemskeNastavitve", "privzetiBrskalnik",
                  "preimenujDatoteko"):
            self.assertIn(m, qml, m)

    def test_besedila_v_vseh_jezikih(self):
        q = _vsi_qml()
        kljuci = set(re.findall(r'koren\.t\("([A-Za-z0-9_]+)"', q))
        for k in sorted(kljuci):
            if k.startswith(("sk_", "ppIme_", "ppOpis_", "ppKorak_", "ppZvrst_", "oblakRazlog_", "oblakNapaka_", "nadaljujNapaka_",
                             "prilepiNapaka_", "en_")):
                continue
            n = stevilo(k) or stevilo("qml_" + k)
            self.assertEqual(n, 6, k)
        self.assertEqual(stevilo("novo"), 6)


class PotSkoziSafeerOs(unittest.TestCase):
    """Klic iz lupine QML (pogled z qml_odgovor) gre skozi SafeerOS._obdelaj_klic do istih funkcij kot klic strani."""

    def _klic(self, metoda, a):
        import safeer_os as so
        odgovori = []
        dogodek = threading.Event()

        class Pogled:
            def qml_odgovor(self, i, ok, podatki):
                odgovori.append((i, ok, podatki))
                dogodek.set()

        jaz = mock.MagicMock()
        jaz._katalog_most.return_value.pozna.return_value = False
        jaz.SPREMINJAJO_DATOTEKE = so.SafeerOS.SPREMINJAJO_DATOTEKE
        jaz._odgovori = lambda p, i, ok, d: so.SafeerOS._odgovori(jaz, p, i, ok, d)
        so.SafeerOS._obdelaj_klic(jaz, Pogled(), 7, metoda, a)
        self.assertTrue(dogodek.wait(5), metoda)
        return odgovori[0]

    def test_datoteke(self):
        import safeer_os as so
        dat = mock.MagicMock()
        dat.najvecje.return_value = [{"ime": "velik.iso"}]
        dat.prostor.return_value = {"malo": True}
        dat.lastnosti.return_value = {"ok": True, "ime": "a.txt"}
        dat.razveljavi.return_value = {"ok": True, "narejeno": 1}
        dat.izvrzi.return_value = {"ok": True}
        dat.ustvari_datoteko.return_value = {"ok": True, "pot": "/tmp/x.odt"}
        dat.prilepi.return_value = {"ok": True, "narejeno": ["/tmp/b"]}
        with mock.patch.object(so, "os_datoteke", dat), mock.patch.object(so, "os_iskalnik", mock.MagicMock()):
            self.assertEqual(self._klic("najvecjeDatoteke", []), (7, True, [{"ime": "velik.iso"}]))
            self.assertEqual(self._klic("prostorDiska", [])[2], {"malo": True})
            self.assertEqual(self._klic("lastnostiDatoteke", ["/tmp/a.txt"])[2]["ime"], "a.txt")
            dat.lastnosti.assert_called_with("/tmp/a.txt")
            zapis = {"vrsta": "novo", "pari": [["", "/tmp/x.odt"]]}
            self.assertTrue(self._klic("razveljaviDatoteke", [zapis])[2]["ok"])
            dat.razveljavi.assert_called_with(zapis)
            self._klic("izvrziNosilec", ["/media/u/USB"])
            dat.izvrzi.assert_called_with("/media/u/USB")
            self._klic("novaDatoteka", ["/tmp", "Porocilo", "dokument", ""])
            dat.ustvari_datoteko.assert_called_with("/tmp", "Porocilo", "dokument", "")
            self._klic("prilepiDatoteke", [["/tmp/a"], "/tmp/c", True])
            dat.prilepi.assert_called_with(["/tmp/a"], "/tmp/c", True)

    def test_naprave_mediji_programi(self):
        import safeer_os as so
        control = mock.MagicMock(return_value={"ok": True})
        ponudniki = mock.MagicMock()
        ponudniki.stanje.return_value = [{"id": "bazaar"}]
        with mock.patch.object(so, "_control_naprave", control), mock.patch.object(so, "os_ponudniki_programov", ponudniki):
            self.assertTrue(self._klic("odpriMedijNa", ["tv1", json.dumps({"title": "Film"})])[2]["ok"])
            control.assert_called_with("Ukaz", "tv1", "media.open", json.dumps({"title": "Film"}))
            self._klic("shraniNaNapravo", ["/tmp/velik.iso"])
            control.assert_called_with("ShrambaZacni", "/tmp/velik.iso")
            self._klic("pretvoriVideo", ["/tmp/v.mkv"])
            control.assert_called_with("PretvorbaZacni", "/tmp/v.mkv")
            self.assertEqual(self._klic("ponudnikiProgramov", [])[2], [{"id": "bazaar"}])
        dock = mock.MagicMock()
        dock.razvrsti.return_value = {"ok": True}
        with mock.patch.object(so, "os_dock", dock):
            self.assertEqual(self._klic("dockRazvrsti", [["b.dockitem", "a.dockitem"]])[2], {"ok": True})
            dock.razvrsti.assert_called_with(["b.dockitem", "a.dockitem"])


class NamizjeQml(unittest.TestCase):
    """Namizje QML (offscreen) z laznim SafeerOS, ki si zapomni klice in vrne pripravljene odgovore."""

    DOM = "/home/uporabnik"

    @classmethod
    def setUpClass(cls):
        try:
            import PySide6  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("PySide6 ni namescen")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["test"])

    def setUp(self):
        D = self.DOM
        self.odgovori = {
            "nosilci": [{"ime": "USB", "pot": "/media/u/USB", "naprava": "/dev/sdb1", "velikost": 32e9, "prosto": 2e9, "odstranljiv": True}],
            "prostorDiska": {"skupaj": 256e9, "prosto": 3e9, "malo": True},
            # Naprava v Linku, ki shrani in pretvori (sicer »Shrani na napravo« ni v meniju).
            "pretvorbaZaTvMozna": {"ok": True, "shramba": True, "naprave": 1},
            "predlogeDatotek": [{"ime": "Racun", "pot": D + "/Predloge/Racun.ods"}],
            "mapa": {"pot": D + "/Dokumenti", "stars": D, "elementi": [
                {"ime": "Projekti", "pot": D + "/Dokumenti/Projekti", "mapa": True, "vrsta": "mapa"},
                {"ime": "a.odt", "pot": D + "/Dokumenti/a.odt", "mapa": False, "vrsta": "dokument", "velikost": 10},
                {"ime": "pesem.mp3", "pot": D + "/Dokumenti/pesem.mp3", "mapa": False, "vrsta": "zvok", "velikost": 10},
                {"ime": "film.mkv", "pot": D + "/Dokumenti/film.mkv", "mapa": False, "vrsta": "video", "velikost": 10}]},
            "najvecjeDatoteke": [{"ime": "velik.iso", "pot": D + "/velik.iso", "vrsta": "arhiv", "velikost": 4e9}],
            "lastnostiDatoteke": {"ok": True, "ime": "a.odt", "pot": D + "/Dokumenti/a.odt", "mapa": False, "vrsta": "dokument",
                                  "velikost": 10, "spremenjeno": 1760000000, "pravice": "rw-r--r--", "lastnik": "u"},
            "novaDatoteka": {"ok": True, "pot": D + "/Dokumenti/Nov dokument.odt"},
            "razveljaviDatoteke": {"ok": True, "narejeno": 1, "napake": []},
            "prilepiDatoteke": {"ok": True, "narejeno": [D + "/Dokumenti/b.txt"], "napake": [], "pari": [["/tmp/b.txt", D + "/Dokumenti/b.txt"]]},
            "izvrziNosilec": {"ok": True},
            "odpriLokalniMedij": True,
            "datotekeNaprave": {"ok": True, "shared": True, "server": {"base_url": "https://10.0.0.2:1"}, "kljuc": "k1",
                                "items": [{"id": "s:1", "name": "Pesem.mp3", "type": "audio"}, {"id": "s:2", "name": "Dok.odt", "type": "file"}]},
            "predvajajZNaprave": True,
            "prenesiDatotekoNaprave": {"ok": True, "delta": True, "preneseno": 100, "velikost": 1000, "iz_lokalnih": 900, "odprto": True},
            "programiNamizja": [{"id": "gimp.desktop", "ime": "GIMP", "skupina": "ustvarjanje"},
                                {"id": "nastavitve-zaslon.desktop", "ime": "Zaslon", "skupina": "sistem", "nastavitev": True}],
            "napraveNamizja": [{"kljuc": "tv1", "ime": "Televizor", "platforma": "tv", "programi": "tv1", "datoteke": "tv1"}],
            "dock": {"plank": True, "programi": [{"id": "a.desktop", "ime": "A", "dockitem": "a.dockitem"},
                                                 {"id": "b.desktop", "ime": "B", "dockitem": "b.dockitem"}]},
            "dockRazvrsti": {"ok": True},
            "igreOblak": [{"id": "gfn", "ime": "GeForce NOW", "ponudnik": "NVIDIA", "namescen": False, "stran": "https://example.org",
                           "zdruzljivost": {"stanje": "zdruzljivo"}}],
            "igreOblakNamesti": {"ok": True},
            "ponudnikiProgramov": [{"id": "bazaar", "ime": "Bazaar", "vrsta": "flatpak", "namescen": False, "namestljiv": True}],
            "ponudnikPodrobnosti": {"ok": True, "vrsta": "flatpak", "prenos_mb": 12, "paketi": [{"ime": "io.github.kolunmi.Bazaar"}]},
            "ponudnikNamesti": {"ok": True},
            "zapiskiSeznam": [{"id": "z1", "naslov": "Nakupi", "odlomek": "mleko"}],
            "knjiznicaMedijev": [{"pot": D + "/Glasba/Reka.mp3", "naslov": "Reka", "vrsta": "glasba"}],
            "mediaIsciPredpomnilnik": [],
            "isciDatoteke": [],
            "napraveZaMedij": [{"id": "tv1", "ime": "Televizor", "platforma": "tv"}],
            "odpriMedijNa": {"ok": True},
            "govorStanje": {"podprto": True, "namesceno": False, "prenos": 48e6},
            "govorNamesti": True,
            "povezava": {"control": True, "stanje": "nov"},
            "predvajalnikStanje": {},
        }
        self.klici = []

    def _namizje(self):
        import safeer_os as so
        from core import os_lupina
        test = self

        class Os:
            shramba = {}

            def _zacetek(self):
                return {"jezik": "sl", "platforma": "linux", "mape": [{"vrsta": "HOME", "ime": "Domov", "pot": test.DOM},
                                                                       {"vrsta": "DOWNLOAD", "ime": "Prenosi", "pot": test.DOM + "/Prenosi"}]}

            def _seznam_programov(self):
                return test.odgovori["programiNamizja"]

            def _obdelaj_klic(self, pogled, klic_id, metoda, a):
                test.klici.append((metoda, a))
                pogled.qml_odgovor(klic_id, True, test.odgovori.get(metoda, []))
        prava = os_lupina.Namizje._lastna

        def lastna(n, i, m, a):
            if m == "napraveNamizja":
                n.pogled.qml_odgovor(i, True, test.odgovori[m])
                return True
            return prava(n, i, m, a)
        for z in (mock.patch.object(so, "_jezik", return_value="sl"),
                  mock.patch.object(so, "videz_cinnamon", return_value={"naVoljo": True, "kontrast": False, "tekstOdstotek": 100}),
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
        # Okno QML pospravimo v glavni niti: sicer ga lahko pobere gc.collect() v drugi niti (threat_intel) med
        # kasnejsim preizkusom in proces se sesuje (izmerjeno v skupini gtk4, 15. 10. 2026).
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
        """Izraz v kontekstu Namizje.qml (id-ji koren, datoteke, programi, zadetki …) ali v kontekstu `objekt`."""
        from PySide6.QtQml import QQmlEngine, QQmlExpression
        o = objekt or self.koren
        e = QQmlExpression(QQmlEngine.contextForObject(o), o, koda)
        v = e.evaluate()
        self.assertFalse(e.hasError(), e.error().toString() if e.hasError() else "")
        if isinstance(v, tuple):          # PySide6: (vrednost, ali je undefined)
            v = v[0]
        return v.toVariant() if hasattr(v, "toVariant") else v

    def _obj(self, ime):
        from PySide6.QtCore import QObject
        o = self.koren.findChild(QObject, ime)
        self.assertIsNotNone(o, ime)
        return o

    def _klicano(self, metoda, a=None, cas=3.0):
        return self._pocakaj(lambda: any(m == metoda and (a is None or x == a) for m, x in self.klici), cas)

    # ------------------------------------------------------------------ Datoteke
    def test_najvecje_prostor_in_izvrzi(self):
        self._namizje()
        D = self.DOM
        self.assertTrue(self._pocakaj(lambda: self._obj("opozoriloProstora").property("visible")))
        self._js('datoteke.odpri({ vrsta: "najvecje", pot: "@najvecje" })')
        self.assertTrue(self._klicano("najvecjeDatoteke", []))
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.prikazani.length") == 1))
        self.assertEqual(self._js("datoteke.prikazani[0].pot"), D + "/velik.iso")
        # Pogon v stranski vrstici: meni z »Izvrzi«.
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.nosilci.length") == 1))
        self._js("datoteke.meniPogonaZa(datoteke.nosilci[0])")
        meni = self._obj("meniPogona")
        self.assertTrue(self._pocakaj(lambda: meni.property("visible")))
        self._obj("vnosIzvrzi").triggered.emit()
        self.assertTrue(self._klicano("izvrziNosilec", ["/media/u/USB"]))

    def test_lastnosti_novo_razveljavi(self):
        self._namizje()
        D = self.DOM
        self._js('datoteke.odpriLokalno("%s/Dokumenti")' % D)
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.prikazani.length") == 4))
        self._js("datoteke.meniZa(1)")
        self.assertTrue(self._pocakaj(lambda: self._obj("meniDatoteke").property("visible")))
        self.assertTrue(self._obj("vnosLastnosti").property("visible"))
        self.assertTrue(self._pocakaj(lambda: self._obj("vnosShrani").property("visible")))
        self._obj("vnosLastnosti").triggered.emit()
        self.assertTrue(self._klicano("lastnostiDatoteke", [D + "/Dokumenti/a.odt"]))
        self.assertTrue(self._pocakaj(lambda: self._obj("lastnosti").property("visible")))
        self.assertEqual(self._obj("lastnostiIme").property("text"), "a.odt")
        self._js("datoteke.lastnostiZa('x')")       # drugo odprtje ne podre okna
        # Nova datoteka: ime, vrsta, »Kje«; po potrditvi novaDatoteka in »Razveljavi« (novo -> Smeti).
        self._js('datoteke.novo({ nacin: "datoteka", vrsta: "dokument" })')
        okno = self._obj("oknoNovo")
        self.assertTrue(self._pocakaj(lambda: okno.property("visible")))
        self.assertEqual(self._obj("novoIme").property("text"), "Nov dokument")
        self._obj("novoIme").setProperty("text", "Porocilo")
        self._obj("novoPotrdi").klik.emit()
        self.assertTrue(self._klicano("novaDatoteka", [D + "/Dokumenti", "Porocilo", "dokument", ""]))
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.razveljavitve.length") == 1))
        self._js("datoteke.razveljavi(null)")
        self.assertTrue(self._klicano("razveljaviDatoteke", [{"vrsta": "novo", "pari": [["", D + "/Dokumenti/Nov dokument.odt"]]}]))
        # Predloga iz mape Predloge je med vrstami.
        self.assertIn("predloga:" + D + "/Predloge/Racun.ods", [m["vrednost"] for m in self._js("moznosti", okno)])

    def test_kopiraj_prilepi_in_spust(self):
        self._namizje()
        D = self.DOM
        self._js('datoteke.odpriLokalno("%s/Dokumenti")' % D)
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.prikazani.length") == 4))
        self._js("datoteke.vOdlozisce(datoteke.prikazani[1], false)")
        self._js('datoteke.prilepi("%s/Dokumenti/Projekti")' % D)
        self.assertTrue(self._klicano("prilepiDatoteke", [[D + "/Dokumenti/a.odt"], D + "/Dokumenti/Projekti", False]))
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.razveljavitve.length") == 1))
        self.assertEqual(self._js("datoteke.razveljavitve[0].vrsta"), "kopija")
        # Spust iz drugega programa (Nemo): kopija v odprto mapo; naslov https ni datoteka.
        self.klici.clear()
        ok = self._js('datoteke.spusti({ urls: ["file:///tmp/b.txt", "https://example.org/x"], accept: function () {} }, "%s/Dokumenti")' % D)
        self.assertTrue(ok)
        self.assertTrue(self._klicano("prilepiDatoteke", [["/tmp/b.txt"], D + "/Dokumenti", False]))
        # Vlecenje iz seznama v mapo: premik (brez Ctrl).
        self.klici.clear()
        self._js('datoteke.vlecem = ["%s/Dokumenti/a.odt"]' % D)
        self._js('datoteke.spusti({ urls: [], accept: function () {} }, "%s/Dokumenti/Projekti")' % D)
        self.assertTrue(self._klicano("prilepiDatoteke", [[D + "/Dokumenti/a.odt"], D + "/Dokumenti/Projekti", True]))
        # Spust v mapo, kjer datoteka ze je, ni smiseln.
        self._js('datoteke.vlecem = ["%s/Dokumenti/a.odt"]' % D)
        self.assertFalse(self._js('datoteke.spusti({ urls: [], accept: function () {} }, "%s/Dokumenti")' % D))
        # Vlecenje ven: standardni seznam naslovov datotek.
        self.assertEqual(self.n.most.datotekaPot("file:///tmp/a%20b.txt"), "/tmp/a b.txt")
        self.assertEqual(self.n.most.datotekaPot("https://example.org/a"), "")
        q = _beri("assets", "os", "qml", "Datoteke.qml")
        self.assertIn('Drag.mimeData: ({ "text/uri-list": panel.naslovi(modelData) })', q)
        self.assertEqual(self._js("datoteke.naslovi(datoteke.prikazani[1])"), "file://%s/Dokumenti/a.odt\r\n" % D)
        self.assertIn("Drag.dragType: Drag.Automatic", q)

    def test_mediji_in_datoteke_z_naprave(self):
        self._namizje()
        D = self.DOM
        self._js('datoteke.odpriLokalno("%s/Dokumenti")' % D)
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.prikazani.length") == 4))
        self._js("datoteke.odpriElement(datoteke.prikazani[2])")
        self.assertTrue(self._klicano("odpriLokalniMedij", [D + "/Dokumenti/pesem.mp3"]))
        # Datoteke naprave: glasba se predvaja sproti, dokument se »nadaljuje tukaj«.
        self.assertTrue(self._js('datoteke.pokaziNapravo("tv1")'))
        self.assertTrue(self._klicano("datotekeNaprave", ["tv1", ""]))
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.prikazani.length") == 2))
        self._js("datoteke.odpriElement(datoteke.prikazani[1])")      # Dok.odt, Pesem.mp3 (po abecedi)
        self.assertTrue(self._klicano("predvajajZNaprave"))
        a = [x for m, x in self.klici if m == "predvajajZNaprave"][0]
        self.assertEqual(a[1:], ["k1", [{"id": "s:1", "name": "Pesem.mp3", "type": "audio"}], 0, "Televizor", "tv1"])
        self._js("datoteke.meniZa(0)")
        self.assertTrue(self._pocakaj(lambda: self._obj("vnosNadaljuj").property("visible")))
        self._obj("vnosNadaljuj").triggered.emit()
        self.assertTrue(self._klicano("prenesiDatotekoNaprave", ["tv1", "s:2", "Dok.odt", {"base_url": "https://10.0.0.2:1"}, []]))

    # ------------------------------------------------------------------ Programi
    def test_dock_ponudniki_igre(self):
        self._namizje()
        self._js("programi.urediDock()")
        dock = self._obj("urediDock")
        self.assertTrue(self._pocakaj(lambda: dock.property("visible")))
        self._js("premakni(0, 1)", dock)
        self.assertTrue(self._klicano("dockRazvrsti", [["b.dockitem", "a.dockitem"]]))
        self._js("close()", dock)
        # Igre v oblaku med programi; klik pokaze meni z namestitvijo.
        self.assertTrue(self._pocakaj(lambda: any(p["id"] == "oblak:gfn" for p in self._js("programi.prikazani"))))
        self._js('programi.zazeni(programi.prikazani.filter(function (p) { return p.id === "oblak:gfn" })[0])')
        self.assertTrue(self._pocakaj(lambda: self._obj("meniOblaka").property("visible")))
        self._js("programi.namestiOblak(programi.oblak[0])")
        self.assertTrue(self._klicano("igreOblakNamesti", ["gfn"]))
        # Ponudniki: najprej podrobnosti in potrditev, sele nato namestitev.
        self._js('programi.odpriPonudnike("")')
        pp = self._obj("zavihekPonudniki")         # kontekst PonudnikiProgramov.qml (id-ji ponudniki, viri, github)
        self.assertTrue(self._klicano("ponudnikiProgramov", []))
        self.assertTrue(self._pocakaj(lambda: len(self._js("ponudniki.vsi", pp)) == 1))
        self._js("ponudniki.klik(ponudniki.vsi[0])", pp)
        self.assertTrue(self._klicano("ponudnikPodrobnosti", ["bazaar"]))
        self.assertFalse(any(m == "ponudnikNamesti" for m, _ in self.klici))
        self.assertTrue(self._pocakaj(lambda: bool(self._js("ponudniki.potrditve['bazaar']", pp))))
        self._js("ponudniki.namesti(ponudniki.vsi[0])", pp)
        self.assertTrue(self._klicano("ponudnikNamesti", ["bazaar"]))

    # ------------------------------------------------------------------ iskanje
    def test_iskanje_zapiski_mediji_prikazi_na(self):
        self._namizje()
        self._js('polje.text = "reka na tv"')
        self.assertTrue(self._klicano("napraveZaMedij", []))
        self.assertTrue(self._klicano("zapiskiSeznam", ["reka"]))
        self.assertTrue(self._klicano("knjiznicaMedijev", ["", "reka", 0]))
        self.assertTrue(self._pocakaj(lambda: self._js("zadetki.caka") == 0))
        vrste = [self._js("zadetkiModel.get(%d).vrsta" % i) for i in range(self._js("zadetkiModel.count"))]
        self.assertEqual(vrste[0], "naCilj")
        self.assertIn("medij", vrste)
        self.assertIn("mediji", vrste)
        self.assertEqual(self._js("zadetki.trenutni"), 0)          # »Prikazi na« je privzet
        self._js("zadetki.izberi(0)")
        self.assertTrue(self._klicano("odpriMedijNa", ["tv1", json.dumps({"title": "reka", "kind": "", "year": None}, separators=(",", ":"))]))
        # Zapisek odpre razdelek Zapiski.
        self.odgovori["zapiskiSeznam"] = [{"id": "z1", "naslov": "Nakupi", "odlomek": "mleko"}]
        self._js('polje.text = "nakupi"')
        self.assertTrue(self._pocakaj(lambda: self._js("zadetki.zadnjiNiz") == "nakupi" and self._js("zadetki.caka") == 0))
        i = [self._js("zadetkiModel.get(%d).vrsta" % j) for j in range(self._js("zadetkiModel.count"))].index("zapisek")
        self.assertEqual(self._js("zadetki.trenutni"), i)          # ime zapiska se z nizom zacne: pred spletom
        self._js("zadetki.izberi(%d)" % i)
        self.assertTrue(self._klicano("odpriRazdelek", ["zapisek:z1"]))
        # Nastavitve sistema so svoja skupina.
        self._js('polje.text = "zaslon"')
        self.assertTrue(self._pocakaj(lambda: self._js("zadetki.zadnjiNiz") == "zaslon" and self._js("zadetki.caka") == 0))
        self.assertEqual(self._js("zadetkiModel.get(1).skupina"), "Nastavitve")

    def test_iskanje_z_glasom(self):
        self._namizje()
        self.assertTrue(self._obj("gumbMikrofon").property("visible"))
        self._obj("gumbMikrofon").klik.emit()
        self.assertTrue(self._klicano("govorStanje", []))
        govor = self._obj("govor")
        self.assertTrue(self._pocakaj(lambda: govor.property("plosca") == "ponudba"))
        self.assertEqual(govor.property("mb"), 48)
        self._obj("govorPrenesi").klik.emit()
        self.assertTrue(self._klicano("govorNamesti", []))
        self.n.dogodek("govor", {"vrsta": "namescam", "odstotek": 40})
        self.assertTrue(self._pocakaj(lambda: govor.property("odstotek") == 40))
        self.n.dogodek("govor", {"vrsta": "poslusam"})
        self.assertTrue(self._pocakaj(lambda: govor.property("stanje") == "poslusam"))
        self.n.dogodek("govor", {"vrsta": "besedilo", "besedilo": "gimp"})
        self.assertTrue(self._pocakaj(lambda: self._obj("iskalnoPolje").property("text") == "gimp"))
        self.assertEqual(govor.property("plosca"), "")

    def test_link_in_meni_namizja(self):
        self._namizje()
        self.assertTrue(self._klicano("povezava", []))
        self.assertTrue(self._pocakaj(lambda: self._obj("linkBesedilo").property("text") == "Poveži se v Safeer Link"))
        self._js("koren.linkKlik()")
        self.assertTrue(self._klicano("prijava", []))
        q = _beri("assets", "os", "qml", "Namizje.qml")
        # Brez docka, ki ga Safeer OS ureja (Wayland brez GNOME), vnosa ni (core/os_dock.vrsta_docka, »dock« v zacetek).
        self.assertIn('MeniVnos { text: koren.t("prilagodiDock"); visible: koren.platforma === "linux" && koren.dockNaVoljo; onTriggered: programi.urediDock() }', q)


class Staticno(unittest.TestCase):
    def test_tipkovnica_v_datotekah(self):
        q = _beri("assets", "os", "qml", "Datoteke.qml")
        for niz in ("d.key === Qt.Key_Z", "d.key === Qt.Key_V", "d.key === Qt.Key_C || d.key === Qt.Key_X", "Qt.AltModifier",
                    "d.key === Qt.Key_F2", "Keys.onDeletePressed", "Qt.Key_Menu"):
            self.assertIn(niz, q)
        # Menija in okna v slogu namizja (MeniVnos, Okno) - en vir videza.
        self.assertNotIn("component MeniVnos", q + _beri("assets", "os", "qml", "Programi.qml"))
        self.assertIn("modal: true; focus: true", _beri("assets", "os", "qml", "Okno.qml"))

    def test_brez_trdo_kodiranih_barv_v_novih_datotekah(self):
        for ime in ("Okno.qml", "Meni.qml", "MeniVnos.qml", "MeniCrta.qml", "NovoIme.qml", "Lastnosti.qml", "ShraniNaNapravo.qml",
                    "PretvoriZaTv.qml", "UrediDock.qml", "PonudnikiProgramov.qml", "Predogled.qml", "Programi.qml", "Datoteke.qml"):
            self.assertNotRegex(_beri("assets", "os", "qml", ime), r'"#[0-9a-fA-F]{3,8}"', ime)

    def test_iskanje_js_je_knjiznica_za_qml(self):
        js = _beri("assets", "os", "iskanje.js")
        self.assertIn("var SafeerIskanje = (function (tvornica) {", js)
        self.assertNotIn("koren.SafeerIskanje", js)          # QML ne dovoli pisanja v globalni objekt
        self.assertIn('import "../iskanje.js" as Iskanje', _beri("assets", "os", "qml", "Namizje.qml"))


if __name__ == "__main__":
    unittest.main()

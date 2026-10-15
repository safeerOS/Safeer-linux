"""Namizje QML: priljubljene (Datoteke in Programi), izbira vec datotek z dejanji za vse, predogled datotek ter
razvrscanje in vrstni red programov (lastnik, 15. 10. 2026).

Offscreen z laznim SafeerOS: mape, predogled in priljubljene so PRAVI (core/os_datoteke, core/priljubljeno v zacasni
mapi), dejanja, ki bi spreminjala sistem (Smeti, posiljanje, zagon), so pripravljeni odgovori. Vsak preizkus preveri se,
da QML med delom ni izpisal napake (TypeError, ReferenceError …)."""
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

from core import os_datoteke, priljubljeno


class Osnova(unittest.TestCase):
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
        from PySide6.QtCore import qInstallMessageHandler
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        self.DOM = os.path.join(self.mapa, "dom")
        self.dok = os.path.join(self.DOM, "Dokumenti")
        os.makedirs(os.path.join(self.dok, "Projekti"))
        self.slika = self._slika(os.path.join(self.dok, "jezero.png"))
        with open(os.path.join(self.dok, "beri.txt"), "w", encoding="utf-8") as f:
            f.write("Pozdravljen, svet!\nDruga vrstica čšž\n")
        with open(os.path.join(self.dok, "pesem.mp3"), "wb") as f:
            f.write(b"ID3" + b"\0" * 64)
        self.shramba = priljubljeno.Priljubljeno(os.path.join(self.mapa, "cfg", "priljubljeno.json"))
        self.odgovori = {
            "nosilci": [], "prostorDiska": {"malo": False}, "predlogeDatotek": [], "sliciceDatotek": {},
            "vSmetiVec": {"ok": True, "idji": ["a.1", "b.1"], "narejeno": [], "napake": []},
            "razveljaviDatoteke": {"ok": True, "narejeno": 2, "napake": []},
            "napraveZaPosiljanje": [{"id": "tv1", "ime": "Televizor"}],
            "posljiNapravi": {"ok": True, "stanje": "poslano"},
            "odpriDatoteko": True, "odpriLokalniMedij": True, "zazeni": True,
            "programiNamizja": [
                {"id": "gimp.desktop", "ime": "GIMP", "skupina": "ustvarjanje", "uporaba": 5, "zadnjic": 100},
                {"id": "firefox.desktop", "ime": "Firefox", "skupina": "splet", "uporaba": 1, "zadnjic": 300},
                {"id": "writer.desktop", "ime": "LibreOffice Writer", "skupina": "pisarna", "uporaba": 9, "zadnjic": 200},
                {"id": "zaslon.desktop", "ime": "Zaslon", "skupina": "sistem", "nastavitev": True}],
            "dock": {"plank": False, "programi": []}, "igreOblak": [], "napraveNamizja": [],
            "povezava": {"control": True, "stanje": "povezan"}, "predvajalnikStanje": {}, "lupaUcenje": {"izbire": []},
        }
        self.klici = []
        self.sporocila = []
        qInstallMessageHandler(lambda _v, _k, s: self.sporocila.append(s))
        self.addCleanup(qInstallMessageHandler, None)

    @staticmethod
    def _slika(pot, w=640, h=400):
        from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
        img = QImage(w, h, QImage.Format.Format_RGB32)
        p = QPainter(img)
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor(40, 90, 160))
        g.setColorAt(1, QColor(150, 210, 190))
        p.fillRect(0, 0, w, h, g)
        p.setBrush(QColor(30, 60, 50))
        p.drawEllipse(w // 4, h // 2, w // 2, h // 2)
        p.end()
        img.save(pot)
        return pot

    def _namizje(self, jezik="sl"):
        import safeer_os as so
        from core import os_lupina
        test = self

        class Os:
            shramba = {}

            def _zacetek(self):
                return {"jezik": jezik, "platforma": "linux", "mape": [{"vrsta": "HOME", "ime": "Domov", "pot": test.DOM},
                                                                        {"vrsta": "DOCUMENTS", "ime": "Dokumenti", "pot": test.dok}]}

            def _seznam_programov(self):
                return test.odgovori["programiNamizja"]

            def _obdelaj_klic(self, pogled, klic_id, metoda, a):
                test.klici.append((metoda, a))
                s = test.shramba
                pravi = {
                    "mapa": lambda: os_datoteke.preglej(a[0]),
                    "predogledDatoteke": lambda: os_datoteke.predogled(a[0]),
                    "priljubljenoSeznam": s.stanje,
                    "priljubljenoPreklopi": lambda: s.preklopi(a[0], a[1], a[2] if len(a) > 2 else None),
                    "priljubljenoVrstniRed": lambda: s.vrstni_red(a[0], a[1]),
                    "priljubljenoKategorija": lambda: s.kategorija(a[0], a[1]),
                    "priljubljenoNastavi": lambda: s.nastavi(a[0], a[1]),
                }
                odg = pravi[metoda]() if metoda in pravi else test.odgovori.get(metoda, [])
                pogled.qml_odgovor(klic_id, True, odg)
        prava = os_lupina.Namizje._lastna

        def lastna(n, i, m, a):
            if m == "napraveNamizja":
                n.pogled.qml_odgovor(i, True, [])
                return True
            return prava(n, i, m, a)
        for z in (mock.patch.object(so, "_jezik", return_value=jezik),
                  mock.patch.object(so, "videz_cinnamon", return_value={"naVoljo": True, "kontrast": False, "tekstOdstotek": 100}),
                  mock.patch.object(os_lupina.Namizje, "_lastna", lastna)):
            z.start()
            self.addCleanup(z.stop)
        n = os_lupina.Namizje(Os(), v_oknu=True)
        self.assertEqual(n.okno.errors(), [])
        # Sprememba v shrambi (tudi z delovne povrsine) pride kot dogodek, kot v SafeerOS._priljubljeno.
        self.shramba.ob_spremembi = lambda st: n.dogodek("priljubljeno", st)
        self.n = n
        self.koren = n.okno.rootObject()
        n.okno.resize(1440, 900)
        n.okno.show()
        n.okno.requestActivate()
        self.assertTrue(self._pocakaj(lambda: self.koren.property("platforma") == "linux"))
        self.assertTrue(self._klicano("priljubljenoSeznam", []))
        return n

    def tearDown(self):
        import gc
        # Samo sporocila med preizkusom: po zaprtju okna casovniki namizja ne najdejo vec mostu (Most je null).
        # (»Most … of null« je okno prejsnjega preizkusa, ki ga Qt se ni pospravil.)
        napake = [s for s in self.sporocila if any(x in s for x in ("TypeError", "ReferenceError", "Error:", ".qml:"))
                  and "Cannot read property 'klic' of null" not in s]
        n = getattr(self, "n", None)
        if n is not None:
            n.okno.close()
            n.okno.deleteLater()
        self.n = self.koren = None
        self._pocakaj(lambda: False, 0.1)
        gc.collect()
        self.assertEqual(napake, [], "QML je izpisal napako")

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

    def _tipka(self, tipka, mod=None):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        QTest.keyClick(self.n.okno, tipka, mod or Qt.KeyboardModifier.NoModifier)
        self._pocakaj(lambda: False, 0.05)

    def _klik_vrstice(self, i, mod=None, gumb=None):
        """Klik na i-to vrstico seznama Datotek (z Ctrl/Shift), kot z misko."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        seznam = self._obj("seznamDatotek")
        self._js("positionViewAtIndex(%d, ListView.Contain)" % i, seznam)
        self._pocakaj(lambda: False, 0.05)
        x, y = self._js("(function () { var it = itemAtIndex(%d); var p = it.mapToItem(null, 60, it.height / 2); return [p.x, p.y] })()" % i, seznam)
        QTest.mouseClick(self.n.okno, gumb or Qt.MouseButton.LeftButton, mod or Qt.KeyboardModifier.NoModifier, QPoint(int(x), int(y)))
        self._pocakaj(lambda: False, 0.05)

    def _odpri_dokumente(self):
        self._js('datoteke.odpriLokalno("%s")' % self.dok)
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.prikazani.length") == 4))
        # Projekti (mapa), beri.txt, jezero.png, pesem.mp3
        self.assertEqual([e["ime"] for e in self._js("datoteke.prikazani")], ["Projekti", "beri.txt", "jezero.png", "pesem.mp3"])
        self._obj("seznamDatotek").forceActiveFocus()


class Priljubljeno(Osnova):
    def test_datoteke_dodaj_ctrl_d_nedosegljiva_odstrani(self):
        self._namizje()
        self._odpri_dokumente()
        self._js("datoteke.meniZa(1)")
        self.assertTrue(self._pocakaj(lambda: self._obj("meniDatoteke").property("visible")))
        vnos = self._obj("vnosPriljubljeno")
        self.assertEqual(vnos.property("text"), "Dodaj med priljubljene")
        vnos.triggered.emit()
        txt = os.path.join(self.dok, "beri.txt")
        self.assertTrue(self._pocakaj(lambda: [d["pot"] for d in self.shramba.stanje()["datoteke"]] == [txt]))
        self.assertTrue(self._pocakaj(lambda: self._js("koren.jePriljubljenaPot(%r)" % txt)))
        self._js("datoteke.meniZa(1)")
        self.assertTrue(self._pocakaj(lambda: vnos.property("text") == "Odstrani iz priljubljenih"))
        self._js("meni.close()", self._obj("meniDatoteke"))
        # Ctrl+D na mapi Projekti (tipkovnica).
        from PySide6.QtCore import Qt
        self._klik_vrstice(0)
        self._tipka(Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(self._pocakaj(lambda: len(self.shramba.stanje()["datoteke"]) == 2))
        self.assertTrue(self.shramba.stanje()["datoteke"][1]["mapa"])
        # Stranska vrstica: Priljubljeno. Datoteka v Smeteh se ne pokaze nikjer (brez »ni na voljo«); obnovljena se
        # vrne na isto mesto - Safeer OS po dejanju poslje dogodek (osvezi), seznam se osvezi sam.
        viri = self._js("datoteke.viri")
        self.assertEqual(viri[1]["oznaka"], "Priljubljeno")
        self._js('datoteke.odpri({ vrsta: "priljubljeno", pot: "@priljubljeno" })')
        self.assertTrue(self._pocakaj(lambda: [e["ime"] for e in self._js("datoteke.prikazani")] == ["beri.txt", "Projekti"]))
        smeti = os.path.join(self.mapa, "Smeti")
        os.mkdir(smeti)
        os.rename(txt, os.path.join(smeti, "beri.txt"))
        self.shramba.osvezi()
        self.assertTrue(self._pocakaj(lambda: [e["ime"] for e in self._js("datoteke.prikazani")] == ["Projekti"]))
        self.assertFalse(self._js("koren.jePriljubljenaPot(%r)" % txt))
        os.rename(os.path.join(smeti, "beri.txt"), txt)
        self.shramba.osvezi()
        self.assertTrue(self._pocakaj(lambda: [e["ime"] for e in self._js("datoteke.prikazani")] == ["beri.txt", "Projekti"]))
        # Ob ponovnem odprtju vira Safeer OS vprasa znova (izginilo z drugim programom, odklopljen disk).
        os.rename(txt, os.path.join(smeti, "beri.txt"))
        self._js('datoteke.odpri({ vrsta: "priljubljeno", pot: "@priljubljeno" })')
        self.assertTrue(self._pocakaj(lambda: [e["ime"] for e in self._js("datoteke.prikazani")] == ["Projekti"]))

    def test_programi_priljubljeni_vrstni_red_kategorija_razvrsti_pogled(self):
        from PySide6.QtCore import Qt
        self._namizje()
        self.assertTrue(self._pocakaj(lambda: len(self._js("programi.prikazani")) == 4))
        # Po imenu (privzeto).
        self.assertEqual([p["ime"] for p in self._js("programi.prikazani")], ["Firefox", "GIMP", "LibreOffice Writer", "Zaslon"])
        # Kategorije iz skupnega kataloga (isti kot delovna povrsina): sistem -> Drugo.
        self.assertEqual(self._js("programi.skupine"), ["pisarna", "ustvarjanje", "splet", "drugo"])
        # Priljubljena iz menija; vrstica na vrhu.
        for ime in ("writer.desktop", "gimp.desktop", "firefox.desktop"):
            self._js('programi.meniZa(programi.prikazani.filter(function (p) { return p.id === "%s" })[0], null)' % ime)
            vnos = self._obj("vnosPriljubljenProgram")
            self.assertTrue(self._pocakaj(lambda: self._obj("meniPrograma").property("visible")))
            self.assertEqual(vnos.property("text"), "Dodaj med priljubljene")
            vnos.triggered.emit()
            self.assertTrue(self._pocakaj(lambda: "ta:" + ime in self.shramba.stanje()["programi"]))
        vrsta = self._obj("vrstaPriljubljenih")
        self.assertTrue(self._pocakaj(lambda: vrsta.property("count") == 3 and vrsta.property("visible")))
        # Alt+desno premakne prvega (Writer) za GIMP - zapisano v shrambo.
        vrsta.forceActiveFocus()
        self._js("currentIndex = 0", vrsta)
        self._tipka(Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        self.assertTrue(self._pocakaj(lambda: self.shramba.stanje()["programi"] == ["ta:gimp.desktop", "ta:writer.desktop", "ta:firefox.desktop"]))
        self.assertEqual(vrsta.property("currentIndex"), 1)
        # Vlecenje z misko: Firefox (3.) na prvo mesto.
        self._vleci_v_vrsti(vrsta, 2, 0)
        self.assertTrue(self._pocakaj(lambda: self.shramba.stanje()["programi"][0] == "ta:firefox.desktop"), self.shramba.stanje()["programi"])
        # Kategorija »★ Priljubljeni« kaze isti vrstni red.
        self._js('programi.skupina = "priljubljeni"')
        self.assertEqual([p["id"] for p in self._js("programi.prikazani")], [k[3:] for k in self.shramba.stanje()["programi"]])
        self._js('programi.skupina = ""')
        # Razvrsti: nazadnje uporabljeni (podatki uporabe iz Safeer OS) - zapomnjeno v shrambi.
        self._obj("gumbRazvrsti").klik.emit()
        self.assertTrue(self._pocakaj(lambda: self._obj("meniRazvrsti").property("visible")))
        self._obj("vnosRazvrstiNazadnje").triggered.emit()
        self.assertTrue(self._pocakaj(lambda: self.shramba.stanje()["nastavitve"]["programiRazvrsti"] == "nazadnje"))
        self.assertTrue(self._pocakaj(lambda: [p["ime"] for p in self._js("programi.prikazani")][:3] == ["Firefox", "LibreOffice Writer", "GIMP"]))
        self.assertIn("Nazadnje uporabljeni", self._obj("gumbRazvrsti").property("besedilo"))
        self._js('programi.nastaviRazvrsti("najveckrat")')
        self.assertTrue(self._pocakaj(lambda: [p["ime"] for p in self._js("programi.prikazani")][:3] == ["LibreOffice Writer", "GIMP", "Firefox"]))
        # Zagon (uspel) premakne program na vrh pri »nazadnje«.
        self._js('programi.nastaviRazvrsti("nazadnje")')
        self.assertTrue(self._pocakaj(lambda: self._js("programi.razvrsti") == "nazadnje"))
        self._js('programi.zazeni(programi.prikazani.filter(function (p) { return p.id === "gimp.desktop" })[0])')
        self.assertTrue(self._klicano("zazeni", ["gimp.desktop"]))
        self.assertTrue(self._pocakaj(lambda: self._js("programi.prikazani[0].id") == "gimp.desktop"))
        # Pogled seznam/mreza (zapomnjen).
        mreza = self._obj("mrezaProgramov")
        visina_mreze = mreza.property("cellHeight")
        self._obj("gumbPogled").klik.emit()
        self.assertTrue(self._pocakaj(lambda: self.shramba.stanje()["nastavitve"]["programiPogled"] == "seznam"))
        self.assertTrue(self._pocakaj(lambda: mreza.property("cellHeight") < visina_mreze))
        self.assertEqual(self._js("mreza.stolpcev", mreza), 1)
        # Prestavi v drugo kategorijo (podmeni): GIMP -> Mediji.
        gimp = 'programi.prikazani.filter(function (p) { return p.id === "gimp.desktop" })[0]'
        self._js("programi.meniZa(%s, null)" % gimp)
        self.assertTrue(self._pocakaj(lambda: self._obj("meniPrograma").property("visible")))
        pod = self._obj("podmeniKategorija")
        self.assertEqual(pod.property("title"), "Kategorija: Ustvarjanje")
        self.assertEqual(self._js("count", pod), 6)
        self._js("itemAt(2).triggered()", pod)                     # pisarna, ustvarjanje, mediji, …
        self.assertTrue(self._pocakaj(lambda: self.shramba.stanje()["kategorije"] == {"ta:gimp.desktop": "mediji"}))
        self.assertTrue(self._pocakaj(lambda: self._js("programi.kategorijaP(%s)" % gimp) == "mediji"))
        self.assertIn("mediji", self._js("programi.skupine"))
        # Odstranjen program se ne pokaze (ne v vrstici, ne v kategoriji Priljubljeni); ob namestitvi se vrne.
        vsi = list(self.odgovori["programiNamizja"])
        self.odgovori["programiNamizja"] = [p for p in vsi if p["id"] != "firefox.desktop"]
        self._js("programi.nalozi()")
        self.assertTrue(self._pocakaj(lambda: vrsta.property("count") == 2))
        self.assertNotIn("Firefox", [p["ime"] for p in self._js("programi.priljubljeni")])
        self.assertIn("ta:firefox.desktop", self.shramba.stanje()["programi"])      # zapis ostane
        self.odgovori["programiNamizja"] = vsi
        self._js("programi.nalozi()")
        self.assertTrue(self._pocakaj(lambda: vrsta.property("count") == 3))
        self.assertEqual(self._js("programi.priljubljeni[0].id"), "firefox.desktop")    # na svojem mestu
        # Ctrl+D v mrezi odstrani priljubljenega.
        mreza.forceActiveFocus()
        i = [p["id"] for p in self._js("programi.prikazani")].index("gimp.desktop")
        self._js("currentIndex = %d" % i, mreza)
        self._tipka(Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(self._pocakaj(lambda: "ta:gimp.desktop" not in self.shramba.stanje()["programi"]))

    def _vleci_v_vrsti(self, vrsta, od, kam):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        okno = self.n.okno

        def tocka(i):
            x, y = self._js("(function () { var it = itemAtIndex(%d); var p = it.mapToItem(null, it.width / 2, it.height / 2); return [p.x, p.y] })()" % i, vrsta)
            return QPoint(int(x), int(y))
        a, b = tocka(od), tocka(kam)
        QTest.mousePress(okno, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
        for k in range(1, 13):
            QTest.mouseMove(okno, QPoint(a.x() + (b.x() - a.x()) * k // 12, a.y()))
            self._pocakaj(lambda: False, 0.03)
        QTest.mouseRelease(okno, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(b.x(), a.y()))
        self._pocakaj(lambda: False, 0.1)


class Izbira(Osnova):
    def test_izbira_misko_tipke_meni_smeti_razveljavi_vlecenje(self):
        from PySide6.QtCore import Qt
        self._namizje()
        self._odpri_dokumente()
        txt, png, mp3 = (os.path.join(self.dok, x) for x in ("beri.txt", "jezero.png", "pesem.mp3"))
        self._klik_vrstice(1)
        self._klik_vrstice(3, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self._js("datoteke.steviloIzbranih"), 3)
        self.assertEqual(self._obj("steviloIzbranih").property("text"), "Izbrano: 3")
        self.assertTrue(self._obj("steviloIzbranih").property("visible"))
        self._klik_vrstice(2, Qt.KeyboardModifier.ControlModifier)        # Ctrl+klik odvzame
        self.assertEqual(sorted(e["pot"] for e in self._js("datoteke.izbraniVnosi()")), [txt, mp3])
        # Vlecenje izbrane vrstice nese vse izbrane (text/uri-list).
        nasl = self._js("datoteke.naslovi(datoteke.prikazani[1])")
        self.assertEqual(nasl, "file://%s\r\nfile://%s\r\n" % (txt, mp3))
        self.assertEqual(self._js("datoteke.potiZaVlecenje(datoteke.prikazani[2])"), [png])     # neizbrana: samo ta
        # Tipkovnica: Ctrl+A vse, Escape eno, Shift+puscica gor obseg.
        self._tipka(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self._js("datoteke.steviloIzbranih"), 4)
        self._tipka(Qt.Key.Key_Escape)
        self.assertEqual(self._js("datoteke.steviloIzbranih"), 1)
        self._tipka(Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
        self._tipka(Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self._js("datoteke.steviloIzbranih"), 3)
        self._tipka(Qt.Key.Key_Down)
        self.assertEqual(self._js("datoteke.steviloIzbranih"), 1)
        # Desni klik na izbrano: meni za vse izbrane.
        self._klik_vrstice(1)
        self._klik_vrstice(3, Qt.KeyboardModifier.ShiftModifier)
        self._klik_vrstice(2, Qt.KeyboardModifier.NoModifier, Qt.MouseButton.RightButton)
        meni = self._obj("meniVec")
        self.assertTrue(self._pocakaj(lambda: meni.property("visible")))
        self.assertEqual(self._js("count", meni) >= 8, True)
        self.assertTrue(self._pocakaj(lambda: self._obj("vnosPosljiVec").property("visible")))
        self.assertFalse(self._obj("vnosPretvoriTvVec").property("visible"))       # ne samo videi
        self.assertFalse(self._obj("vnosPretvoriVec").property("visible"))         # ni skupne oblike: vnosa ni
        self._obj("vnosKopirajVec").triggered.emit()
        self.assertEqual(self._js("datoteke.odlozisce.poti"), [txt, png, mp3])
        # Poslji na napravo: vse naenkrat.
        self._js("close()", meni)
        self._js("datoteke.meniVrstice(datoteke.prikazani[1], null)")
        self.assertTrue(self._pocakaj(lambda: meni.property("visible")))
        self._obj("vnosPosljiVec").triggered.emit()
        self.assertTrue(self._klicano("napraveZaPosiljanje", []))
        self.assertTrue(self._pocakaj(lambda: len(self._js("moznosti", self._izbirnik())) == 1))
        self._js("moznosti[0].ob()", self._izbirnik())
        self.assertTrue(self._klicano("posljiNapravi", ["tv1", [txt, png, mp3]]))
        # Delete: vse izbrane v Smeti z enim klicem; Ctrl+Z razveljavi vse naenkrat.
        self._klik_vrstice(1)
        self._klik_vrstice(3, Qt.KeyboardModifier.ShiftModifier)
        self.odgovori["vSmetiVec"]["narejeno"] = [txt, png, mp3]
        self._tipka(Qt.Key.Key_Delete)
        self.assertTrue(self._klicano("vSmetiVec", [[txt, png, mp3]]))
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.razveljavitve.length") == 1))
        self.assertEqual(self._js("datoteke.razveljavitve[0]"), {"vrsta": "smeti", "idji": ["a.1", "b.1"]})
        self._obj("seznamDatotek").forceActiveFocus()
        self._tipka(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(self._klicano("razveljaviDatoteke", [{"vrsta": "smeti", "idji": ["a.1", "b.1"]}]))

    def _izbirnik(self):
        from PySide6.QtCore import QObject
        for o in self.koren.findChildren(QObject):
            if o.property("naslov") is not None and o.property("moznosti") is not None:
                return o
        self.fail("izbirnik")

    def test_brez_mrtvih_vnosov(self):
        """Brez naprave ni »Poslji na napravo«, brez pretvorbe ni »Pretvori v …«; ko gre, sta tam (15. 10. 2026)."""
        self._namizje()
        self._odpri_dokumente()
        self.odgovori["napraveZaPosiljanje"] = []
        self._js("datoteke.meniZa(1)")
        self.assertTrue(self._pocakaj(lambda: self._obj("meniDatoteke").property("visible")))
        self.assertTrue(self._klicano("pretvorbaMoznosti", [os.path.join(self.dok, "beri.txt")]))
        self.assertFalse(self._obj("vnosPoslji").property("visible"))
        self.assertFalse(self._obj("vnosPretvori").property("visible"))
        self._js("close()", self._obj("meniDatoteke"))
        self.odgovori["napraveZaPosiljanje"] = [{"id": "tv1", "ime": "Televizor"}]
        self.odgovori["pretvorbaMoznosti"] = {"skupina": "besedilo", "cilji": ["pdf", "odt"], "orodje": True}
        self._js("datoteke.meniZa(1)")
        self.assertTrue(self._pocakaj(lambda: self._obj("vnosPretvori").property("visible")))
        self.assertTrue(self._obj("vnosPoslji").property("visible"))
        self._js("close()", self._obj("meniDatoteke"))
        # Orodja ni (npr. LibreOffice): vnosa ni.
        self.odgovori["pretvorbaMoznosti"] = {"skupina": "besedilo", "cilji": ["pdf"], "orodje": False}
        self._js("datoteke.meniZa(1)")
        self.assertTrue(self._pocakaj(lambda: self._obj("meniDatoteke").property("visible")))
        self._pocakaj(lambda: False, 0.2)
        self.assertFalse(self._obj("vnosPretvori").property("visible"))

    def test_pretvori_vec_skupne_oblike(self):
        self._namizje()
        self._odpri_dokumente()
        moznosti = {"a": {"skupina": "slika", "cilji": ["jpg", "webp", "bmp"], "orodje": True},
                    "b": {"skupina": "slika", "cilji": ["png", "webp", "bmp"], "orodje": True}}
        izhodi = iter(["a", "b"])
        prej = self.odgovori.get

        class Odgovori(dict):
            def get(self, k, d=None):
                if k == "pretvorbaMoznosti":
                    return moznosti[next(izhodi)]
                if k == "pretvoriDatoteko":
                    return {"ok": True, "id": "p1"}
                if k == "pretvorbaDatotekeStanje":
                    return {"ok": True, "stanje": "dela"}
                return prej(k, d)
        self.odgovori = Odgovori(self.odgovori)
        self._js("datoteke.izberiVse()")
        izbirnik = self._izbirnik()
        self._js("izbirnik.pretvoriVec([datoteke.prikazani[1], datoteke.prikazani[2]])", self._obj("seznamDatotek"))
        self.assertTrue(self._pocakaj(lambda: [m["ime"] for m in self._js("moznosti", izbirnik)] == ["WEBP", "BMP"]))
        self._js("moznosti[0].ob()", izbirnik)
        self.assertTrue(self._pocakaj(lambda: len([1 for m, _ in self.klici if m == "pretvoriDatoteko"]) == 2))


class Predogled(Osnova):
    def test_slika_besedilo_puscice_enter_escape(self):
        from PySide6.QtCore import Qt
        self._namizje()
        self._odpri_dokumente()
        self._klik_vrstice(2)                                     # jezero.png
        self._tipka(Qt.Key.Key_Space)
        p = self._obj("predogled")
        self.assertTrue(self._pocakaj(lambda: p.property("visible")))
        self.assertTrue(self._pocakaj(lambda: p.property("nacin") == "slika"))
        slika = self._obj("predogledSlika")
        self.assertTrue(self._pocakaj(lambda: self._js("status === Image.Ready && sourceSize.width > 0", slika)))
        self.assertEqual(self._obj("predogledIme").property("text"), "jezero.png")
        # Levo: prejsnja datoteka (beri.txt) - besedilo iz Safeer OS, monospace.
        self._tipka(Qt.Key.Key_Left)
        self.assertTrue(self._pocakaj(lambda: p.property("nacin") == "besedilo"))
        self.assertIn("Druga vrstica čšž", self._obj("predogledTekst").property("text"))
        self.assertFalse(self._obj("predogledOdrezano").property("visible"))
        self.assertTrue(self._klicano("predogledDatoteke", [os.path.join(self.dok, "beri.txt")]))
        # Desno dvakrat: glasba - »Predvajaj«.
        self._tipka(Qt.Key.Key_Right)
        self._tipka(Qt.Key.Key_Right)
        self.assertTrue(self._pocakaj(lambda: p.property("nacin") == "medij"))
        self.assertTrue(self._obj("predogledPredvajaj").property("visible"))
        self._tipka(Qt.Key.Key_Return)                           # Enter: kot dvojni klik (Medijski center)
        self.assertTrue(self._klicano("odpriLokalniMedij", [os.path.join(self.dok, "pesem.mp3")]))
        self.assertTrue(self._pocakaj(lambda: not p.property("visible")))
        # Preslednica zapre; Escape tudi.
        self._obj("seznamDatotek").forceActiveFocus()
        self._tipka(Qt.Key.Key_Space)
        self.assertTrue(self._pocakaj(lambda: p.property("visible")))
        self._tipka(Qt.Key.Key_Space)
        self.assertTrue(self._pocakaj(lambda: not p.property("visible")))
        self._obj("seznamDatotek").forceActiveFocus()
        self._tipka(Qt.Key.Key_Space)
        self.assertTrue(self._pocakaj(lambda: p.property("visible")))
        self._tipka(Qt.Key.Key_Escape)
        self.assertTrue(self._pocakaj(lambda: not p.property("visible")))

    def test_velika_in_binarna(self):
        from PySide6.QtCore import Qt
        with open(os.path.join(self.dok, "dnevnik.log"), "w", encoding="utf-8") as f:
            f.write("vrstica dnevnika\n" * 30000)
        with open(os.path.join(self.dok, "program"), "wb") as f:
            f.write(b"\x7fELF\0\0" * 50)
        self._namizje()
        self._js('datoteke.odpriLokalno("%s")' % self.dok)
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.prikazani.length") == 6))
        imena = [e["ime"] for e in self._js("datoteke.prikazani")]
        self._obj("seznamDatotek").forceActiveFocus()
        self._klik_vrstice(imena.index("dnevnik.log"))
        self._tipka(Qt.Key.Key_Space)
        p = self._obj("predogled")
        self.assertTrue(self._pocakaj(lambda: p.property("nacin") == "besedilo"))
        self.assertTrue(self._obj("predogledOdrezano").property("visible"))
        self.assertIn("200 KB", self._obj("predogledOdrezano").property("text"))
        self.assertEqual(len(self._obj("predogledTekst").property("text").encode()), os_datoteke.MEJA_BESEDILA)
        self._js("premakni(%d)" % (imena.index("program") - imena.index("dnevnik.log")), p)
        self.assertTrue(self._pocakaj(lambda: p.property("nacin") == "podatki"))
        self.assertEqual(self._obj("predogledRazlog").property("text"), "Ta datoteka ni besedilo, zato je ni mogoče pokazati.")
        self._tipka(Qt.Key.Key_Return)                           # Odpri s privzetim programom
        self.assertTrue(self._klicano("odpriDatoteko", [os.path.join(self.dok, "program")]))


if __name__ == "__main__":
    unittest.main()

"""Sporocila v Safeer OS (safeer_os.py): vklop Sporocil v celoti (Nastavitve, Prilagodi namizje), most vgrajenih
kanalov, prekrivanje okna za kanale, znacka na namizju steje tudi vgrajene kanale (lastnik, 15. 10. 2026)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*pot):
    with open(os.path.join(KOREN, *pot), encoding="utf-8") as d:
        return d.read()


class _Kanali:
    def __init__(self):
        self.ustavljeni = False
        self.zagnani = 0

    def ustavi_vse(self):
        self.ustavljeni = True

    def zazeni_vse(self):
        self.zagnani += 1

    def zasciteni(self):
        return set()

    def neprebrano_skupaj(self):
        return 7


class _Sporocila:
    def __init__(self):
        self.klici = []

    def ustavi(self):
        self.klici.append("ustavi")

    def nadaljuj(self):
        self.klici.append("nadaljuj")


class _Okno:
    def __init__(self):
        self.vidno = True

    def set_visible(self, v):
        self.vidno = v


class _Kuverta:
    def __init__(self):
        self.zaprta = False

    def zapri(self):
        self.zaprta = True


class _Os:
    def __init__(self):
        self.sporocila = _Sporocila()
        self._kanali_sporocil = _Kanali()
        self._kuverta = _Kuverta()
        self.okna_razdelkov = {"sporocila": (_Okno(), None)}
        self.lupina = None
        self.posnetek = ""
        self._spletni = None
        self._spletni_namizje = None
        self.dogodki = []
        self.plosca_skrita = 0
        self.kuverta_zacni = 0
        self.okno = None
        self.okno_delovna = object()

    def _dogodek(self, vrsta, podatki, pogled=None):
        self.dogodki.append((vrsta, podatki))

    def _skrij_plosco_sporocil(self):
        self.plosca_skrita += 1

    def _zacni_kuverto(self):
        self.kuverta_zacni += 1

    def _kanali(self):
        return self._kanali_sporocil

    def _zacni_kanale(self):
        import safeer_os
        return safeer_os.SafeerOS._zacni_kanale(self)

    def _odpri_okno_razdelka(self, ime, cilj=""):
        self.dogodki.append(("okno", ime))
        return True

    def _uskladi_vklop_sporocil(self, vklop):
        import safeer_os
        import threading
        self.niti_uskladitve = getattr(self, "niti_uskladitve", []) + [threading.current_thread() is threading.main_thread()]
        return safeer_os.SafeerOS._uskladi_vklop_sporocil(self, vklop)


class VklopSporocil(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.so = safeer_os
        self.mapa = Path(tempfile.mkdtemp())
        p = mock.patch.object(safeer_os.sporocila_vklop, "PRIVZETA_POT", self.mapa / "sporocila.sqlite3")
        p.start()
        self.addCleanup(p.stop)

    def test_izklop_ustavi_vse_in_vklop_vrne_brez_zagona(self):
        o = _Os()
        kuverta = o._kuverta
        self.assertFalse(self.so.SafeerOS._nastavi_sporocila(o, False))
        self.assertEqual(o.sporocila.klici, ["ustavi"], "storitev (posta, Telegram, Matrix) ne tece")
        self.assertTrue(o._kanali_sporocil.ustavljeni, "vgrajeni kanali so sproscini")
        self.assertTrue(kuverta.zaprta and o._kuverta is None, "kuverte v pultu ni (brez mrtve ikone)")
        self.assertFalse(o.okna_razdelkov["sporocila"][0].vidno)
        self.assertIn(("sporocilaVklop", False), o.dogodki)
        self.assertFalse(self.so.sporocila_vklop.sporocila_vklopljena())
        # razdelka ni nikjer: odpiranje (tudi z Linka ali obvestila) se ne zgodi
        with mock.patch.object(self.so, "_ima_delovno", lambda _s: True):
            self.assertFalse(self.so.SafeerOS._odpri_razdelek(o, "sporocila"))
            self.assertFalse(self.so.SafeerOS._odpri_razdelek(o, "kanal:telegram"))
        self.assertNotIn(("okno", "sporocila"), o.dogodki)
        with mock.patch.object(self.so.GLib, "idle_add") as idle:
            self.so.SafeerOS.pokazi_sporocila(o)
        idle.assert_not_called()
        # vklop: vse se vrne brez ponovnega zagona
        with mock.patch.object(self.so.GLib, "idle_add", lambda f, *a, **k: f()):
            self.assertTrue(self.so.SafeerOS._nastavi_sporocila(o, True))
        self.assertEqual(o.sporocila.klici, ["ustavi", "nadaljuj"])
        self.assertEqual((o._kanali_sporocil.zagnani, o.kuverta_zacni), (1, 1))
        with mock.patch.object(self.so, "_ima_delovno", lambda _s: True):
            self.assertTrue(self.so.SafeerOS._odpri_razdelek(o, "sporocila"))

    def test_vklop_iz_niti_ozadja_gtk_v_glavni_niti(self):
        """Most poklice sporocilaVklop v niti ozadja: storitev se ustavi tam, kanali, kuverta in okno pa v glavni niti
        (GTK in WebKit samo v glavni niti - pregled 15. 10. 2026)."""
        import threading
        o = _Os()
        cakajo = []
        with mock.patch.object(self.so.GLib, "idle_add", lambda f, *a, **k: cakajo.append(f)):
            t = threading.Thread(target=lambda: self.so.SafeerOS._nastavi_sporocila(o, False))
            t.start()
            t.join(5)
        self.assertEqual(o.sporocila.klici, ["ustavi"])
        self.assertFalse(o._kanali_sporocil.ustavljeni, "kanali se ne sprostijo v niti ozadja")
        self.assertEqual(len(cakajo), 1)
        cakajo[0]()
        self.assertTrue(o._kanali_sporocil.ustavljeni)
        self.assertEqual(o.niti_uskladitve, [True])

    def test_nastavitve_in_prilagodi_imata_stikalo(self):
        vir = beri("safeer_os.py")
        self.assertIn('"sporocila": sporocila_vklop.sporocila_vklopljena()', vir)
        self.assertIn('if kljuc == "sporocila":', vir)
        self.assertIn('stikalo("sporocila", "ndSporocila", "sporocila", d.sporocila)', beri("assets", "os", "os.js"))
        self.assertIn('prilagodi.nastavi({ sporocila: koren.videz.sporocila === false })',
                      beri("assets", "os", "qml", "Prilagodi.qml"))
        self.assertIn('self.os._nastavi_sporocila(sprememba["sporocila"])', beri("core", "os_lupina.py"))
        # razdelek izklopljenih Sporocil ni med zadetki iskanja (QML in delovna povrsina) in ne v meniju
        self.assertIn('koren.videz.sporocila !== false || x[0] !== "sporocila"', beri("assets", "os", "qml", "Namizje.qml"))
        self.assertIn('(sporocilaVklopljena || c[0] !== "sporocila")', beri("assets", "os", "delovna.js"))
        self.assertIn('#meni button[data-razdelek="sporocila"]', beri("assets", "os", "os.js"))


class MostKanalov(unittest.TestCase):
    def test_most_in_stran_se_ujemata(self):
        vir, js = beri("safeer_os.py"), beri("assets", "os", "os.js")
        for metoda in ("kanaliSeznam", "kanalDodaj", "kanalOdstrani", "kanalPreimenuj", "kanalPremakni", "kanalVklopi",
                       "kanalIzbrisiPodatke", "kanalPokazi", "kanalPolozaj", "kanalSkrij", "kanalUkaz",
                       "kanalIzberiProgram", "sporocilaKanalVklop"):
            self.assertIn('"%s":' % metoda, vir, metoda)
            self.assertIn('klic("%s"' % metoda, js, metoda)
        html = beri("assets", "os", "index.html")
        for idn in ("vgrajenKanal", "vgrajenKanalVsebina", "slojVgrajenUredi", "kanalUrediVklop", "vgrajenUrediVklop"):
            self.assertIn('id="%s"' % idn, html)

    def test_okna_sporocil_imajo_prekrivanje(self):
        vir = beri("safeer_os.py")
        self.assertIn("prekrivanje = self._prekrivanje_kanalov(pogled)", vir)
        self.assertIn("postavitev.append(self._prekrivanje_kanalov(pogled))", vir)
        self.assertIn("okno.set_child(prekrivanje)", vir)

    def test_kanali_ob_zagonu_namizja_po_izrisu(self):
        vir = beri("safeer_os.py")
        telo = vir.split("def _ob_namizju", 1)[1].split("def _izklopi_delovno", 1)[0]
        self.assertIn("GLib.idle_add(self._zacni_kanale, priority=GLib.PRIORITY_LOW)", telo)

    def test_kuverta_steje_vgrajene_kanale(self):
        import safeer_os as so
        o = _Os()
        o._kuverta_stevilo = -1
        narisano = []
        o._narisi_kuverto = narisano.append
        o.sporocila = mock.Mock()
        o.sporocila.neprebrano_skupaj.return_value = 2
        with mock.patch.object(so.sporocila_vklop, "sporocila_vklopljena", lambda: True), \
                mock.patch.object(so.threading, "Thread", lambda target, **k: mock.Mock(start=target)), \
                mock.patch.object(so.GLib, "idle_add", lambda f, *a: f()):
            so.SafeerOS._osvezi_kuverto(o)
        self.assertEqual(narisano, [9], "2 iz posta/Telegram + 7 iz vgrajenih kanalov")


if __name__ == "__main__":
    unittest.main()

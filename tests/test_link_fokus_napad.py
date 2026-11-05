# -*- coding: utf-8 -*-
"""Skok po gumbih z daljincem (core/link_fokus.py) proti zlonamerni strani (napadalski pregled 5. 11. 2026).

Daljinec premika pravi kazalec na element, ki ga opise dostopnost (AT-SPI), in OK klikne z uinput. Postavitev,
velikost in fokus elementov spletne vsebine doloca stran. Lazen AT-SPI tu posnema brskalnik: okno, orodna vrstica,
vidno obmocje (scroll pane) in dokument strani, ki je velik kot vsa stran (tako ga vrne WebKit, izmerjeno 5. 11.).
"""
import unittest

from core import link_fokus
from core.link_fokus import Fokus


class _Pravokotnik:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.width, self.height = x, y, w, h


class _Stanja:
    def __init__(self, stanja):
        self.stanja = set(stanja)

    def contains(self, s):
        return s in self.stanja


class _Atspi:
    class StateType:
        SHOWING, SENSITIVE, FOCUSED, EDITABLE, ACTIVE = "showing", "sensitive", "focused", "editable", "active"

    class CoordType:
        WINDOW = "window"

    def __init__(self, aplikacije):
        self.namizje = _El("desktop", (0, 0, 0, 0), aplikacije)

    def get_desktop(self, _i):
        return self.namizje


class _El:
    def __init__(self, vloga, pravokotnik, otroci=(), stanja=("showing", "sensitive"), pid=None, zadetek=None):
        self.vloga, self.p, self.otroci, self.stanja, self.pid = vloga, _Pravokotnik(*pravokotnik), list(otroci), stanja, pid
        self.zadetek, self.stars = zadetek, None
        for c in self.otroci:
            c.stars = self

    def get_role_name(self):
        return self.vloga

    def get_state_set(self):
        return _Stanja(self.stanja)

    def get_extents(self, _k):
        return self.p

    def get_child_count(self):
        return len(self.otroci)

    def get_child_at_index(self, i):
        return self.otroci[i]

    def get_process_id(self):
        return self.pid

    def get_parent(self):
        return self.stars

    def get_index_in_parent(self):
        return self.stars.otroci.index(self)

    def get_accessible_at_point(self, x, y, _k):
        # GTK4 (vsebniki) vrne None; dokument strani (WebKit) isce zadetek sam - s plastmi, ki jih doloca stran.
        return self.zadetek(x, y) if self.zadetek else None


OKNO = (4242, 0, 0, 800, 600)


def _brskalnik(vsebina, zadetek=None, nazaj=None):
    """Okno brskalnika 800 x 600: orodna vrstica z gumbom (0-50), vidno obmocje stran 50-600, dokument strani."""
    dokument = _El("document web", (0, 50, 800, 30000), vsebina, zadetek=zadetek)
    vrstica = _El("tool bar", (0, 0, 800, 50), [_El("push button", (10, 10, 30, 30))])
    pogled = _El("scroll pane", (0, 50, 800, 550), [dokument])
    okvir = _El("frame", (0, 0, 800, 600), [_El("panel", (0, 0, 800, 600), [vrstica, pogled])],
                stanja=("showing", "sensitive", "active"))
    return _Atspi([_El("application", (0, 0, 0, 0), [okvir], stanja=(), pid=4242)])


class _Lazni:
    def __init__(self, atspi):
        self.atspi = atspi

    def __enter__(self):
        self.prej = link_fokus._atspi
        link_fokus._atspi = lambda: self.atspi
        return self

    def __exit__(self, *_a):
        link_fokus._atspi = self.prej


class VelikanskiElement(unittest.TestCase):
    def test_sredina_velikanskega_gumba_ostane_v_oknu(self):
        """role=button sirine 40000 px: prej je bila sredina (20700, 15500) - kazalec izven okna."""
        with _Lazni(_brskalnik([_El("push button", (700, 500, 40000, 30000))])):
            elementi = link_fokus.preberi_elemente(OKNO)
        gumbi = [e for e in elementi if e[3] >= 50]
        self.assertEqual(len(gumbi), 1, elementi)
        cx, cy = gumbi[0][:2]
        self.assertTrue(700 <= cx < 800 and 500 <= cy < 600, (cx, cy))

    def test_element_strani_ne_seze_na_orodno_vrstico(self):
        """Gumb strani, pomaknjen nad vidno obmocje (y 30-60): sredina 45 bi bila na orodni vrstici brskalnika."""
        with _Lazni(_brskalnik([_El("link", (200, 30, 100, 30))])):
            elementi = link_fokus.preberi_elemente(OKNO)
        strani = [e for e in elementi if e[2] >= 200]
        self.assertEqual(len(strani), 1, elementi)
        self.assertGreaterEqual(strani[0][1], 50, "sredina elementa strani je na orodni vrstici")
        self.assertGreaterEqual(strani[0][3], 50)

    def test_gumb_orodne_vrstice_ostane(self):
        with _Lazni(_brskalnik([])):
            elementi = link_fokus.preberi_elemente(OKNO)
        self.assertEqual([e[:2] for e in elementi], [(25.0, 25.0)])


class _Drugi:
    def __init__(self):
        self.kazalec = []
        drugi = self

        class Vnos:
            def absolutno(self, x, y):
                drugi.kazalec.append((x, y))
                return True
        self.vnos = Vnos()


def _fokus(elementi, zadetek=None):
    f = Fokus(_Drugi())
    f._okno = lambda: OKNO
    f._elementi = lambda _o: elementi
    f.zahteve = []

    def zahteva(z, _rok):
        f.zahteve.append(z)
        return zadetek
    f._pomocnik_zahteva = zahteva
    return f


def _e(cx, cy, fokus=0, pot="0", stran=1):
    return (float(cx), float(cy), cx - 10, cy - 10, 20, 20, fokus, 0, 0, pot, stran)


class ZacetniFokus(unittest.TestCase):
    def test_fokus_strani_ne_doloci_prvega_skoka(self):
        """Stran s focus() na svojem gumbu (v kotu) ne odloci, kam skoci kazalec ob novem oknu."""
        f = _fokus([_e(780, 590, fokus=1, pot="1"), _e(400, 300, pot="2")])
        f.premakni("dol")
        self.assertEqual(f.izbira[9], "2")
        self.assertEqual(f.drugi.kazalec, [(400, 300)])

    def test_fokus_programa_se_vedno_velja(self):
        """Pogovorno okno programa: privzeti gumb (fokus programa, ne strani) ostane prvi cilj."""
        f = _fokus([_e(780, 590, fokus=1, pot="1", stran=0), _e(400, 300, pot="2")])
        f.premakni("dol")
        self.assertEqual(f.izbira[9], "1")


class PremaknjenCilj(unittest.TestCase):
    def _izbran(self, zadetek, izbira=None):
        f = _fokus([_e(400, 300, pot="0/1/0/3")], zadetek)
        f.premakni("dol")                       # novo okno: izbira je edini element
        if izbira is not None:
            f.izbira = izbira
        return f

    def test_isti_cilj_klikne(self):
        f = self._izbran({"pot": "0/1/0/3", "v_strani": True})
        self.assertTrue(f.pred_klikom())
        self.assertEqual(f.zahteve, [{"okno": list(OKNO), "tocka": [400.0, 300.0]}])

    def test_besedilo_v_gumbu_je_isti_cilj(self):
        self.assertTrue(self._izbran({"pot": "0/1/0/3/0", "v_strani": True}).pred_klikom())

    def test_tuj_okvir_pod_kazalcem_ne_klikne(self):
        f = self._izbran({"pot": "0/1/0/7/0/0", "v_strani": True})
        self.assertFalse(f.pred_klikom())
        self.assertTrue(f.zavrnjen_klik)

    def test_prekrivalo_strani_ne_klikne(self):
        """Prekrivalo brez vloge: WebKit vrne dokument (prednika izbire) - to ni izbrani gumb."""
        self.assertFalse(self._izbran({"pot": "0/1/0", "v_strani": True}).pred_klikom())

    def test_gtk_brez_iskanja_zadetka_klikne(self):
        """Iskanje se je ustavilo na vsebniku GTK nad spletnim pogledom: ne vemo vec kot prej, daljinec dela."""
        self.assertTrue(self._izbran({"pot": "0", "v_strani": False}).pred_klikom())

    def test_zunaj_okna_ne_klikne(self):
        self.assertFalse(self._izbran({"zunaj": True}).pred_klikom())

    def test_pomocnik_ne_odgovori_klikne(self):
        self.assertTrue(self._izbran(None).pred_klikom())

    def test_element_programa_brez_preverbe(self):
        f = self._izbran({"pot": "9", "v_strani": True}, izbira=_e(400, 300, pot="0/1/0/3", stran=0))
        self.assertTrue(f.pred_klikom())
        self.assertEqual(f.zahteve, [])

    def test_novo_okno_pod_kazalcem_ne_klikne(self):
        """window.open pod kazalcem: OK ne klikne na slepo v novo okno."""
        f = self._izbran({"pot": "0/1/0/3", "v_strani": True})
        f._okno = lambda: (4243, 0, 0, 800, 600)
        self.assertFalse(f.pred_klikom())

    def test_kazalec_uporabnika_brez_preverbe(self):
        f = self._izbran({"zunaj": True})
        f.izbira = None                          # uporabnik je premaknil kazalec sam (miska, dotik)
        self.assertTrue(f.pred_klikom())


class ZadetekVAtspi(unittest.TestCase):
    """Pomocni proces: zadetek pod tocko prek GetAccessibleAtPoint, GTK4 vsebniki po pravokotnikih."""

    def _drevo(self, nad_gumbom):
        gumb = _El("push button", (300, 300, 120, 40))
        tuj = _El("push button", (280, 270, 200, 100))
        okvir_strani = _El("internal frame", (280, 270, 200, 100), [_El("document web", (280, 270, 200, 100), [tuj])])

        def isci(x, y):
            return okvir_strani.otroci[0].otroci[0] if nad_gumbom else gumb
        return _brskalnik([gumb, okvir_strani], zadetek=isci), gumb

    def test_premaknjen_tuj_okvir(self):
        atspi, _g = self._drevo(True)
        with _Lazni(atspi):
            elementi = link_fokus.preberi_elemente(OKNO)
            gumb = [e for e in elementi if e[2] == 300][0]
            z = link_fokus.zadetek(OKNO, gumb[:2])
        self.assertTrue(z["v_strani"])
        self.assertFalse(link_fokus._pod_potjo(z["pot"], gumb[9]), (z, gumb))

    def test_isti_gumb(self):
        atspi, _g = self._drevo(False)
        with _Lazni(atspi):
            elementi = link_fokus.preberi_elemente(OKNO)
            gumb = [e for e in elementi if e[2] == 300][0]
            z = link_fokus.zadetek(OKNO, gumb[:2])
        self.assertEqual(z["pot"], gumb[9])


class OkNaDaljincu(unittest.TestCase):
    """Pot OK od daljinca (core/link_sway.SwayVnos.izvedi): ob premaknjenem cilju ni klika miske."""

    def _klik(self, zadetek):
        from core.link_sway import SwayVnos
        f = _fokus([_e(400, 300, pot="0/1/0/3")], zadetek)
        poslano = []

        class Drugi(_Drugi):
            def tece(self):
                return True
        d = Drugi()
        f.drugi = d
        d.fokus = f
        f.premakni("dol")
        v = object.__new__(SwayVnos)
        v.drugi = d
        v._poslji = lambda *a: (poslano.append(a), True)[1]
        v.stevec = 0
        v.izvedi({"vrsta": "klik"})
        return [a for a in poslano if a[:2] == ("m", 2)]

    def test_premaknjen_cilj_ni_klik(self):
        self.assertEqual(self._klik({"pot": "0/1/0/7/0/0", "v_strani": True}), [])

    def test_isti_cilj_je_klik(self):
        self.assertEqual(len(self._klik({"pot": "0/1/0/3", "v_strani": True})), 2)   # gumb dol in gor


if __name__ == "__main__":
    unittest.main()

"""Pregled Spleta 14. 10. 2026 (brez okna): pravila navigacije okvirjev, lokalne datoteke, »Izbrisi ob izhodu«,
Safeer DRM po kliku, zunanji programi brez zamrznitve, seja brez zgodovine."""
import os
import tempfile
import types
import unittest

import safeer_brskalnik as b
from core import os_splet


class _Cfg(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)

    def set(self, k, v):
        self[k] = v


class _GLib:
    def __init__(self):
        self.cakajo = []

    def idle_add(self, f, *a):
        self.cakajo.append((f, a))

    def pozeni(self):
        while self.cakajo:
            f, a = self.cakajo.pop(0)
            f(*a)


def preizkus_vdelana_vsebina():
    stran = "https://www.primer.si/clanek"
    assert os_splet.je_vdelana_vsebina("about:srcdoc", stran)
    assert os_splet.je_vdelana_vsebina("data:text/html,<p>x</p>", stran)
    assert os_splet.je_vdelana_vsebina("blob:https://www.primer.si/0b7c-11", stran)
    assert os_splet.je_vdelana_vsebina("blob:webkit-pdfjs-viewer://pdfjs/3f2a", stran)
    assert not os_splet.je_vdelana_vsebina("blob:https://drugi.example/0b7c", stran)       # tuj izvor
    assert not os_splet.je_vdelana_vsebina("blob:null/abc", stran)
    assert not os_splet.je_vdelana_vsebina("javascript:alert(1)", stran)
    assert not os_splet.je_vdelana_vsebina("about:blank#x", stran)


def preizkus_lokalni_naslov():
    with tempfile.NamedTemporaryFile(suffix=".html") as f:
        uri = "file://" + f.name
        assert os_splet.lokalni_naslov(uri) == uri
        assert os_splet.lokalni_naslov("file://localhost" + f.name) == "file://localhost" + f.name
    assert os_splet.lokalni_naslov("file:///ni/take/datoteke.html") == ""
    assert os_splet.lokalni_naslov("file://" + tempfile.gettempdir()) == ""          # mapa
    assert os_splet.lokalni_naslov("file://drug-racunalnik/etc/hosts") == ""
    assert os_splet.lokalni_naslov("https://a.si/") == ""


def preizkus_lokalna_datoteka_samo_od_uporabnika():
    from unittest import mock
    with tempfile.NamedTemporaryFile(suffix=".html") as f:
        uri = "file://" + f.name
        pogled = mock.Mock()
        pogled.get_uri.return_value = "https://banka.example/"
        s = types.SimpleNamespace(koren=b.KOREN, trenutni=lambda: pogled, nov_zavihek=mock.Mock())
        assert not os_splet.VdelaniSplet.odpri_povezavo(s, uri)                 # sporocilo: ne
        assert os_splet.VdelaniSplet.odpri_povezavo(s, uri, lokalno=True)       # »Odpri z«: da
        s.nov_zavihek.assert_called_once_with(uri, lokalno=True)
    vir = open(os.path.join(b.KOREN, "safeer_brskalnik.py"), encoding="utf-8").read()
    assert "odpri_povezavo(naslov, lokalno=True)" in vir and "odpri(naslov, lokalno=True)" in vir


def preizkus_izbrisi_ob_izhodu_za_vse_splete():
    """Safeer OS ob izhodu: oba Spleta (okno, namizje) - DRM konec in brisanje, s cakanjem na WebKit."""
    dnevnik = []
    zamik = []

    class S:
        def __init__(self, ime):
            self.ime = ime

        def koncaj_drm(self):
            dnevnik.append(("drm", self.ime))

        def pocisti_ob_izhodu(self, ob_koncu=None):
            dnevnik.append(("brisi", self.ime))
            zamik.append(ob_koncu)              # WebKit konca kasneje (asinhrono)

    class Kontekst:
        def iteration(self, _blokiraj):
            if zamik:
                zamik.pop(0)()
                return True
            return False
    G = types.SimpleNamespace(MainContext=types.SimpleNamespace(default=lambda: Kontekst()))
    assert os_splet.pocisti_vse_ob_izhodu([S("okno"), None, S("namizje")], G, cas=2)
    assert dnevnik == [("drm", "okno"), ("drm", "namizje"), ("brisi", "okno"), ("brisi", "namizje")]
    # WebKit se ne oglasi: izhod ne caka dlje od roka.
    zamik.clear()

    class Tih(S):
        def pocisti_ob_izhodu(self, ob_koncu=None):
            pass
    assert not os_splet.pocisti_vse_ob_izhodu([Tih("x")], G, cas=0.05)
    vir = open(os.path.join(b.KOREN, "safeer_os.py"), encoding="utf-8").read()
    assert "pocisti_vse_ob_izhodu([self._spletni, self._spletni_namizje], GLib)" in vir


def preizkus_seja_ni_shranjena_ob_brisanju_zgodovine():
    c = _Cfg()
    b.shrani_ali_pozabi_sejo(c, ["https://a.si/"], 0)
    assert b.nalozi_sejo(c) == ["https://a.si/"]
    c["brisi_ob_izhodu"] = ["zgodovina"]
    b.shrani_ali_pozabi_sejo(c, ["https://b.si/"], 0)
    assert b.nalozi_sejo(c) == [] and c["splet_seja_izbran"] == 0
    vir = open(os.path.join(b.KOREN, "safeer_brskalnik.py"), encoding="utf-8").read()
    assert "shrani_ali_pozabi_sejo(self.splet.config" in vir.split("def _ob_zaprtju", 1)[1]


# ---------------------------------------------------------------- pravila navigacije (decide-policy)
_PDT = types.SimpleNamespace(NAVIGATION_ACTION="NAV", NEW_WINDOW_ACTION="NOVO", RESPONSE="ODZIV")
_NT = types.SimpleNamespace(LINK_CLICKED="KLIK", OTHER="DRUGO", FORM_SUBMITTED="OBRAZEC")


class _Zahteva:
    def __init__(self, uri, metoda="GET"):
        self.uri, self.metoda = uri, metoda

    def get_uri(self):
        return self.uri

    def get_http_method(self):
        return self.metoda


class _Dejanje:
    def __init__(self, uri, vrsta="DRUGO", metoda="GET", preusmeritev=False):
        self.z, self.vrsta, self.pre = _Zahteva(uri, metoda), vrsta, preusmeritev

    def get_request(self): return self.z
    def get_navigation_type(self): return self.vrsta
    def get_mouse_button(self): return 1
    def get_modifiers(self): return 0
    def is_redirect(self): return self.pre
    def is_user_gesture(self): return self.vrsta == "KLIK"


class _Odlocitev:
    def __init__(self, dejanje=None, glavni=True, odziv_uri=None, metoda="GET"):
        self.d, self.izid, self.glavni = dejanje, None, glavni
        self.odziv = types.SimpleNamespace(get_uri=lambda: odziv_uri)
        self.zahteva = _Zahteva(odziv_uri, metoda)

    def get_navigation_action(self): return self.d
    def use(self): self.izid = "use"
    def ignore(self): self.izid = "ignore"
    def is_main_frame_main_resource(self): return self.glavni
    def get_request(self): return self.zahteva
    def get_response(self): return self.odziv


class _Pogled:
    def __init__(self, uri, politika="ALWAYS"):
        self.uri, self.nalozeno, self.p = uri, [], politika

    def get_uri(self): return self.uri
    def load_uri(self, u): self.nalozeno.append(u)
    def get_settings(self): return types.SimpleNamespace(get_hardware_acceleration_policy=lambda: self.p)


def _splet():
    s = object.__new__(os_splet.VdelaniSplet)
    s.WebKit2 = types.SimpleNamespace(PolicyDecisionType=_PDT, NavigationType=_NT,
                                      HardwareAccelerationPolicy=types.SimpleNamespace(NEVER="NEVER", ALWAYS="ALWAYS"))
    s.Gdk = types.SimpleNamespace(ModifierType=types.SimpleNamespace(CONTROL_MASK=4))
    s.GLib = _GLib()
    s.config = _Cfg()
    s.zavihki, s.stremio_dodatek = [], None
    s.jezik = lambda: "sl"
    return s


def preizkus_okvir_z_utm_ne_zamenja_zavihka():
    s, p = _splet(), _Pogled("https://glasba.primer.si/")
    o = _Odlocitev(_Dejanje("https://open.spotify.com/embed/track/1?utm_source=generator"))
    s._politika(p, o, "NAV")
    s.GLib.pozeni()
    assert o.izid == "use" and p.nalozeno == []
    # Klik na povezavo (glavni okvir): sledilni parametri gredo stran, kot v safeer_mint.py.
    o = _Odlocitev(_Dejanje("https://novice.primer.si/a?utm_source=x&id=3", "KLIK"))
    s._politika(p, o, "NAV")
    s.GLib.pozeni()
    assert o.izid == "ignore" and p.nalozeno == ["https://novice.primer.si/a?id=3"]
    # Preusmeritev in obrazec ostaneta.
    for d in (_Dejanje("https://n.primer.si/a?utm_source=x", "KLIK", preusmeritev=True),
              _Dejanje("https://n.primer.si/a?utm_source=x", "OBRAZEC", "POST")):
        o = _Odlocitev(d)
        s._politika(p, o, "NAV")
        assert o.izid == "use"


def preizkus_srcdoc_data_blob_dovoljeni():
    s, p = _splet(), _Pogled("https://www.primer.si/")
    for uri, izid in (("about:srcdoc", "use"), ("data:text/html,x", "use"), ("blob:https://www.primer.si/1", "use"),
                      ("blob:https://tuj.example/1", "ignore"), ("javascript:x", "ignore")):
        o = _Odlocitev(_Dejanje(uri))
        s._politika(p, o, "NAV")
        assert o.izid == izid, uri


def preizkus_zamenjava_za_izris_samo_glavni_okvir_get_in_izven_signala():
    s, p = _splet(), _Pogled("https://a.primer.si/")
    s._zelena_politika = lambda naslov: "NEVER"
    zamenjave = []
    s._zamenjaj_za_pospesevanje = lambda pg, u: zamenjave.append(u) or True
    o = _Odlocitev(glavni=False, odziv_uri="https://okvir.example/")
    assert s._odziv(p, o) is False and o.izid is None                         # okvir: nic
    o = _Odlocitev(glavni=True, odziv_uri="https://b.primer.si/", metoda="POST")
    assert s._odziv(p, o) is False                                            # obrazec: ne postane GET
    o = _Odlocitev(glavni=True, odziv_uri="https://b.primer.si/")
    assert s._odziv(p, o) is True and o.izid == "ignore" and zamenjave == []  # ne med signalom
    s.GLib.pozeni()
    assert zamenjave == ["https://b.primer.si/"]
    s._zelena_politika = lambda naslov: "ALWAYS"
    o = _Odlocitev(glavni=True, odziv_uri="https://c.primer.si/")
    assert s._odziv(p, o) is False                                            # isti izris: nic


# ---------------------------------------------------------------- Safeer DRM po kliku
def _splet_drm(odlocitev):
    s = _splet()
    s.config["dovoljenja_privzeto"] = {"drm": odlocitev}
    p = _Pogled("https://video.primer.si/film")
    z = {"pogled": p}
    s.zavihki = [z]
    s.trenutni = lambda: p
    s.vrstica = []
    s.pojavna = types.SimpleNamespace(set_reveal_child=lambda v: s.vrstica.append(v))
    s.pojavna_napis = types.SimpleNamespace(set_text=lambda t: s.vrstica.append(t))
    s.pojavna_odpri = types.SimpleNamespace(set_label=lambda t: None)
    s.pojavna_vedno = types.SimpleNamespace(set_visible=lambda v: None)
    s._pojavno, s._drm_ponudba = None, None
    s.vdelano, s.vprasano = [], []
    s._drm_vdelaj = lambda pg, u: s.vdelano.append(u) or True
    s._drm = types.SimpleNamespace(odpri=lambda u: s.vdelano.append("brskalnik:" + u))
    s._vprasaj = lambda naslov, opis, gumbi, odgovor: s.vprasano.append(odgovor)
    return s, p, z


def preizkus_drm_ponudba_brez_zagona_in_klik():
    s, p, z = _splet_drm("dovoli")
    s._drm_ponudi(p, p.uri, True)
    assert s.vdelano == [] and s._drm_ponudba == (p, p.uri) and True in s.vrstica
    assert "Video na video.primer.si" in s.vrstica[0]
    s._drm_klik()
    assert s.vdelano == [p.uri] and s._drm_ponudba is None


def preizkus_drm_zavrnjeno_in_vprasaj():
    s, p, z = _splet_drm("zavrni")
    s._drm_ponudi(p, p.uri, False)
    s._drm_klik()
    assert s.vdelano == []
    s, p, z = _splet_drm("vprasaj")
    s._drm_ponudi(p, p.uri, False)
    s._drm_klik()
    assert s.vdelano == [] and len(s.vprasano) == 1
    s.vprasano[0](1)                                        # »Dovoli«: zapomni in zazeni
    assert s.vdelano == [p.uri]
    assert s.config["dovoljenja_strani"]["video.primer.si"]["drm"] == "dovoli"


def preizkus_drm_ponudba_ne_velja_na_drugi_strani():
    s, p, z = _splet_drm("dovoli")
    s._drm_ponudi(p, p.uri, False)
    p.uri = "https://drugo.example/"
    s._drm_klik()
    assert s.vdelano == []
    assert s._drm_ponudi(_Pogled("http://video.primer.si/"), "http://video.primer.si/") is None   # samo https


# ---------------------------------------------------------------- zunanji programi
def preizkus_zunanji_program_vrata_pred_iskanjem_in_v_niti():
    import threading
    from unittest import mock
    from core import os_odpri_z
    s = _splet()
    klici = []

    def program(shema):
        klici.append(shema)
        return {"oznaka": "thunderbird.desktop", "ime": "Thunderbird"}
    vprasanja = []
    s._vprasaj = lambda naslov, opis, gumbi, odgovor: vprasanja.append(odgovor)
    s._t = s._ti = lambda k: k
    niti = []
    nit = lambda target, **k: types.SimpleNamespace(start=lambda: niti.append(target))  # noqa: E731
    with mock.patch.object(os_odpri_z, "program_za_shemo", program), mock.patch.object(threading, "Thread", nit):
        _zunanji(s, niti, klici, vprasanja)


def _zunanji(s, niti, klici, vprasanja):
    s._zunanji_program("mailto:a@b.si", "mailto", "https://stran.example/", True)
    assert klici == [] and len(niti) == 1                  # iskanje v niti, ne v niti GTK
    s._zunanji_program("mailto:a@b.si", "mailto", "https://stran.example/", True)
    assert len(niti) == 1                                  # iskanje ze tece
    niti[0]()
    s.GLib.pozeni()
    assert klici == ["mailto"] and len(vprasanja) == 1
    # Zanka strani med odprtim vprasanjem: brez iskanja in brez novih vprasanj.
    for _ in range(50):
        s._zunanji_program("mailto:a@b.si", "mailto", "https://stran.example/", False)
    s.GLib.pozeni()
    assert klici == ["mailto"] and len(vprasanja) == 1 and len(niti) == 1
    vprasanja[0](0)                                        # »Preklici«: tiho za to stran
    s._zunanji_program("mailto:a@b.si", "mailto", "https://stran.example/", True)
    assert len(niti) == 1 and len(vprasanja) == 1


class Pregled(unittest.TestCase):
    """CI zaganja skupino gtk4 z unittest: vsak preizkus_* je tu metoda test_*."""


for _ime, _f in list(globals().items()):
    if _ime.startswith("preizkus_"):
        setattr(Pregled, "test_" + _ime[len("preizkus_"):], (lambda f: lambda self: f())(_f))
del _ime, _f


if __name__ == "__main__":
    unittest.main()

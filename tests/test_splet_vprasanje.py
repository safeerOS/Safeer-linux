"""Splet: vprasanje strani (lokacija ...) je vrstica nad stranjo, ne modalni dialog (lastnik, 15. 10. 2026: modalni
dialog lokacije na speedtest.net je zaklenil okno Splet - ✕ ni delal, Spleta ni bilo mogoce zapreti)."""
import pathlib
import types
import unittest

from core import os_splet

KOREN = pathlib.Path(__file__).resolve().parent.parent


class _Cfg(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)

    def set(self, k, v):
        self[k] = v


class _Pogled:
    def __init__(self, uri):
        self.uri = uri

    def get_uri(self):
        return self.uri


class _Zahteva:
    def __init__(self):
        self.izid = None

    def allow(self):
        self.izid = "allow"

    def deny(self):
        self.izid = "deny"


class _Vrstica:
    def __init__(self):
        self.vidna, self.besedilo = False, ""

    def set_reveal_child(self, v):
        self.vidna = bool(v)

    def set_text(self, t):
        self.besedilo = t

    def set_tooltip_text(self, _t):
        pass


def _splet(uri="https://www.speedtest.net/result/1"):
    s = object.__new__(os_splet.VdelaniSplet)
    s.config = _Cfg()
    s.jezik = lambda: "sl"
    p = _Pogled(uri)
    s.zavihki = [{"pogled": p}]
    s.aktivni = p
    s.vprasanje = _Vrstica()
    s.vprasanje_napis = s.vprasanje
    s.dialogi_klici = []
    s._vprasaj = lambda *a, **k: s.dialogi_klici.append(a)
    s.WebKit2 = types.SimpleNamespace()
    os_splet.dovoljenja_strani.vrste_zahteve = lambda z, W: ["lokacija"]
    return s, p


def _zahtevaj(s, p):
    z = _Zahteva()
    assert s._dovoljenje(p, z) is True
    return z


def preizkus_lokacija_v_vrstici_ne_v_dialogu():
    izvirnik = os_splet.dovoljenja_strani.vrste_zahteve
    try:
        s, p = _splet()
        z = _zahtevaj(s, p)
        assert s.dialogi_klici == [], "modalni dialog bi zaklenil okno Splet"
        assert s.vprasanje.vidna and "speedtest.net" in s.vprasanje.besedilo
        assert z.izid is None                               # caka na uporabnika
        s._vprasanje_odgovor(1)
        assert z.izid == "allow" and not s.vprasanje.vidna
        assert s.config["dovoljenja_strani"]["www.speedtest.net"]["lokacija"] == "dovoli"
    finally:
        os_splet.dovoljenja_strani.vrste_zahteve = izvirnik


def preizkus_ne_zdaj_zavrne_brez_spomina():
    izvirnik = os_splet.dovoljenja_strani.vrste_zahteve
    try:
        s, p = _splet()
        z = _zahtevaj(s, p)
        s._vprasanje_odgovor(-1)
        assert z.izid == "deny" and not s.vprasanje.vidna
        assert "dovoljenja_strani" not in s.config
    finally:
        os_splet.dovoljenja_strani.vrste_zahteve = izvirnik


def preizkus_vprasanje_velja_za_zavihek_in_stran():
    izvirnik = os_splet.dovoljenja_strani.vrste_zahteve
    try:
        s, p = _splet()
        z = _zahtevaj(s, p)
        drug = _Pogled("https://drugo.example/")
        s.zavihki.append({"pogled": drug})
        s.aktivni = drug
        s._pokazi_vprasanje()
        assert not s.vprasanje.vidna                        # drug zavihek: vrstice ni
        s.aktivni = p
        s._pokazi_vprasanje()
        assert s.vprasanje.vidna                            # nazaj: vprasanje je se tu
        # Zaprt zavihek: zahteva se zavrne (ne visi v WebKitu), brez spomina.
        os_splet.VdelaniSplet._opusti_vprasanja(s.zavihki[0])
        assert z.izid == "deny" and "dovoljenja_strani" not in s.config
        # Ista stran, drug naslov (SPA) ostane; druga stran zavrne.
        z2 = _zahtevaj(s, p)
        p.uri = "https://www.speedtest.net/result/2"
        s._osvezi_orodja = lambda: None
        s._uri_spremenjen(p, None)
        assert z2.izid is None and s.vprasanje.vidna
        p.uri = "https://drugo.example/"
        s._uri_spremenjen(p, None)
        assert z2.izid == "deny" and not s.vprasanje.vidna
    finally:
        os_splet.dovoljenja_strani.vrste_zahteve = izvirnik


def preizkus_vdelana_aplikacija_dobi_dialog():
    izvirnik = os_splet.dovoljenja_strani.vrste_zahteve
    try:
        s, _p = _splet()
        tuj = _Pogled("https://mail.example/")                 # pogled vdelane aplikacije: ni zavihek Spleta
        _zahtevaj(s, tuj)
        assert len(s.dialogi_klici) == 1 and not s.vprasanje.vidna
    finally:
        os_splet.dovoljenja_strani.vrste_zahteve = izvirnik


def preizkus_dialogi_niso_modalni_in_se_zaprejo_s_spletom():
    vir = (KOREN / "core" / "os_splet.py").read_text(encoding="utf-8")
    assert "d.set_modal(True)" not in vir
    assert "d.choose(self._okno_za_dialog(pogled), preklic," in vir
    os_ = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
    zacetek = os_.index("def _skrij_splet_na_namizju(")
    assert "zapri_dialoge()" in os_[zacetek:os_.index("def _sprosti_splet_na_namizju(")]

    class _Preklic:
        def __init__(self):
            self.preklican = False

        def cancel(self):
            self.preklican = True
    s = object.__new__(os_splet.VdelaniSplet)
    s._dialogi = [_Preklic(), _Preklic()]
    s.zapri_dialoge()
    assert all(c.preklican for c in s._dialogi)


class Vprasanje(unittest.TestCase):
    """Kot v test_splet_pregled.py: vsak preizkus_* je tu metoda test_* (pytest in unittest)."""


for _ime, _f in list(globals().items()):
    if _ime.startswith("preizkus_"):
        setattr(Vprasanje, "test_" + _ime[len("preizkus_"):], (lambda f: lambda self: f())(_f))
del _ime, _f


if __name__ == "__main__":
    unittest.main()

"""Preizkusi core/usenet_ponudnik.py (naloga 74). Brez pravega omrezja: lazni streznik NNTP prek TLS na 127.0.0.1
(socketserver v tej datoteki) in lazna zbirka skrivnosti. Varovalo zavrne vsako povezavo izven 127.0.0.1.

Poverilnice in imena so izmisljena (news.primer.invalid); potrdila so samo za ta preizkus.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import socket
import socketserver
import ssl
import threading

import pytest

from core import usenet_nntp as nntp
from core import usenet_ponudnik as up

GESLO = "Lazno-Geslo-74!xyz"
UPORABNIK = "uporabnik.primer74"
NAPACNO = "Napacno-Geslo-74?abc"

# Preizkusni CA in potrdilo za IP 127.0.0.1 (veljata do 2126; zasebni kljuc je samo za ta preizkus).
CA_PEM = """-----BEGIN CERTIFICATE-----
MIIBqDCCAU+gAwIBAgIUYkpjsTlNX3GSTUSEH/CHnrf2jbUwCgYIKoZIzj0EAwIw
ITEfMB0GA1UEAwwWUHJlaXprdXNuaSBDQSBuYWxvZ2E3NDAgFw0yNjEwMjYxMzMw
MTNaGA8yMTI2MTAwMjEzMzAxM1owITEfMB0GA1UEAwwWUHJlaXprdXNuaSBDQSBu
YWxvZ2E3NDBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABI36IYsWAXjGGNAvtg/g
vnLTeLEeiolGHUiTho8q4rBryA+zQ5oMPTeNAxWTqIHr34jzvSxIusXKkvViEox4
Hx6jYzBhMB8GA1UdIwQYMBaAFOWAJPFvrLF9yG0xIZ4IpeN5txwuMA8GA1UdEwEB
/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEGMB0GA1UdDgQWBBTlgCTxb6yxfchtMSGe
CKXjebccLjAKBggqhkjOPQQDAgNHADBEAiB+vjAvMaboO9LyA2DZcDKkRl2ZVt/4
YM2psClrek7JOQIgZUjVv25unxBwKDixZM3Q3NCeGDRTzzhkHNbCh68uAS4=
-----END CERTIFICATE-----
"""
SRV_PEM = """-----BEGIN CERTIFICATE-----
MIIBwTCCAWegAwIBAgIUXf4eLTX34ct6VpEO9rfuCWDu9vUwCgYIKoZIzj0EAwIw
ITEfMB0GA1UEAwwWUHJlaXprdXNuaSBDQSBuYWxvZ2E3NDAgFw0yNjEwMjYxMzMw
MTNaGA8yMTI2MTAwMjEzMzAxM1owFDESMBAGA1UEAwwJMTI3LjAuMC4xMFkwEwYH
KoZIzj0CAQYIKoZIzj0DAQcDQgAEsgxcaMxDO7eMhPlIEdwt9LNqoqhDy/JUJPBi
Z4+2z0eGDXJxixvDbyrgN2lfwMAG6Jch9k+IUcqpSpSuxqroOKOBhzCBhDAMBgNV
HRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIHgDATBgNVHSUEDDAKBggrBgEFBQcDATAP
BgNVHREECDAGhwR/AAABMB0GA1UdDgQWBBRVrhj0/vtgp0CzbVF5lwrtSS9WZjAf
BgNVHSMEGDAWgBTlgCTxb6yxfchtMSGeCKXjebccLjAKBggqhkjOPQQDAgNIADBF
AiEAvwL4xlsJXZ6DxeQnCZUA+NY31mOonsqkVN5wImFcRs4CIEWtPtZSdkK45oit
oF4oDXEQTQkil/ktwP7OrJ2CjjLF
-----END CERTIFICATE-----
"""
SRV_KEY = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg+21pdW8qIwpxDL35
orh09GF7P/OjzyvoRdmoVMhwreahRANCAASyDFxozEM7t4yE+UgR3C30s2qiqEPL
8lQk8GJnj7bPR4YNcnGLG8NvKuA3aV/AwAbolyH2T4hRyqlKlK7Gqug4
-----END PRIVATE KEY-----
"""


# ------------------------------------------------------------------ lazni streznik NNTP (TLS, 127.0.0.1)

class _Rokovalec(socketserver.StreamRequestHandler):
    def setup(self):
        s = self.server.lazni
        try:
            self.request = s.ctx.wrap_socket(self.request, server_side=True)
        except (ssl.SSLError, OSError):
            s.zabelezi("tls_napaka")
            self.request = None
            return
        super().setup()

    def handle(self):
        s = self.server.lazni
        if self.request is None:
            return
        s.zabelezi("povezav", hkrati=+1)
        try:
            self.wfile.write(s.pozdrav)
            while True:
                vrstica = self.rfile.readline(8192)
                if not vrstica:
                    return
                v = vrstica.decode("utf-8", "replace").rstrip("\r\n")
                with s.zaklep:
                    s.prejeto.append(v)
                if v.startswith("AUTHINFO USER "):
                    s.zabelezi("user")
                    self.wfile.write(s.na_user)
                elif v.startswith("AUTHINFO PASS "):
                    s.zabelezi("pass")
                    self.wfile.write(s.na_pass(v[len("AUTHINFO PASS "):]))
                elif v.startswith("STAT "):
                    s.zabelezi("stat")
                    s.zakasnitev.wait(0.2)
                    self.wfile.write(b"223 0 " + v[5:].encode() + b"\r\n")
                elif v == "QUIT":
                    s.zabelezi("quit")
                    self.wfile.write(b"205 adijo\r\n")
                    return
                else:
                    self.wfile.write(b"500 ?\r\n")
        except (OSError, ssl.SSLError):
            pass
        finally:
            s.zabelezi("konec", hkrati=-1)

    def finish(self):
        if self.request is not None:
            try:
                super().finish()
            except (OSError, ssl.SSLError):
                pass


class _TStreznik(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class LazniStreznik:
    """Scenarij se nastavi z atributi: pozdrav, na_user, na_pass(geslo). Steje povezave in ukaze."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.zaklep = threading.Lock()
        self.stevci: dict = {}
        self.prejeto: list = []
        self.hkrati = 0
        self.najvec_hkrati = 0
        self.zakasnitev = threading.Event()
        self.pozdrav = b"200 lazni streznik pripravljen\r\n"
        self.na_user = b"381 vpisi geslo\r\n"
        self.na_pass = lambda g: b"281 ok\r\n" if g == GESLO else b"481 Authentication failed\r\n"
        self._s = _TStreznik(("127.0.0.1", 0), _Rokovalec)
        self._s.lazni = self
        self.vrata = self._s.server_address[1]
        threading.Thread(target=self._s.serve_forever, daemon=True).start()

    def zabelezi(self, kaj, hkrati=0):
        with self.zaklep:
            self.stevci[kaj] = self.stevci.get(kaj, 0) + 1
            self.hkrati += hkrati
            self.najvec_hkrati = max(self.najvec_hkrati, self.hkrati)

    def n(self, kaj):
        with self.zaklep:
            return self.stevci.get(kaj, 0)

    def ustavi(self):
        self._s.shutdown()
        self._s.server_close()


# ------------------------------------------------------------------ pripomocki

class LaznaZbirka:
    """Mock modula skrivnosti (shrani/preberi/pozabi)."""

    def __init__(self, deluje=True):
        self.vnosi: dict = {}
        self.deluje = deluje

    def shrani(self, kljuc, vrednost):
        if not self.deluje:
            return False
        self.vnosi[kljuc] = vrednost
        return True

    def preberi(self, kljuc):
        return self.vnosi.get(kljuc)

    def pozabi(self, kljuc):
        self.vnosi.pop(kljuc, None)


@pytest.fixture(scope="session")
def potrdila(tmp_path_factory):
    d = tmp_path_factory.mktemp("potrdila")
    (d / "ca.pem").write_text(CA_PEM)
    (d / "srv.pem").write_text(SRV_PEM)
    (d / "srv.key").write_text(SRV_KEY)
    srv = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    srv.load_cert_chain(str(d / "srv.pem"), str(d / "srv.key"))
    return srv, str(d / "ca.pem")


@pytest.fixture
def odjemalec(potrdila):
    # Preverba potrdila in imena ostane vklopljena - samo zaupanja vreden CA je preizkusni.
    return ssl.create_default_context(cafile=potrdila[1])


@pytest.fixture
def streznik(potrdila):
    s = LazniStreznik(potrdila[0])
    yield s
    s.ustavi()


@pytest.fixture(autouse=True)
def izolacija(monkeypatch, tmp_path):
    zbirka = LaznaZbirka()
    monkeypatch.setattr(up, "skrivnosti", zbirka)
    nntp.nastavi_shrambo_zapaha(str(tmp_path / "stanje" / "usenet-zapah"))
    for m in (nntp._ZAVRNJENI, nntp._NEZNANE, up._PREVERBE, up._V_POMNILNIKU):
        m.clear()
    ura = [1000.0]
    monkeypatch.setattr(up, "_ura", lambda: ura[0])
    poskusi: list = []
    prava_povezi = socket.socket.connect
    pravi_dns = socket.getaddrinfo

    def varna_povezi(self, naslov):
        poskusi.append(naslov)
        if not (isinstance(naslov, tuple) and ipaddress.ip_address(naslov[0]).is_loopback):
            raise AssertionError("preizkus: povezava izven 127.0.0.1 ni dovoljena")
        return prava_povezi(self, naslov)

    def varen_dns(gostitelj, *a, **k):
        if gostitelj not in ("127.0.0.1", "localhost"):
            raise AssertionError("preizkus: DNS izven 127.0.0.1 ni dovoljen")
        return pravi_dns(gostitelj, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", varna_povezi)
    monkeypatch.setattr(socket, "getaddrinfo", varen_dns)
    yield {"zbirka": zbirka, "ura": ura, "poskusi": poskusi, "pot": str(tmp_path / "nast" / "usenet.json"),
           "mapa": tmp_path}
    nntp.nastavi_shrambo_zapaha(None)


def v_niti(fn, *a, **k):
    """Omrezje ni dovoljeno na glavni niti - preizkus klice kot vmesnik (delovna nit)."""
    izid: dict = {}

    def delo():
        try:
            izid["v"] = fn(*a, **k)
        except BaseException as e:  # noqa: BLE001
            izid["e"] = e

    t = threading.Thread(target=delo)
    t.start()
    t.join(30)
    assert not t.is_alive(), "preizkus: nit visi"
    if "e" in izid:
        raise izid["e"]
    return izid["v"]


def lokalni(streznik, **k):
    return up.Ponudnik(gostitelj="127.0.0.1", uporabnik=UPORABNIK, vrata=streznik.vrata, ime="Moj ponudnik", **k)


def preveri(iz, streznik, odjemalec, geslo=GESLO, p=None):
    return v_niti(up.preveri_ponudnika, p or lokalni(streznik), geslo, pot_nastavitev=iz["pot"], kontekst=odjemalec)


# ------------------------------------------------------------------ validacija

@pytest.mark.parametrize("g", ["", "nntps://news.primer.invalid", "news.primer.invalid/pot", "news primer.invalid",
                               "news.primer.invalid:563", "uporabnik:geslo@news.primer.invalid", "[::1]",
                               "-slabo.primer.invalid", "news.primer.invalid.", "a" * 254, "999.1.1.1",
                               "news\r\n.primer.invalid", "news\x00.invalid", "news..primer.invalid", None, 5])
def test_neveljaven_gostitelj(g):
    with pytest.raises(ValueError) as e:
        up.Ponudnik(gostitelj=g, uporabnik=UPORABNIK)
    if isinstance(g, str) and g:
        assert g not in str(e.value)


@pytest.mark.parametrize("g", ["news.primer.invalid", "eu.news.primer.invalid", "10.0.0.5", "::1", "fd00::5",
                               "novice.primer.invalid"])
def test_veljaven_gostitelj(g):
    p = up.Ponudnik(gostitelj=g, uporabnik=UPORABNIK)
    assert (p.vrata, p.tls, p.najvec_povezav) == (563, True, 8)


@pytest.mark.parametrize("polje,vrednost", [
    ("vrata", 0), ("vrata", 65536), ("vrata", -1), ("vrata", "563"), ("vrata", True), ("vrata", 1.5),
    ("najvec_povezav", 0), ("najvec_povezav", 101), ("najvec_povezav", True), ("najvec_povezav", "8"),
    ("uporabnik", ""), ("uporabnik", "a\r\nQUIT"), ("uporabnik", "a\x00b"), ("uporabnik", "x" * 401),
    ("uporabnik", "\ud800"), ("uporabnik", None), ("ime", "a\nb"), ("ime", "x" * 81), ("ime", None),
    ("tls", "da"), ("tls", 1), ("nevarno_brez_tls", 1)])
def test_neveljavna_polja(polje, vrednost):
    k = {"gostitelj": "news.primer.invalid", "uporabnik": UPORABNIK, polje: vrednost}
    with pytest.raises(ValueError) as e:
        up.Ponudnik(**k)
    if isinstance(vrednost, str) and len(vrednost) > 3:
        assert vrednost not in str(e.value)


def test_meje_povezav_veljajo():
    assert up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK, najvec_povezav=1).najvec_povezav == 1
    assert up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK, najvec_povezav=100).najvec_povezav == 100


# ids: geslo ne sme v imena preizkusov (pytest jih pise v .pytest_cache in izpis).
@pytest.mark.parametrize("geslo", ["", "a\r\nQUIT", GESLO + "\r\n", GESLO + "\x00", "x" * 401, None, 7],
                         ids=["prazno", "crlf", "geslo-crlf", "geslo-nul", "predolgo", "none", "int"])
def test_shrani_zavrne_neveljavno_geslo(izolacija, geslo):
    p = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK)
    with pytest.raises(ValueError) as e:
        up.shrani_ponudnika(p, geslo, izolacija["pot"])
    assert GESLO not in str(e.value) and GESLO not in repr(e.value)
    assert not os.path.exists(izolacija["pot"]) and not izolacija["zbirka"].vnosi


# ------------------------------------------------------------------ TLS in golo besedilo

def test_brez_tls_samo_izrecno_in_doma(izolacija):
    with pytest.raises(ValueError):
        up.Ponudnik(gostitelj="192.168.1.20", uporabnik=UPORABNIK, vrata=119, tls=False)
    with pytest.raises(ValueError):
        up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK, vrata=119, tls=False,
                    nevarno_brez_tls=True)  # ime: brez DNS ne vemo, da je doma
    with pytest.raises(ValueError):
        up.Ponudnik(gostitelj="203.0.113.7", uporabnik=UPORABNIK, vrata=119, tls=False, nevarno_brez_tls=True)
    with pytest.raises(ValueError):
        up.Ponudnik(gostitelj="::ffff:203.0.113.7", uporabnik=UPORABNIK, vrata=119, tls=False, nevarno_brez_tls=True)
    for doma in ("10.1.2.3", "fd00::7", "::ffff:192.168.1.20"):
        up.Ponudnik(gostitelj=doma, uporabnik=UPORABNIK, vrata=119, tls=False, nevarno_brez_tls=True)
    p = up.Ponudnik(gostitelj="192.168.1.20", uporabnik=UPORABNIK, vrata=119, tls=False, nevarno_brez_tls=True)
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    with pytest.raises(up.NapakaPonudnika) as e:
        v_niti(up.preveri_ponudnika, p, GESLO)
    assert e.value.razlog == up.BREZ_TLS
    with pytest.raises(up.NapakaPonudnika):
        up.ustvari_bazen(p)
    assert izolacija["poskusi"] == []  # nobene povezave


def test_tls_privzeto_preveri_potrdilo(izolacija, streznik):
    # Brez konteksta: sistemski CA ne pozna laznega streznika -> TLS pade, geslo ne gre nikamor.
    izid = v_niti(up.preveri_ponudnika, lokalni(streznik), GESLO)
    assert izid == up.NI_ODGOVORA
    assert streznik.n("user") == 0 and streznik.n("pass") == 0
    assert not nntp.prijava_zavrnjena("127.0.0.1", UPORABNIK, GESLO)


def test_kontekst_brez_preverbe_zavrnjen(izolacija, streznik):
    k = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    k.check_hostname = False
    k.verify_mode = ssl.CERT_NONE
    with pytest.raises(ValueError):
        v_niti(up.preveri_ponudnika, lokalni(streznik), GESLO, kontekst=k)
    assert izolacija["poskusi"] == []


def test_ne_na_glavni_niti(izolacija, streznik, odjemalec):
    with pytest.raises(RuntimeError):
        up.preveri_ponudnika(lokalni(streznik), GESLO, kontekst=odjemalec)
    assert izolacija["poskusi"] == []


# ------------------------------------------------------------------ shranjevanje

def test_shrani_preberi_0600_brez_gesla(izolacija):
    p = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK, najvec_povezav=12, ime="Doma")
    assert up.shrani_ponudnika(p, GESLO, izolacija["pot"]) is True
    assert os.stat(izolacija["pot"]).st_mode & 0o777 == 0o600
    besedilo = open(izolacija["pot"], encoding="utf-8").read()
    assert GESLO not in besedilo
    assert up.preberi_ponudnika(izolacija["pot"]) == p
    (kljuc, vrednost), = izolacija["zbirka"].vnosi.items()
    assert vrednost == GESLO and UPORABNIK not in kljuc and "news" not in kljuc and len(kljuc) > 64
    assert [f for f in os.listdir(os.path.dirname(izolacija["pot"])) if f.startswith(".")] == []  # brez ostankov


def test_brez_zbirke_geslo_samo_v_pomnilniku(izolacija):
    izolacija["zbirka"].deluje = False
    p = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK)
    assert up.shrani_ponudnika(p, GESLO, izolacija["pot"]) is False
    assert up._preberi_geslo(p.kljuc_gesla) == GESLO
    for koren, _, datoteke in os.walk(izolacija["mapa"]):
        for d in datoteke:
            assert GESLO.encode() not in open(os.path.join(koren, d), "rb").read()


def test_zamenjan_racun_pozabi_staro_geslo(izolacija):
    a = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK)
    b = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik="drugi.primer74")
    up.shrani_ponudnika(a, GESLO, izolacija["pot"])
    up.shrani_ponudnika(b, NAPACNO, izolacija["pot"])
    assert list(izolacija["zbirka"].vnosi) == [b.kljuc_gesla]


@pytest.mark.parametrize("vsebina", [b"{", b"x" * (70 * 1024), b'{"verzija": 2, "ponudnik": {}}', b"\xff\xfe",
                                     b'{"verzija": 1, "ponudnik": {"gostitelj": "news.primer.invalid", '
                                     b'"uporabnik": "u", "vrata": 1' + b"0" * 400 + b'}}',
                                     b'{"verzija": 1, "ponudnik": {"gostitelj": "news.primer.invalid", '
                                     b'"uporabnik": "u", "zlo": 1}}',
                                     b'{"verzija": 1, "ponudnik": []}'])
def test_pokvarjene_nastavitve(izolacija, vsebina):
    os.makedirs(os.path.dirname(izolacija["pot"]), exist_ok=True)
    with open(izolacija["pot"], "wb") as f:
        f.write(vsebina)
    assert up.preberi_ponudnika(izolacija["pot"]) is None
    assert up.stanje_za_vmesnik(izolacija["pot"])["vpisan"] is False


# ------------------------------------------------------------------ preverba

def test_preverba_velja(izolacija, streznik, odjemalec):
    p = lokalni(streznik)
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    assert up.stanje_za_vmesnik(izolacija["pot"])["stanje"] == up.NEPREVERJEN
    assert preveri(izolacija, streznik, odjemalec) == up.VELJA
    assert (streznik.n("povezav"), streznik.n("user"), streznik.n("pass")) == (1, 1, 1)
    streznik.zakasnitev.wait(0.2)  # QUIT pride za zaprtjem odjemalca
    assert streznik.n("quit") == 1
    s = up.stanje_za_vmesnik(izolacija["pot"])
    assert s["stanje"] == up.VELJA and s["usenet_viden"] is True


def test_napacno_geslo_zapah_brez_ponovitev(izolacija, streznik, odjemalec):
    p = lokalni(streznik)
    up.shrani_ponudnika(p, NAPACNO, izolacija["pot"])
    assert preveri(izolacija, streznik, odjemalec, NAPACNO) == up.NE_VELJA
    assert streznik.n("pass") == 1
    # Uporabnik klika znova (tudi po minuti): zapah velja, nic ne gre na omrezje.
    for _ in range(5):
        izolacija["ura"][0] += 120
        assert preveri(izolacija, streznik, odjemalec, NAPACNO) == up.ZAKLENJEN
    assert (streznik.n("povezav"), streznik.n("user"), streznik.n("pass")) == (1, 1, 1)
    with pytest.raises(up.NapakaPonudnika) as e:
        up.ustvari_bazen(p, kontekst=odjemalec)
    assert e.value.razlog == up.RACUN_ZAKLENJEN
    assert up.stanje_za_vmesnik(izolacija["pot"])["stanje"] == up.ZAKLENJEN
    # Ponovni zagon (pomnilnik procesa prazen): trajni zapah na disku velja, brez gesla v datoteki.
    nntp._ZAVRNJENI.clear()
    up._PREVERBE.clear()
    assert preveri(izolacija, streznik, odjemalec, NAPACNO) == up.ZAKLENJEN
    assert streznik.n("povezav") == 1
    zapah = open(os.path.join(izolacija["mapa"], "stanje", "usenet-zapah"), "rb").read()
    assert NAPACNO.encode() not in zapah and UPORABNIK.encode() not in zapah
    # Samo nov vpis odklene en nov poskus.
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    assert preveri(izolacija, streznik, odjemalec) == up.VELJA
    assert streznik.n("povezav") == 2 and streznik.n("pass") == 2


def test_zapah_ustavi_ziv_bazen_racuna(izolacija, streznik, odjemalec):
    p = lokalni(streznik)
    up.shrani_ponudnika(p, NAPACNO, izolacija["pot"])
    bazen = up.ustvari_bazen(p, kontekst=odjemalec)
    assert preveri(izolacija, streznik, odjemalec, NAPACNO) == up.NE_VELJA
    with pytest.raises(nntp.NapakaNntp) as e:
        v_niti(bazen.stat, "<a1@primer.invalid>")
    assert e.value.izid == nntp.PRIJAVA
    assert streznik.n("pass") == 1
    bazen.zapri()


def test_481_na_user_geslo_ne_gre(izolacija, streznik, odjemalec):
    streznik.na_user = b"481 Authentication rejected\r\n"
    assert preveri(izolacija, streznik, odjemalec) == up.NE_VELJA
    assert streznik.n("pass") == 0
    assert not any(GESLO in v for v in streznik.prejeto)


@pytest.mark.parametrize("odgovor", [b"482 Authentication commands issued out of sequence\r\n",
                                     b"999 kaj?\r\n", b"abc\r\n", b"281x\r\n", b"502 Permission denied\r\n"])
def test_cuden_odgovor_na_pass_je_zavrnitev(izolacija, streznik, odjemalec, odgovor):
    # Dvom pri AUTHINFO = zavrnjena prijava, ki se ne ponovi (pravilo usenet_nntp).
    streznik.na_pass = lambda g: odgovor
    assert preveri(izolacija, streznik, odjemalec) == up.NE_VELJA
    izolacija["ura"][0] += 120
    assert preveri(izolacija, streznik, odjemalec) == up.ZAKLENJEN
    assert streznik.n("pass") == 1


@pytest.mark.parametrize("pozdrav", [b"502 too many connections\r\n", b"502 service unavailable\r\n",
                                     b"400 too many connections for this account\r\n"])
def test_prevec_povezav_v_pozdravu(izolacija, streznik, odjemalec, pozdrav):
    streznik.pozdrav = pozdrav
    assert preveri(izolacija, streznik, odjemalec) == up.PREVEC_POVEZAV
    assert streznik.n("user") == 0
    assert not nntp.prijava_zavrnjena("127.0.0.1", UPORABNIK, GESLO)


def test_meja_povezav_po_geslu_ni_zapah(izolacija, streznik, odjemalec):
    streznik.na_pass = lambda g: b"482 too many connections\r\n"
    assert preveri(izolacija, streznik, odjemalec) == up.PREVEC_POVEZAV
    assert not nntp.prijava_zavrnjena("127.0.0.1", UPORABNIK, GESLO)
    assert preveri(izolacija, streznik, odjemalec) == up.PREPOGOSTO  # tudi tu ne v zanki
    assert streznik.n("pass") == 1


@pytest.mark.parametrize("pozdrav", [b"200 " + b"x" * 100_000 + b"\r\n", b"2" * 100_000, b"hello\r\n",
                                     b"200\x00\r\n", b"600 kaj\r\n", b"480 najprej prijava\r\n"])
def test_sovrazen_pozdrav(izolacija, streznik, odjemalec, pozdrav):
    streznik.pozdrav = pozdrav
    assert preveri(izolacija, streznik, odjemalec) == up.NI_ODGOVORA
    assert streznik.n("user") == 0
    assert not nntp.prijava_zavrnjena("127.0.0.1", UPORABNIK, GESLO)


def test_ogromen_odgovor_na_pass_drugic_zapah(izolacija, streznik, odjemalec):
    # Odgovor ni znan (geslo je morda prislo do streznika): prvic NI_ODGOVORA, drugic zapored zapah (usenet_nntp).
    streznik.na_pass = lambda g: b"281 " + b"y" * 100_000 + b"\r\n"
    assert preveri(izolacija, streznik, odjemalec) == up.NI_ODGOVORA
    izolacija["ura"][0] += 61
    assert preveri(izolacija, streznik, odjemalec) == up.ZAKLENJEN
    izolacija["ura"][0] += 61
    assert preveri(izolacija, streznik, odjemalec) == up.ZAKLENJEN
    assert streznik.n("pass") == 2


def test_ena_preverba_na_minuto(izolacija, streznik, odjemalec):
    assert preveri(izolacija, streznik, odjemalec) == up.VELJA
    assert preveri(izolacija, streznik, odjemalec) == up.PREPOGOSTO
    izolacija["ura"][0] += 59
    assert preveri(izolacija, streznik, odjemalec) == up.PREPOGOSTO
    izolacija["ura"][0] += 2
    assert preveri(izolacija, streznik, odjemalec) == up.VELJA
    assert streznik.n("povezav") == 2


def test_hkratna_klika_ena_povezava(izolacija, streznik, odjemalec):
    izidi: list = []
    zacni = threading.Barrier(4)

    def klik():
        zacni.wait()
        izidi.append(up.preveri_ponudnika(lokalni(streznik), GESLO, kontekst=odjemalec))

    niti = [threading.Thread(target=klik) for _ in range(4)]
    for t in niti:
        t.start()
    for t in niti:
        t.join(30)
    assert sorted(izidi) == [up.PREPOGOSTO] * 3 + [up.VELJA]
    assert streznik.n("povezav") == 1


# ------------------------------------------------------------------ bazen

def test_bazen_trda_meja(izolacija, streznik, odjemalec):
    p = lokalni(streznik, najvec_povezav=2)
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    bazen = up.ustvari_bazen(p, kontekst=odjemalec)
    assert bazen.najvec == 2
    bazen.nastavi_najvec(50)
    assert bazen.najvec == 2
    niti = [threading.Thread(target=bazen.stat, args=("<c%d@primer.invalid>" % i,)) for i in range(8)]
    for t in niti:
        t.start()
    for t in niti:
        t.join(30)
    bazen.zapri()
    assert streznik.n("stat") == 8
    assert streznik.najvec_hkrati <= 2
    assert GESLO not in repr(bazen) and UPORABNIK not in repr(bazen)


def test_bazen_ne_cez_mejo_modula(izolacija):
    p = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK, najvec_povezav=100)
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    b = up.ustvari_bazen(p)
    assert b.najvec == nntp.NAJVEC_POVEZAV
    b.zapri()
    assert izolacija["poskusi"] == []  # tovarna ne odpira povezav


def test_bazen_brez_gesla(izolacija):
    p = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK)
    with pytest.raises(up.NapakaPonudnika) as e:
        up.ustvari_bazen(p)
    assert e.value.razlog == up.NI_GESLA and izolacija["poskusi"] == []


# ------------------------------------------------------------------ pozabi in vmesnik

def test_pozabi_zbrise_geslo_in_zapah(izolacija, streznik, odjemalec):
    p = lokalni(streznik)
    up.shrani_ponudnika(p, NAPACNO, izolacija["pot"])
    assert preveri(izolacija, streznik, odjemalec, NAPACNO) == up.NE_VELJA
    assert nntp.prijava_zavrnjena("127.0.0.1", UPORABNIK, NAPACNO)
    up.pozabi_ponudnika(izolacija["pot"])
    assert izolacija["zbirka"].vnosi == {} and not os.path.exists(izolacija["pot"])
    assert not nntp.prijava_zavrnjena("127.0.0.1", UPORABNIK, NAPACNO)
    zapah = os.path.join(izolacija["mapa"], "stanje", "usenet-zapah")
    assert nntp._zapahi_racuna(nntp._beri_zapahe(zapah), "127.0.0.1", UPORABNIK) == []
    s = up.stanje_za_vmesnik(izolacija["pot"])
    assert s["vpisan"] is False and s["usenet_viden"] is False
    up.pozabi_ponudnika(izolacija["pot"])  # drugic brez napake


def test_stanje_za_vmesnik_brez_skrivnosti(izolacija):
    s = up.stanje_za_vmesnik(izolacija["pot"])
    assert s["vpisan"] is False and s["usenet_viden"] is False and s["besedilo"]
    p = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik=UPORABNIK, ime="Doma", najvec_povezav=20)
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    s = up.stanje_za_vmesnik(izolacija["pot"])
    assert s == {"vpisan": True, "usenet_viden": True, "ime": "Doma", "gostitelj": "news.primer.invalid",
                 "vrata": 563, "tls": True, "najvec_povezav": 20, "geslo_shranjeno": True,
                 "stanje": up.NEPREVERJEN, "besedilo": s["besedilo"]}
    besedilo = json.dumps(s, ensure_ascii=False)
    assert GESLO not in besedilo and UPORABNIK not in besedilo
    izolacija["zbirka"].vnosi.clear()
    s = up.stanje_za_vmesnik(izolacija["pot"])
    assert s["geslo_shranjeno"] is False and s["besedilo"] == up._BESEDILA[up.NI_GESLA]


def test_geslo_in_uporabnik_nikjer(izolacija, streznik, odjemalec, caplog):
    caplog.set_level(logging.DEBUG)
    p = lokalni(streznik)
    izhodi = [repr(p), str(p)]
    up.shrani_ponudnika(p, NAPACNO, izolacija["pot"])
    izhodi.append(preveri(izolacija, streznik, odjemalec, NAPACNO))
    izolacija["ura"][0] += 120
    izhodi.append(preveri(izolacija, streznik, odjemalec, NAPACNO))
    for slabo in (GESLO + "\r\nQUIT", GESLO + "\x00"):
        try:
            up.shrani_ponudnika(p, slabo, izolacija["pot"])
        except ValueError as e:
            izhodi += [str(e), repr(e), repr(e.args), str(e.__context__), str(e.__cause__)]
    try:
        up.Ponudnik(gostitelj="127.0.0.1", uporabnik=UPORABNIK + "\r\n")
    except ValueError as e:
        izhodi += [str(e), repr(e)]
    for napaka in (lambda: up.ustvari_bazen(p, kontekst=odjemalec),):
        try:
            napaka()
        except up.NapakaPonudnika as e:
            izhodi += [str(e), repr(e)]
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    izhodi.append(preveri(izolacija, streznik, odjemalec))
    izhodi.append(json.dumps(up.stanje_za_vmesnik(izolacija["pot"]), ensure_ascii=False))
    izhodi.append(caplog.text)
    vse = "\n".join(izhodi)
    for skrivnost in (GESLO, NAPACNO, UPORABNIK):
        assert skrivnost not in vse
    # Datoteke: gesla ni nikjer; uporabnik je samo v nastavitvah (0600), ki ga potrebujejo za prijavo.
    for koren, _, datoteke in os.walk(izolacija["mapa"]):
        for d in datoteke:
            pot = os.path.join(koren, d)
            vsebina = open(pot, "rb").read()
            assert GESLO.encode() not in vsebina and NAPACNO.encode() not in vsebina
            if pot != izolacija["pot"]:
                assert UPORABNIK.encode() not in vsebina
    assert "usenet ponudnik: preverba" in caplog.text  # dnevnik je bil res zajet
    # Streznik je geslo res prejel (sicer bi bil preizkus prazen).
    assert any(GESLO in v for v in streznik.prejeto)


# ------------------------------------------------------------------ naloga 116: zavrnitev ne tece med nastavitvami

def test_zavrnitev_ne_tece_v_druge_nastavitve(izolacija, streznik, odjemalec):
    # Odtis zavrnjenega gesla (G1) je bil za ves proces: naslednji preizkus z istim racunom in svezimi nastavitvami
    # je dobil GESLO_ZAVRNJENO/ZAKLENJEN brez omrezja (CI 40454036242, hitra-vrata 3).
    p = lokalni(streznik)
    up.shrani_ponudnika(p, NAPACNO, izolacija["pot"])
    assert preveri(izolacija, streznik, odjemalec, NAPACNO) == up.NE_VELJA
    # Kot nov preizkus: druga shramba zapaha, prazen pomnilnik procesa, druge nastavitve.
    nntp.nastavi_shrambo_zapaha(str(izolacija["mapa"] / "stanje2" / "usenet-zapah"))
    for m in (nntp._ZAVRNJENI, nntp._NEZNANE, up._PREVERBE):
        m.clear()
    druga = str(izolacija["mapa"] / "nast2" / "usenet.json")
    up.shrani_ponudnika(p, NAPACNO, druga)
    assert v_niti(up.preveri_ponudnika, p, NAPACNO, pot_nastavitev=druga, kontekst=odjemalec) == up.NE_VELJA
    assert streznik.n("pass") == 2
    with pytest.raises(up.NapakaPonudnika) as e:  # v prvih nastavitvah zavrnitev ostane
        up.shrani_ponudnika(p, NAPACNO, izolacija["pot"])
    assert e.value.razlog == up.GESLO_ZAVRNJENO


def test_ziv_bazen_s_prostim_mestom_ne_ovira_preverbe(izolacija, streznik, odjemalec):
    p = lokalni(streznik, najvec_povezav=2)
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    bazen = up.ustvari_bazen(p, kontekst=odjemalec)
    assert v_niti(bazen.stat, "<n116@primer.invalid>") is True  # ena prosta povezava ostane odprta
    assert preveri(izolacija, streznik, odjemalec) == up.VELJA
    assert streznik.najvec_hkrati <= 2
    bazen.zapri()


def test_poln_bazen_preverba_v_uporabi(izolacija, streznik, odjemalec):
    p = lokalni(streznik, najvec_povezav=1)
    up.shrani_ponudnika(p, GESLO, izolacija["pot"])
    bazen = up.ustvari_bazen(p, kontekst=odjemalec)
    assert v_niti(bazen.stat, "<n116@primer.invalid>") is True
    assert preveri(izolacija, streznik, odjemalec) == up.V_UPORABI
    assert streznik.najvec_hkrati == 1 and streznik.n("pass") == 1
    bazen.zapri()

"""Neodvisen pregled 118 (27. 10. 2026, Linux 1.0.133): popravki najdb S1, N1, N2 in N3.

Vsak preizkus brez popravka pade (PoC pregledovalca: pomocnik-win/izhod/pregled-118/test_poc_118.py je iste napake
pokazal z izvajanjem).
"""
from __future__ import annotations

import http.client
import socket
import threading
import time
import types

import pytest

from core import usenet_ponudnik as up, usenet_streznik as us, usenet_vezava as uv, viri_sink
import test_usenet_nntp as TN
from test_usenet_vezava import iz, potrdila, kontekst, vnos, v_niti, GESLO  # noqa: F401 - pritrdila

MiB = 1024 * 1024


def _zapis(gostitelj, vrata=563):
    return {"gostitelj": gostitelj, "uporabnik": "u", "vrata": vrata, "tls": True, "najvec_povezav": 4, "ime": "Moj ponudnik"}


# ---------------------------------------------------------------- S1: ponudnik iz kroga samo v javni internet
@pytest.mark.parametrize("gostitelj", ["192.168.1.1", "10.0.0.5", "172.16.3.4", "127.0.0.1", "169.254.1.1", "[fe80::1]",
                                       "::1", "localhost", "nas.local", "nas", "streznik.lan", "x.home.arpa", "100.64.0.1"])
def test_s1_domace_omrezje_iz_kroga_zavrnjeno(gostitelj):
    assert viri_sink.cist_usenet(_zapis(gostitelj)) is None


@pytest.mark.parametrize("gostitelj", ["news.eweka.nl", "reader.example.com", "8.8.8.8", "2001:4860:4860::8888"])
def test_s1_javni_ponudnik_ostane(gostitelj):
    assert viri_sink.cist_usenet(_zapis(gostitelj)) is not None


def test_s1_vezava_ne_sprejme_domacega_naslova(iz):
    v = uv.Vezava(iz.pot)
    assert v.prejmi_iz_kroga(_zapis("192.168.1.1", 80), True) is False
    assert up.preberi_ponudnika(iz.pot) is None


# ---------------------------------------------------------------- N3: »Pozabi« velja tudi za uskladitev iz kroga
def test_n3_pozabljen_ponudnik_se_iz_kroga_ne_vrne(iz):
    v = uv.Vezava(iz.pot)
    z = _zapis("news.eweka.nl")
    assert v.prejmi_iz_kroga(z, True) is True
    uv.most(v, ["odstrani"])
    assert up.preberi_ponudnika(iz.pot) is None
    assert v.prejmi_iz_kroga(z, True) is False
    # Drug racun z druge naprave se se vedno sprejme.
    assert v.prejmi_iz_kroga(_zapis("reader.example.com"), True) is True


# ---------------------------------------------------------------- N1: »Pozabi« med pripravo filma
def test_n1_pozabi_med_pripravo_ustavi_film_in_bazen(iz, potrdila, kontekst, monkeypatch):
    from unittest import mock
    from core import usenet_bralnik
    import usenet_gradnja as G
    film = G.Leno(2 * MiB + 5, 118)
    o = G.Objava(700 * 1024)
    o.dodaj("Film.mkv", film)
    with mock.patch.object(TN, "CLANKI", o):
        srv = TN.LazniStreznik(potrdila, rok_posiljanja=10.0)
        v = uv.Vezava(iz.pot, kontekst=kontekst)
        try:
            assert uv.most(v, ["shrani", vnos(srv.vrata), GESLO])["ok"]
            prava = usenet_bralnik.pripravi
            niti = []

            def pripravi_in_klik_pozabi(*a, **k):
                izid = prava(*a, **k)
                t = threading.Thread(target=lambda: uv.most(v, ["odstrani"]))
                t.start()          # uporabnik klikne »Pozabi« med pripravo (druga nit mostu)
                niti.append(t)
                return izid

            monkeypatch.setattr(usenet_bralnik, "pripravi", pripravi_in_klik_pozabi)
            v_niti(v.predvajaj, o.nzb(), "Film")
            niti[0].join(15)
            assert not niti[0].is_alive()
            assert up.preberi_ponudnika(iz.pot) is None
            assert v.predvaja() == 0                      # film po »Pozabi« ne tece vec
            konec = time.monotonic() + 3
            while up._RACUNI and time.monotonic() < konec:
                time.sleep(0.05)
            assert not up._RACUNI                         # bazen s poverilnicami pozabljenega racuna je zaprt
        finally:
            v.ustavi_predvajanje()
            srv.ustavi()


# ---------------------------------------------------------------- N2: prazne povezave brez zetona ne zasedejo mest
class _Bralnik:
    def __init__(self, n):
        self.vir = types.SimpleNamespace(velikost=n, ime="Film.mkv")

    def beri(self, odmik, n):
        return bytes((odmik + i) % 251 for i in range(n))

    def zapri(self):
        pass


def test_n2_prazne_povezave_brez_zetona_kmalu_sprostijo_mesta(monkeypatch):
    monkeypatch.setattr(us, "ROK_PRVE_ZAHTEVE_S", 0.5)
    s = us.Streznik(_Bralnik(MiB), "Film.mkv")
    vticnice = []
    try:
        for _ in range(us.NAJVEC_POVEZAV):
            vticnice.append(socket.create_connection(("127.0.0.1", s.vrata)))   # nic ne poslje
        time.sleep(1.5)                                   # rok prve zahteve je potekel: mesta so prosta
        c = http.client.HTTPConnection("127.0.0.1", s.vrata, timeout=5)
        c.request("GET", "/%s/%s" % (s.zeton, s.pot), headers={"Range": "bytes=0-9"})
        r = c.getresponse()
        assert r.status == 206 and r.read() == bytes(range(10))
        c.close()
    finally:
        for x in vticnice:
            x.close()
        s.zapri()

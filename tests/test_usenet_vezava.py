"""Vezava lastnega ponudnika Usenet v Safeer OS za Linux (naloga 114, core/usenet_vezava.py).

Okno »Moji viri -> Usenet ponudnik« (most mediaUsenetPonudnik), predvajanje NZB prek lastnega pogona
(usenet_streznik na 127.0.0.1 z zetonom) in ponudnik samo v ozjem krogu naprav - brez gesla. Brez pravega omrezja:
lazni streznik NNTP prek TLS na 127.0.0.1 (tests/test_usenet_nntp.py), lazna zbirka skrivnosti, varovalo zavrne vsako
povezavo izven 127.0.0.1. Poverilnice in imena so izmisljena.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import os
import re
import shutil
import socket
import tempfile
import threading
import types
from pathlib import Path
from unittest import mock

import pytest

from core import debrid, os_media, usenet_nntp as nntp, usenet_ponudnik as up, viri_sink
from core import usenet_vezava as uv

KOREN = Path(__file__).resolve().parent.parent

import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))  # usenet_gradnja, test_usenet_nntp (pomoc preizkusov)
import test_usenet_nntp as TN  # noqa: E402
import usenet_gradnja as G  # noqa: E402

GESLO = TN.GESLO
UPORABNIK = TN.UPORABNIK
NAPACNO = "napacno-geslo-114-Zq"
MiB = 1024 * 1024


class LaznaZbirka:
    def __init__(self):
        self.vnosi: dict = {}

    def shrani(self, kljuc, vrednost):
        self.vnosi[kljuc] = vrednost
        return True

    def preberi(self, kljuc):
        return self.vnosi.get(kljuc)

    def pozabi(self, kljuc):
        self.vnosi.pop(kljuc, None)


def _pocisti():
    for m in (nntp._ZAVRNJENI, nntp._NEZNANE, up._PREVERBE, up._V_POMNILNIKU, up._ZAVRNJENA, up._RACUNI, uv._VEZAVE):
        m.clear()


@pytest.fixture(autouse=True)
def iz(monkeypatch, tmp_path):
    zbirka = LaznaZbirka()
    monkeypatch.setattr(up, "skrivnosti", zbirka)
    nntp.nastavi_shrambo_zapaha(str(tmp_path / "stanje" / "usenet-zapah"))
    _pocisti()
    ura = [1000.0]
    monkeypatch.setattr(up, "_ura", lambda: ura[0])
    poskusi: list = []
    prava_povezi = socket.socket.connect

    def varna_povezi(self, naslov):
        poskusi.append(naslov)
        if not (isinstance(naslov, tuple) and ipaddress.ip_address(naslov[0]).is_loopback):
            raise AssertionError("preizkus: povezava izven 127.0.0.1 ni dovoljena")
        return prava_povezi(self, naslov)

    monkeypatch.setattr(socket.socket, "connect", varna_povezi)
    mapa = tmp_path / "media"
    mapa.mkdir()
    yield types.SimpleNamespace(zbirka=zbirka, ura=ura, poskusi=poskusi, mapa=mapa, koren=tmp_path,
                                pot=str(mapa / uv.IME_DATOTEKE))
    for v in list(uv._VEZAVE.values()):
        v.ustavi_predvajanje()
    _pocisti()
    nntp.nastavi_shrambo_zapaha(None)


@pytest.fixture(scope="module")
def potrdila():
    if not shutil.which("openssl"):
        pytest.skip("brez openssl ni laznega streznika NNTP")
    d = tempfile.TemporaryDirectory()
    TN.ustvari_potrdila(d.name)
    yield d.name
    d.cleanup()


@pytest.fixture
def kontekst(potrdila):
    import ssl
    return ssl.create_default_context(cafile=os.path.join(potrdila, "ca.pem"))   # preverba potrdila ostane vklopljena


def v_niti(fn, *a, **k):
    izid: dict = {}

    def delo():
        try:
            izid["v"] = fn(*a, **k)
        except BaseException as e:  # noqa: BLE001
            izid["e"] = e

    t = threading.Thread(target=delo)
    t.start()
    t.join(60)
    assert not t.is_alive(), "preizkus: nit visi"
    if "e" in izid:
        raise izid["e"]
    return izid["v"]


def vnos(vrata=563, **k):
    return dict({"ime": "Moj ponudnik", "gostitelj": "127.0.0.1", "vrata": str(vrata), "tls": True,
                 "najvec_povezav": "4", "uporabnik": UPORABNIK}, **k)


def vse_datoteke(koren: Path) -> str:
    return "\n".join(p.read_bytes().decode("utf-8", "replace") for p in koren.rglob("*") if p.is_file())


# ------------------------------------------------------------------ okno: stanje, shrani, preveri, odstrani

def test_most_stanje_ni_vpisan(iz):
    r = uv.most(uv.Vezava(iz.pot), ["stanje"])
    assert r["ok"] is True and r["stanje"]["vpisan"] is False and r["stanje"]["kljuc"] == "ni_vpisan"
    assert "besedilo" not in r["stanje"] and "uporabnik" not in r["stanje"]
    assert uv.most(uv.Vezava(iz.pot), ["neznano"]) == {"ok": False, "koda": "n_vnos"}
    assert uv.most(uv.Vezava(iz.pot), "smeti") == {"ok": False, "koda": "n_vnos"}


def test_shrani_geslo_samo_v_zbirki_nikoli_na_stran_v_datoteko_ali_dnevnik(iz, caplog):
    caplog.set_level("DEBUG")
    v = uv.Vezava(iz.pot)
    r = uv.most(v, ["shrani", vnos(), GESLO])
    assert (r["ok"], r["koda"]) == (True, "shranjeno")
    s = r["stanje"]
    assert (s["vpisan"], s["geslo_shranjeno"], s["kljuc"], s["vrata"], s["najvec_povezav"]) == (True, True, "nepreverjen", 563, 4)
    assert GESLO in iz.zbirka.vnosi.values()                         # geslo samo v sistemski zbirki
    odgovor = json.dumps(r) + json.dumps(uv.most(v, ["stanje"]))
    for zasebno in (GESLO, UPORABNIK):
        assert zasebno not in odgovor                                # stran ne dobi ne gesla ne uporabnika
        assert zasebno not in caplog.text
        assert zasebno not in repr(v)
    assert GESLO not in vse_datoteke(iz.koren)


@pytest.mark.parametrize("sprememba, koda", [
    ({"gostitelj": "http://127.0.0.1"}, "n_gostitelj"), ({"gostitelj": "news primer"}, "n_gostitelj"),
    ({"vrata": "0"}, "n_vrata"), ({"vrata": "abc"}, "n_vrata"), ({"vrata": "9" * 40}, "n_vrata"),
    ({"najvec_povezav": "0"}, "n_povezav"), ({"najvec_povezav": "101"}, "n_povezav"),
    ({"ime": "x" * 81}, "n_ime"), ({"ime": 5}, "n_ime"), ({"uporabnik": "a\r\nb"}, "n_uporabnik"),
    ({"tls": False}, "n_brez_tls"), ({"tls": False, "nevarno_brez_tls": True, "gostitelj": "news.primer.invalid"}, "n_brez_tls_doma"),
    ({"tls": "da"}, "n_vnos"),
])
def test_napacen_vnos_je_koda_brez_vrednosti(iz, sprememba, koda):
    r = uv.most(uv.Vezava(iz.pot), ["shrani", vnos(**sprememba), GESLO])
    assert (r["ok"], r["koda"]) == (False, koda)
    assert GESLO not in json.dumps(r) and "news primer" not in json.dumps(r)
    assert not os.path.exists(iz.pot)


def test_brez_gesla_samo_ime_in_povezave(iz):
    v = uv.Vezava(iz.pot)
    assert uv.most(v, ["shrani", vnos(), ""])["koda"] == "n_geslo"        # nov vpis brez gesla ne gre
    assert uv.most(v, ["shrani", vnos(), GESLO])["ok"]
    r = uv.most(v, ["shrani", vnos(ime="Drugo ime", najvec_povezav="2", uporabnik=""), ""])
    assert (r["ok"], r["koda"], r["stanje"]["ime"], r["stanje"]["najvec_povezav"]) == (True, "posodobljeno", "Drugo ime", 2)
    assert r["stanje"]["geslo_shranjeno"] is True                       # prazno geslo ne zbrise shranjenega
    for drugo in ({"gostitelj": "127.0.0.2"}, {"vrata": "119"}, {"uporabnik": "drug.uporabnik"}):
        r = uv.most(v, ["shrani", vnos(**drugo), ""])
        assert (r["ok"], r["koda"]) == (False, "geslo_za_spremembo")
    assert up.preberi_ponudnika(iz.pot).gostitelj == "127.0.0.1"


def test_preveri_na_glavni_niti_zavrnjena_brez_omrezja(iz):
    v = uv.Vezava(iz.pot)
    uv.most(v, ["shrani", vnos(), GESLO])
    r = uv.most(v, ["preveri"])
    assert (r["ok"], r["koda"]) == (False, "glavna_nit")
    assert iz.poskusi == []
    r = v_niti(uv.most, uv.Vezava(str(iz.mapa / "drugo.json")), ["preveri"])
    assert r["koda"] == "ni_ponudnika"


def test_preveri_prek_tls_velja_zavrnitev_zapah_in_1_na_minuto(iz, potrdila, kontekst):
    srv = TN.LazniStreznik(potrdila)
    try:
        v = uv.Vezava(iz.pot, kontekst=kontekst)
        assert uv.most(v, ["shrani", vnos(srv.vrata), GESLO])["ok"]
        r = v_niti(uv.most, v, ["preveri"])
        assert (r["ok"], r["koda"], r["stanje"]["kljuc"]) == (True, "velja", "velja")
        r = v_niti(uv.most, v, ["preveri"])
        assert r["koda"] == "prepogosto"                                 # najvec 1/min na racun
        iz.ura[0] += 120
        assert uv.most(v, ["shrani", vnos(srv.vrata), NAPACNO])["ok"]
        r = v_niti(uv.most, v, ["preveri"])
        assert (r["ok"], r["koda"], r["stanje"]["kljuc"]) == (False, "ne_velja", "ne_velja")
        pass_pred = sum(1 for u in srv.ukazi if str(u).startswith("AUTHINFO PASS"))
        iz.ura[0] += 120
        r = v_niti(uv.most, v, ["preveri"])
        assert r["ok"] is False and r["koda"] in ("racun_zaklenjen", "ne_velja", "zaklenjen", "geslo_ze_zavrnjeno")
        assert sum(1 for u in srv.ukazi if str(u).startswith("AUTHINFO PASS")) == pass_pred   # zapah: gesla ne posljemo
        assert NAPACNO not in json.dumps(r) and GESLO not in json.dumps(r)
    finally:
        srv.ustavi()


def test_preveri_z_nevarnim_kontekstom_zavrnjena_pred_omrezjem(iz):
    import ssl
    k = ssl.create_default_context()
    k.check_hostname = False
    k.verify_mode = ssl.CERT_NONE
    v = uv.Vezava(iz.pot, kontekst=k)
    uv.most(v, ["shrani", vnos(), GESLO])
    assert v_niti(uv.most, v, ["preveri"])["koda"] == "tls_preverba"
    assert iz.poskusi == []


def test_odstrani_zbrise_ponudnika_in_geslo(iz):
    v = uv.Vezava(iz.pot)
    klici = []
    v.ob_spremembi = lambda: klici.append(1)
    uv.most(v, ["shrani", vnos(), GESLO])
    r = uv.most(v, ["odstrani"])
    assert (r["ok"], r["koda"], r["stanje"]["kljuc"]) == (True, "odstranjeno", "ni_vpisan")
    assert iz.zbirka.vnosi == {} and up.preberi_ponudnika(iz.pot) is None
    assert klici == [1, 1]                                              # zapis za naprave po vsaki spremembi


def test_izjema_jedra_ne_gre_na_stran(iz, monkeypatch):
    def pade(*_a, **_k):
        raise RuntimeError("skrivnost " + GESLO)
    monkeypatch.setattr(up, "stanje_za_vmesnik", pade)
    r = uv.most(uv.Vezava(iz.pot), ["stanje"])
    assert r == {"ok": False, "koda": "napaka"}


# ------------------------------------------------------------------ ozji krog
#: Ponudnik v krogu mora biti v javnem internetu (pregled 118 S1); preizkusi kroga omrezja ne odprejo.
JAVNI = "news.primer.si"


def test_ponudnik_v_domacem_omrezju_ne_gre_v_krog(iz):
    v = uv.Vezava(iz.pot)
    uv.most(v, ["shrani", vnos(), GESLO])                                # 127.0.0.1 (lazni streznik)
    assert v.za_krog() is None

def test_za_krog_brez_gesla_in_samo_v_delu_ozji(iz):
    v = uv.Vezava(iz.pot)
    assert v.za_krog() is None
    uv.most(v, ["shrani", vnos(gostitelj=JAVNI), GESLO])
    z = v.za_krog()
    assert z == {"gostitelj": JAVNI, "uporabnik": UPORABNIK, "vrata": 563, "tls": True, "najvec_povezav": 4,
                 "ime": "Moj ponudnik"}
    izvoz = viri_sink.razdeli_izvoz([], {}, z)
    assert viri_sink.USENET_PONUDNIK not in izvoz                       # zgoraj (javni del) ga ni
    assert viri_sink.USENET_PONUDNIK not in viri_sink.viri_za(izvoz, False)
    assert viri_sink.viri_za(izvoz, True)[viri_sink.USENET_PONUDNIK] == z
    # Ponudnik v javnem delu (spremenjen zapis) ne gre nikomur.
    assert viri_sink.USENET_PONUDNIK not in viri_sink.viri_za(dict(izvoz, usenet_ponudnik=z), False)
    assert GESLO not in json.dumps(izvoz)


@pytest.mark.parametrize("pokvari", [
    {"geslo": GESLO}, {"tls": False}, {"vrata": True}, {"vrata": 0}, {"najvec_povezav": 500}, {"gostitelj": ""},
    {"uporabnik": "a\nb"}, {"ime": "x" * 200},
])
def test_cist_usenet_zavrne(pokvari):
    z = {"gostitelj": JAVNI, "uporabnik": UPORABNIK, "vrata": 563, "tls": True, "najvec_povezav": 4, "ime": ""}
    assert viri_sink.cist_usenet(z) == z
    assert viri_sink.cist_usenet(dict(z, **pokvari)) is None
    assert viri_sink.razdeli_izvoz([], {}, dict(z, **pokvari))["ozji"].get(viri_sink.USENET_PONUDNIK) is None


def test_control_in_medijski_center_dasta_ponudnika_samo_ozjemu_krogu(iz):
    from core import link_seznami
    mc = os_media.MediaCenter(str(iz.mapa), roots=[])
    v = uv.Vezava(iz.pot)
    mc.debrid.lastni_usenet = v
    v.ob_spremembi = mc._viri_zapisi_izvoz
    uv.most(v, ["shrani", vnos(gostitelj=JAVNI), GESLO])
    assert (iz.mapa / "viri_za_naprave.json").exists()
    for ozji in (False, True):
        izvoz = link_seznami.izvoz({}, str(iz.mapa), ozji=ozji)
        assert izvoz == mc.seznami_izvoz({}, ozji=ozji)                  # Control in jedro enako (test_link_seznami)
        assert (viri_sink.USENET_PONUDNIK in izvoz) is ozji
        assert GESLO not in json.dumps(izvoz)
    assert GESLO not in vse_datoteke(iz.koren)
    uv.most(v, ["odstrani"])
    assert viri_sink.USENET_PONUDNIK not in link_seznami.izvoz({}, str(iz.mapa), ozji=True)


def test_prejem_iz_kroga_samo_od_naprave_v_ozjem_krogu_brez_prepisa(iz):
    z = {"gostitelj": JAVNI, "uporabnik": UPORABNIK, "vrata": 563, "tls": True, "najvec_povezav": 4, "ime": "Iz kroga"}
    v = uv.Vezava(iz.pot)
    assert v.prejmi_iz_kroga(z, False) is False and up.preberi_ponudnika(iz.pot) is None
    assert v.prejmi_iz_kroga(z, "da") is False                          # samo dokaz te naprave (True)
    assert v.prejmi_iz_kroga(dict(z, geslo=GESLO), True) is False
    assert v.prejmi_iz_kroga(z, True) is True
    s = v.stanje()
    assert (s["vpisan"], s["geslo_shranjeno"], s["kljuc"], s["iz_kroga"]) == (True, False, "iz_kroga", True)
    assert v.na_voljo() is False and v.za_krog() is None                # brez gesla ne predvaja, ne gre naprej
    # Uporabnik vpise geslo na tej napravi: postane lasten ponudnik (oznaka iz_kroga izgine).
    r = uv.most(v, ["shrani", {"ime": "Iz kroga", "gostitelj": "", "vrata": "563", "tls": True, "najvec_povezav": "4",
                               "uporabnik": ""}, GESLO])
    assert r["ok"] and r["stanje"]["iz_kroga"] is False and v.za_krog() is not None
    # Lokalnega ponudnika zapis z druge naprave nikoli ne prepise.
    assert v.prejmi_iz_kroga(dict(z, gostitelj="drug.primer.si", uporabnik="drug"), True) is False
    assert up.preberi_ponudnika(iz.pot).gostitelj == JAVNI


def test_prejem_iz_kroga_ne_odklene_zapaha(iz):
    # Zapah racuna (zavrnjena prijava) je zapisan na tej napravi; zapis z druge naprave ga ne sme odstraniti.
    nntp._zapisi_zapah(nntp.ponudnik(JAVNI), UPORABNIK, GESLO)          # zapah je po ponudniku (ne gostitelju)
    assert nntp.prijava_zavrnjena(JAVNI, UPORABNIK, GESLO) is True
    z = {"gostitelj": JAVNI, "uporabnik": UPORABNIK, "vrata": 563, "tls": True, "najvec_povezav": 4, "ime": ""}
    v = uv.Vezava(iz.pot)
    assert v.prejmi_iz_kroga(z, True) is True
    assert nntp.prijava_zavrnjena(JAVNI, UPORABNIK, GESLO) is True
    assert v.na_voljo() is False


def test_uskladitev_virov_prevzame_ponudnika_samo_iz_ozjega_kroga(iz, monkeypatch):
    mc = os_media.MediaCenter(str(iz.mapa), roots=[])
    v = uv.Vezava(iz.pot)
    mc.debrid.lastni_usenet = v
    z = {"gostitelj": JAVNI, "uporabnik": UPORABNIK, "vrata": 563, "tls": True, "najvec_povezav": 4, "ime": ""}
    kazalo = {"sources": [], "sources_deleted": {}, "ozji": True, viri_sink.USENET_PONUDNIK: z}
    monkeypatch.setattr(os_media.MediaCenter, "_posiljatelj_v_ozjem_krogu", staticmethod(lambda p: False))
    assert mc.viri_uskladi(kazalo, "naprava-a") is False and up.preberi_ponudnika(iz.pot) is None
    monkeypatch.setattr(os_media.MediaCenter, "_posiljatelj_v_ozjem_krogu", staticmethod(lambda p: True))
    assert mc.viri_uskladi(dict(kazalo, ozji=False), "naprava-a") is False and up.preberi_ponudnika(iz.pot) is None
    assert mc.viri_uskladi(kazalo, "naprava-a") is True
    assert up.je_iz_kroga(iz.pot) is True


# ------------------------------------------------------------------ predvajanje prek lastnega pogona

def test_predvajaj_ne_na_glavni_niti(iz):
    assert uv.Vezava(iz.pot).predvajaj(b"<nzb/>", "x") == (None, "glavna_nit")


def _debrid_z_lastnim(v):
    d = debrid.Debrid(lambda: {}, lambda _d: None, lambda s: s, lambda s: s)
    d.lastni_usenet = v
    d.sme_klicati = lambda p: True
    d.indeksator = lambda: ("https://indeksator.primer.invalid", "k")
    return d


def test_lasten_pogon_konec_do_konca_range_na_127(iz, potrdila, kontekst):
    film = G.Leno(3 * MiB + 11, 114)
    o = G.Objava(700 * 1024)
    o.dodaj("Film.Ime.Izdaje.mkv", film)
    with mock.patch.object(TN, "CLANKI", o):
        srv = TN.LazniStreznik(potrdila, rok_posiljanja=10.0)
        try:
            v = uv.Vezava(iz.pot, kontekst=kontekst)
            assert uv.most(v, ["shrani", vnos(srv.vrata), GESLO])["ok"]
            d = _debrid_z_lastnim(v)
            assert d.usenet_na_voljo() is True                         # brez TorBoxa: lasten ponudnik je dovolj
            d._nzb_toka = lambda id_toka, ponudnik: (o.nzb(), None)
            izid = v_niti(d.usenet_tok, "usenet:1", "Film.Ime.Izdaje", lastni=True)
            assert izid.ponudnik == debrid.LASTNI_USENET and not izid.napaka and izid.url
            assert re.match(r"^http://127\.0\.0\.1:\d+/[A-Za-z0-9_-]{40,}/", izid.url)
            for zasebno in (GESLO, UPORABNIK, "Ime.Izdaje", "primer.invalid"):
                assert zasebno not in izid.url
            vrata = int(izid.url.split(":")[2].split("/")[0])
            pot = izid.url.split(str(vrata), 1)[1]
            c = http.client.HTTPConnection("127.0.0.1", vrata, timeout=20)
            c.request("GET", pot, headers={"Range": "bytes=1000-200999"})
            r = c.getresponse()
            assert (r.status, r.read()) == (206, film.beri(1000, 200000))
            c.close()
            c = http.client.HTTPConnection("127.0.0.1", vrata, timeout=20)
            c.request("GET", "/napacen-zeton/video.mkv")
            assert c.getresponse().status in (403, 404)                   # brez zetona nic
            c.close()
            assert v.predvaja() == 1
            # Drugi film: prejsnji streznik se zapre (en film naenkrat), bazen racuna ostane eden.
            izid2 = v_niti(d.usenet_tok, "usenet:2", "Drugi", lastni=True)
            assert izid2.url and izid2.url != izid.url and v.predvaja() == 1
            # »Pozabi ponudnika« ustavi predvajanje in zapre bazen.
            uv.most(v, ["odstrani"])
            assert v.predvaja() == 0
            assert up._RACUNI == {} or all(x.get("bazen") is None for x in up._RACUNI.values())
        finally:
            srv.ustavi()


def test_napaka_pogona_je_koda_brez_imen(iz, potrdila, kontekst):
    v = uv.Vezava(iz.pot, kontekst=kontekst)
    srv = TN.LazniStreznik(potrdila)
    try:
        uv.most(v, ["shrani", vnos(srv.vrata), GESLO])
        url, koda = v_niti(v.predvajaj, b"<nzb>pokvarjeno", "Skrivno.Ime")
        assert url is None and koda.startswith(uv.PREDPONA_POGONA) and "Skrivno" not in koda
        d = _debrid_z_lastnim(v)
        d._nzb_toka = lambda id_toka, ponudnik: (b"<nzb>pokvarjeno", None)
        izid = v_niti(d.usenet_tok, "usenet:1", "Skrivno.Ime", lastni=True)
        assert (izid.url, izid.napaka, izid.ponudnik) == (None, debrid.NAPAKA_LASTNI_POGON, debrid.LASTNI_USENET)
    finally:
        srv.ustavi()


def test_torbox_pot_ne_odpre_lastnega_pogona(iz):
    klici = []
    lastni = types.SimpleNamespace(na_voljo=lambda: True, predvajaj=lambda *a: klici.append(a) or ("http://127.0.0.1:1/z/video.mkv", ""))
    d = _debrid_z_lastnim(lastni)
    d._nzb_toka = lambda id_toka, ponudnik: (b"<nzb/>", None)
    izid = d.usenet_tok("usenet:1", "x", lastni=False)
    assert klici == [] and izid.ponudnik == debrid.P.TORBOX
    izid = d.usenet_tok("usenet:1", "x", samo_takoj=True)               # vzporedna preverba »pripravljen« (usenet_takoj)
    assert izid.ponudnik == debrid.P.TORBOX and klici == []
    assert d.usenet_tok("usenet:1", "x").ponudnik == debrid.LASTNI_USENET and len(klici) == 1
    lastni.na_voljo = lambda: False
    assert d.lastni_usenet_na_voljo() is False


def test_medijski_center_najprej_lasten_pogon_z_oznako_nntp(iz):
    mc = os_media.MediaCenter(str(iz.mapa), roots=[])
    klici = []

    def tok(url, naslov, **k):
        klici.append(k.get("lastni"))
        return debrid.Izid(url="http://127.0.0.1:5/z/video.mkv", ponudnik=debrid.LASTNI_USENET)

    mc.debrid.lastni_usenet = types.SimpleNamespace(na_voljo=lambda: True)
    mc.debrid.usenet_tok = tok
    mc.debrid.usenet_takoj = lambda *a: pytest.fail("TorBox »pripravljen« ni potreben z lastnim pogonom")
    mc._usenet_zadetki = lambda *a, **k: [{"url": "usenet:1", "naslov": "Film", "gb": 4.0, "opis": "1080p"}]
    r = mc._razresi_usenet_takoj("id1", {"naslov": "Film"}, "tt0000001", [])
    assert r["url"].startswith("http://127.0.0.1:") and r["razlicice"][0]["vir"] == "Usenet · NNTP"
    assert klici == [True]
    mc._usenet_mogoc = lambda *a: True
    mc._razresi_usenet("id1", {"naslov": "Film"}, "movie", "tt0000001", [])
    assert klici[-1] is False                                           # korak s cakanjem: samo TorBox


# ------------------------------------------------------------------ most, vmesnik, tovor

def test_katalog_most_in_ista_vezava_za_predvajanje(iz):
    from core import os_katalog as K
    kat = K.Katalog(str(iz.mapa), lambda *_: None, lambda f: f(), *(lambda *a, **k: True,) * 4)
    assert kat.pozna("mediaUsenetPonudnik")
    r = v_niti(kat.izvedi, "mediaUsenetPonudnik", ["stanje"])
    assert r["stanje"]["kljuc"] == "ni_vpisan"
    assert kat.mc.debrid.lastni_usenet is uv.za_pot(iz.pot)
    assert kat.mc.debrid.lastni_usenet.ob_spremembi == kat.mc._viri_zapisi_izvoz


def test_safeer_os_klic_mostu_po_preverbi_zetona_v_delovni_niti():
    src = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
    zeton = src.index("zeton_velja")
    katalog = src.index("if self._katalog_most().pozna(metoda):")
    assert zeton < katalog
    vejitev = src[katalog:katalog + 1500]
    assert "threading.Thread(target=delo_katalog" in vejitev           # nikoli na glavni niti
    assert "mediaUsenetPonudnik" in src


def _bloki():
    besedila = (KOREN / "assets" / "os" / "besedila.js").read_text(encoding="utf-8")
    return re.findall(r"Object\.assign\(BESEDILA_OS\.(\w\w), (\{\"unpNaslov\".*?\})\);", besedila)


def test_besedila_v_6_jezikih_brez_dvopicja_na_koncu():
    bloki = _bloki()
    assert [j for j, _ in bloki] == ["sl", "en", "de", "es", "fr", "it"]
    kljuci = [set(json.loads(b)) for _, b in bloki]
    assert all(k == kljuci[0] for k in kljuci)
    for _, b in bloki:
        for k, vrednost in json.loads(b).items():
            assert vrednost.strip() and not vrednost.rstrip().endswith(":"), k
    os_js = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
    html = (KOREN / "assets" / "os" / "index.html").read_text(encoding="utf-8")
    uporabljeni = set(re.findall(r't\("(unp[A-Z]\w*)"\s*[,)]', os_js)) | set(re.findall(r'data-(?:t|ph)="(unp\w+)"', html))
    assert uporabljeni and uporabljeni <= kljuci[0], uporabljeni - kljuci[0]
    # Vsaka koda, ki jo vezava vrne strani, ima besedilo (»unpKoda_« + koda).
    assert {"unpKoda_" + k for k in uv.KODE} <= kljuci[0]
    assert re.search(r'id="slojKatViri".*id="unpSekcija".*id="katViriZapri"', html, re.S)   # okno Moji viri
    assert 'id="unpGeslo" type="password"' in html and 'id="unpSporocilo" role="status" aria-live="polite"' in html
    assert "news.example" not in html and "news.example" not in os_js


def test_slog_brez_lastnih_barv():
    css = (KOREN / "assets" / "os" / "katalog.css").read_text(encoding="utf-8")
    unp = "\n".join(v for v in css.splitlines() if ".unp-" in v)
    assert unp and not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", unp)
    tokens = (KOREN / "assets" / "os" / "tokens.css").read_text(encoding="utf-8")
    for spremenljivka in set(re.findall(r"var\((--[\w-]+)\)", unp)):
        assert spremenljivka + ":" in tokens, spremenljivka


def test_tovor_vsebuje_nova_modula():
    s = (KOREN / "packaging" / "install_os_payload.sh").read_text(encoding="utf-8")
    m = re.search(r"for modul in (.*?); do", s, re.S)
    moduli = set(m.group(1).replace("\\\n", " ").split())
    assert {"usenet_ponudnik", "usenet_vezava", "usenet_bralnik", "usenet_streznik"} <= moduli

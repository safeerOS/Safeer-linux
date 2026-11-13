"""Preskok uvoda in odjavne (lastnik 13. 11. 2026): ista pravila kot TV (PreskokPravilaTest.kt)."""
import pytest

from core import preskok_odsekov as P

BB = '{"tvdb_id":81189,"type":"tv","season":1,"episode":2,"intro":[{"start_ms":314551,"end_ms":331127}],"credits":[{"start_ms":2848149,"end_ms":null}]}'
TR = 2900.0


def test_naslov():
    assert P.naslov(1396, "", 1, 2) == "https://api.theintrodb.org/v4/media?tmdb_id=1396&season=1&episode=2"
    assert P.naslov(0, "tt0133093") == "https://api.theintrodb.org/v4/media?imdb_id=tt0133093"
    assert P.naslov(0, "tt0133093&x=1") is None
    assert P.naslov(1396, "", 1, 0) is None          # sezona brez epizode
    assert P.naslov(1396, "", -1, 2) is None
    assert P.naslov(True, "", 1, 2) is None           # bool ni id
    assert P.naslov(0, "") is None
    assert P.iz_kljuca("tmdb:tv:1396:1:2") == P.naslov(1396, "", 1, 2)
    assert P.iz_kljuca("tmdb:film:603") == P.naslov(603)
    assert P.iz_kljuca("tmdb:tv:1396:1:2&x") is None
    assert P.iz_kljuca("file:///film.mkv") is None


def test_razcleni():
    o = P.razcleni(BB)
    assert o == [P.Odsek("uvod", 314.551, 331.127), P.Odsek("odjavna", 2848.149, None)]
    assert P.razcleni('{"intro":[{"start_ms":null,"end_ms":40000}]}')[0].od == 0.0
    assert P.razcleni('{"intro":[{"start_ms":1000,"end_ms":null}]}') == []
    assert P.razcleni('{"recap":[{"start_ms":5000,"end_ms":4000}]}') == []
    assert P.razcleni('{"intro":[{"start_ms":-5,"end_ms":40000}]}') == []
    assert P.razcleni('{"intro":[{"start_ms":0,"end_ms":99999999999}]}') == []
    assert P.razcleni('{"intro":[{"start_ms":"0","end_ms":40000}]}') == []
    assert P.razcleni('{"error":"Invalid imdb_id format"}') == []
    assert P.razcleni("ni json") == []
    assert P.razcleni('{"intro":[{"start_ms":0,"end_ms":40000}]}' + " " * P.NAJVEC_BAJTOV) == []


def test_aktiven_in_cilj():
    o = P.razcleni(BB)
    assert P.aktiven(o, 300, TR) is None
    assert P.aktiven(o, 320, TR).vrsta == "uvod"
    assert P.aktiven(o, 331.127 - 1.5, TR) is None
    assert P.aktiven(o, 2860, TR).vrsta == "odjavna"
    assert P.aktiven(o, 2860, 0) is None
    assert P.cilj(o[0], TR) == pytest.approx(331.127)
    assert P.cilj(o[1], TR) == TR - 1.0


def test_pokvarjeni_vnosi_ne_zasedejo_gumba():
    assert P.aktiven([P.Odsek("uvod", 0, 86400)], 60, TR) is None
    assert P.aktiven([P.Odsek("uvod", 0, 360)], 60, TR) is None
    assert P.aktiven([P.Odsek("uvod", 2700, 2760)], 2710, 7200) is None
    assert P.smiseln(P.Odsek("uvod", 1800, 1860), 7200)
    assert P.aktiven([P.Odsek("odjavna", 0, None)], 60, TR) is None
    assert not P.smiseln(P.Odsek("odjavna", 2000, 2100), 0)


def test_gumb_viden_15_s():
    assert P.gumb_viden(1.0, 15.0)
    assert not P.gumb_viden(1.0, 16.0)


# ---- omrezje: nadomestna vticnica in TLS (nic ne gre na internet)

import socket  # noqa: E402
import threading  # noqa: E402


def _http(status=200, telo=b"{}", glave=None):
    g = {"Content-Length": str(len(telo))} if glave is None else glave
    return (("HTTP/1.1 %d X\r\n" % status) + "".join("%s: %s\r\n" % kv for kv in g.items()) + "\r\n").encode() + telo


class _Tls:
    def __init__(self, odgovor=b"", po_bajt=False, ura=None, korak=0.0):
        self._podatki, self.po_bajt, self._ura, self._korak = odgovor, po_bajt, ura, korak
        self.casi, self.dogodki, self.poslano = [], [], b""

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def _tik(self):
        if self._ura is not None:
            self._ura[0] += self._korak

    def settimeout(self, cas):
        self.casi.append(cas)

    def do_handshake(self):
        self.dogodki.append("rokovanje")
        self._tik()

    def sendall(self, podatki):
        self.dogodki.append("poslji")
        self.poslano += podatki
        self._tik()

    def recv(self, n):
        self._tik()
        n = 1 if self.po_bajt else n
        kos, self._podatki = self._podatki[:n], self._podatki[n:]
        return kos


class _Surova:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


@pytest.fixture
def omrezje(monkeypatch):
    stanje = {"tls": _Tls(_http()), "povezave": []}

    def povezi(naslov, rok_s):
        stanje["povezave"].append((naslov, rok_s))
        return _Surova()
    monkeypatch.setattr(P, "_povezi", povezi)
    monkeypatch.setattr(P, "_ovij", lambda _s: stanje["tls"])
    return stanje


@pytest.fixture
def cisto(monkeypatch):
    monkeypatch.setattr(P, "_seja", {})
    monkeypatch.setattr(P, "_v_teku", {})
    monkeypatch.setattr(P, "_zivih", [0])


def _pocakaj(dogodek):
    assert dogodek.wait(5)


URL = "https://api.theintrodb.org/v4/media?tmdb_id=%d"


def test_odjemalec_samo_nas_gostitelj(omrezje):
    for slab in ("https://napadalec.example/v4/media?imdb_id=tt0133093",
                 "http://api.theintrodb.org/v4/media?imdb_id=tt0133093",
                 "https://api.theintrodb.org:8443/v4/media?imdb_id=tt0133093",
                 "https://api.theintrodb.org/v4/media?imdb_id=tt0133093%0d%0aX:1 HTTP/1.0\r\n"):
        assert P._beri(slab) is None
    assert omrezje["povezave"] == []
    assert P._beri("https://api.theintrodb.org/v4/media?imdb_id=tt0133093") == "{}"
    ((naslov, rok_s),) = omrezje["povezave"]
    assert naslov == ("api.theintrodb.org", 443) and 0 < rok_s <= P.ROK_S
    tls = omrezje["tls"]
    assert tls.dogodki == ["rokovanje", "poslji"]          # nic ne gre ven pred koncanim rokovanjem TLS
    assert tls.poslano.startswith(b"GET /v4/media?imdb_id=tt0133093 HTTP/1.0\r\nHost: api.theintrodb.org\r\n")
    assert b"Accept-Encoding: identity\r\n" in tls.poslano and b"Cookie" not in tls.poslano


def test_tls_nas_kontekst_in_ime_gostitelja():
    a, b = socket.socketpair()
    try:
        tls = P._ovij(a)
        assert tls.context is P._KONTEKST and tls.server_hostname == P.GOSTITELJ
        assert P._KONTEKST.check_hostname and P._KONTEKST.verify_mode == P.ssl.CERT_REQUIRED
        tls.close()
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("odgovor,izid", [
    (_http(302, b"", {"Location": "https://drugje.example/"}), None),       # preusmeritvi ne sledimo
    (_http(404, b"ne"), ""),                                                 # ni podatkov - velja za sejo
    (_http(200, b"{}", {"Transfer-Encoding": "chunked"}), None),
    (_http(200, b"{}", {"Content-Length": "50"}), None),                     # odrezan odgovor
    (_http(200, b"{}", {"Content-Encoding": "gzip", "Content-Length": "2"}), None),
    (_http(200, b"x" * (P.NAJVEC_BAJTOV + 1)), None),
    (b"SMTP 200 nekaj\r\n\r\n{}", None),
    (_http(200, b'{"intro": []}'), '{"intro": []}'),
])
def test_razclenitev_odgovora(omrezje, odgovor, izid):
    omrezje["tls"] = _Tls(odgovor)
    assert P._beri(URL % 1) == izid


def test_kapljanje_ne_podaljsa_skupnega_roka(omrezje, monkeypatch):
    ura = [100.0]
    monkeypatch.setattr(P, "ura", lambda: ura[0])
    omrezje["tls"] = _Tls(b"HTTP/1.1 200 OK\r\n" + b"X" * 5000, po_bajt=True, ura=ura, korak=1.0)
    assert P._beri(URL % 7) is None
    tls = omrezje["tls"]
    assert all(0 < c <= P.ROK_S for c in tls.casi)
    assert len(tls.casi) <= P.SKUPNI_ROK_S + 2           # vsaka operacija dobi samo preostanek roka


def test_pocasno_rokovanje_ustavi_rok_in_nic_ne_poslje(omrezje, monkeypatch):
    ura = [100.0]
    monkeypatch.setattr(P, "ura", lambda: ura[0])
    omrezje["tls"] = _Tls(_http(), ura=ura, korak=P.SKUPNI_ROK_S + 1)    # rokovanje porabi ves rok
    assert P._beri(URL % 8) is None
    assert omrezje["tls"].poslano == b""


def test_404_velja_za_sejo(omrezje, cisto):
    omrezje["tls"] = _Tls(_http(404, b""))
    konec, izidi = threading.Event(), []
    assert P.pridobi(URL % 9, lambda o: (izidi.append(o), konec.set()))
    _pocakaj(konec)
    assert P.pridobi(URL % 9, izidi.append)          # iz predpomnilnika seje, brez nove zahteve
    assert izidi == [[], []] and len(omrezje["povezave"]) == 1


def test_neuspel_zagon_vlakna_sprosti_mesto(cisto, monkeypatch):
    class Nit:
        def __init__(self, *_a, **_k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")
    monkeypatch.setattr(P.threading, "Thread", Nit)
    assert P.pridobi(URL % 12, lambda o: None) is False
    assert P._zivih == [0] and P._v_teku == {}


def test_globok_json_ni_napaka():
    assert P.razcleni("[" * 16000) == []


def test_napaka_v_vlaknu_sprosti_mesto_in_odgovori(cisto, monkeypatch):
    def pade(_url):
        raise RecursionError
    monkeypatch.setattr(P, "_beri", pade)
    konec, izidi = threading.Event(), []
    assert P.pridobi(URL % 1, lambda o: (izidi.append(o), konec.set()))
    _pocakaj(konec)
    assert izidi == [[]] and P._v_teku == {} and P._zivih == [0]


def test_isti_url_dobijo_vsi_klicatelji(cisto, monkeypatch):
    spust = threading.Event()
    monkeypatch.setattr(P, "_beri", lambda _u: (spust.wait(5), '{"intro": [{"start_ms": 1000, "end_ms": 61000}]}')[1])
    izidi, oba = [], threading.Event()

    def izid(o):
        izidi.append(o)
        if len(izidi) == 2:
            oba.set()
    assert P.pridobi(URL % 2, izid) and P.pridobi(URL % 2, izid)
    spust.set()
    _pocakaj(oba)
    assert len(izidi) == 2 and izidi[0] and izidi[0] == izidi[1]


def test_prevec_hkratnih_vrne_false_in_kasneje_uspe(cisto, monkeypatch):
    spust = threading.Event()
    monkeypatch.setattr(P, "_beri", lambda _u: (spust.wait(5), "{}")[1])
    konci = [threading.Event() for _ in range(3)]
    assert P.pridobi(URL % 3, lambda o: konci[0].set())
    assert P.pridobi(URL % 4, lambda o: konci[1].set())
    assert P.pridobi(URL % 5, lambda o: konci[2].set()) is False
    spust.set()
    _pocakaj(konci[0]), _pocakaj(konci[1])
    assert P.pridobi(URL % 5, lambda o: konci[2].set())
    _pocakaj(konci[2])


def test_obviseli_zapis_ne_zaseda_mesta_in_cakajoci_dobijo_prazno(cisto, monkeypatch):
    monkeypatch.setattr(P, "_beri", lambda _u: "{}")
    star = P.ura() - P._MRTEV_S - 1
    odvrzeni = []
    P._v_teku.update({"a": (star, [odvrzeni.append], object()), "b": (star, [], object())})
    konec = threading.Event()
    assert P.pridobi(URL % 6, lambda o: konec.set())
    _pocakaj(konec)
    assert odvrzeni == [[]]          # cakajoci obvisele poizvedbe ne ostane brez odgovora


def test_meja_zivih_vlaken(cisto, monkeypatch):
    monkeypatch.setattr(P, "_beri", lambda _u: "{}")
    P._zivih[0] = P._NAJVEC_ZIVIH      # obvisela vlakna (DNS brez roka) - ne zacnemo novih
    assert P.pridobi(URL % 10, lambda o: None) is False
    assert P._v_teku == {}


def test_staro_vlakno_ne_pobere_novejsega_zapisa(cisto, monkeypatch):
    monkeypatch.setattr(P, "_beri", lambda _u: '{"intro": [{"start_ms": 1000, "end_ms": 61000}]}')
    novi = []
    nov_zeton = object()
    P._v_teku[URL % 11] = (P.ura(), [novi.append], nov_zeton)
    P._zivih[0] = 1
    P._delo(URL % 11, object())       # staro (odvrzeno) vlakno se konca
    assert novi == [] and P._v_teku[URL % 11][2] is nov_zeton and P._zivih == [0]


# ---- skupnostna baza: odsek, ki bi sredi filma prevzel OK/Enter, ni smiseln (slepi pregled TV 13. 11. 2026)

def test_odjavna_mora_biti_na_koncu():
    T = 6000.0
    assert not P.smiseln(P.Odsek("odjavna", 0.55 * T, 0.60 * T), T)      # sredi filma
    assert not P.smiseln(P.Odsek("odjavna", 0.80 * T, 0.85 * T), T)      # ne sega do konca
    assert P.smiseln(P.Odsek("odjavna", 0.80 * T, None), T)
    assert P.smiseln(P.Odsek("napoved", 0.95 * T, T), T)


def test_najvec_dva_odseka_iste_vrste():
    besedilo = '{"intro": [%s]}' % ", ".join('{"start_ms": %d, "end_ms": %d}' % (i * 100000, i * 100000 + 30000)
                                            for i in range(5))
    assert len(P.uporabni(P.razcleni(besedilo), 6000.0)) == 2


def test_predolga_uvoda_ne_porabita_meje():
    """CodeRabbit 13. 11. 2026 (TV): dva predolga uvoda na zacetku ne skrijeta tretjega, veljavnega."""
    besedilo = ('{"intro": [{"start_ms": 0, "end_ms": 360000}, {"start_ms": 1000, "end_ms": 361000},'
                ' {"start_ms": 60000, "end_ms": 90000}]}')
    assert P.aktiven(P.razcleni(besedilo), 70.0, 6000.0) == P.Odsek("uvod", 60.0, 90.0)


def test_koncan_odsek_ne_zakrije_drugega():
    """CodeRabbit 13. 11. 2026 (TV): preskocen povzetek 0-90 s ne skrije uvoda 60-80 s."""
    odseki = [P.Odsek("povzetek", 0.0, 90.0), P.Odsek("uvod", 60.0, 80.0)]
    assert P.aktiven(odseki, 65.0, 6000.0) == odseki[0]
    assert P.aktiven(odseki, 65.0, 6000.0, {odseki[0]}) == odseki[1]


def test_neveljavni_na_zacetku_ne_skrijejo_veljavnega():
    besedilo = '{"intro": [{"start_ms": -5}, {"start_ms": "x"}, {"start_ms": true}, {"start_ms": 1000, "end_ms": 61000}]}'
    assert P.razcleni(besedilo) == [P.Odsek("uvod", 1.0, 61.0)]


def test_odvrzeno_vlakno_ne_prepise_novejsega_odgovora(cisto, monkeypatch):
    monkeypatch.setattr(P, "_beri", lambda _u: "{}")
    nov = [P.Odsek("uvod", 1.0, 61.0)]
    P._seja[URL % 13] = nov                           # novejsa poizvedba je ze shranila odgovor
    P._zivih[0] = 1
    P._delo(URL % 13, object())                       # staro (odvrzeno) vlakno konca s praznim odgovorom
    assert P._seja[URL % 13] is nov

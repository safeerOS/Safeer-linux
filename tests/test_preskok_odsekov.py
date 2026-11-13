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


# ---- omrezje: nadomestek http.client.HTTPSConnection (nic ne gre na internet)

import threading  # noqa: E402
import time  # noqa: E402


class _Vticnica:
    def __init__(self):
        self.prekinjena = threading.Event()

    def shutdown(self, _kako):
        self.prekinjena.set()


class _Odgovor:
    klici_read = 0

    def __init__(self, status=200, telo=b"{}", glave=None, kapljaj=False):
        self.status, self._telo, self._glave, self._kapljaj = status, telo, glave or {}, kapljaj

    def getheader(self, kljuc):
        return self._glave.get(kljuc)

    def read(self, *_a):         # read(n) caka na n bajtov - pri kapljanju skupni rok ne bi veljal
        _Odgovor.klici_read += 1
        return b""

    def read1(self, n):
        if self._kapljaj:
            return b"["
        kos, self._telo = self._telo[:n], self._telo[n:]
        return kos


class _Povezava:
    odgovor = staticmethod(lambda povezava: _Odgovor())
    ustvarjene: list = []

    def __init__(self, gostitelj, vrata, timeout=None, context=None):
        self.gostitelj, self.vrata, self.timeout, self.context = gostitelj, vrata, timeout, context
        self.sock = _Vticnica()
        self.pot = self.glave = None
        _Povezava.ustvarjene.append(self)

    def connect(self):
        pass

    def request(self, metoda, pot, headers=None):
        self.metoda, self.pot, self.glave = metoda, pot, headers

    def getresponse(self):
        return _Povezava.odgovor(self)

    def close(self):
        pass


@pytest.fixture
def omrezje(monkeypatch):
    _Povezava.ustvarjene = []
    _Povezava.odgovor = staticmethod(lambda povezava: _Odgovor())
    monkeypatch.setattr(P, "_Povezava", _Povezava)
    return _Povezava


@pytest.fixture
def cisto(monkeypatch):
    monkeypatch.setattr(P, "_seja", {})
    monkeypatch.setattr(P, "_v_teku", {})
    monkeypatch.setattr(P, "_zivih", [0])


def _pocakaj(dogodek):
    assert dogodek.wait(5)


URL = "https://api.theintrodb.org/v4/media?tmdb_id=%d"


def test_odjemalec_samo_nas_gostitelj_in_preverjen_tls(omrezje):
    def pade(_p):
        raise OSError("brez omrezja")
    omrezje.odgovor = staticmethod(pade)
    assert P._beri("https://napadalec.example/v4/media?imdb_id=tt0133093") is None
    assert P._beri("http://api.theintrodb.org/v4/media?imdb_id=tt0133093") is None
    assert P._beri("https://api.theintrodb.org:8443/v4/media?imdb_id=tt0133093") is None
    assert omrezje.ustvarjene == []
    assert P._beri("https://api.theintrodb.org/v4/media?imdb_id=tt0133093") is None   # napaka omrezja -> None
    (pov,) = omrezje.ustvarjene
    assert (pov.gostitelj, pov.vrata, pov.pot) == ("api.theintrodb.org", 443, "/v4/media?imdb_id=tt0133093")
    assert pov.context is P._KONTEKST and pov.context.check_hostname and pov.context.verify_mode == P.ssl.CERT_REQUIRED
    assert pov.glave["Accept-Encoding"] == "identity" and "Cookie" not in pov.glave


def test_preusmeritve_ne_sledimo(omrezje):
    omrezje.odgovor = staticmethod(lambda _p: _Odgovor(302, glave={"Location": "https://drugje.example/"}))
    assert P._beri(URL % 1) is None
    assert len(omrezje.ustvarjene) == 1


def test_kapljanje_ustavi_skupni_rok(omrezje, monkeypatch):
    ura = [100.0]

    def tik():
        ura[0] += 1.0
        return ura[0]
    omrezje.odgovor = staticmethod(lambda _p: _Odgovor(kapljaj=True))
    monkeypatch.setattr(P, "ura", tik)
    _Odgovor.klici_read = 0
    assert P._beri(URL % 7) is None
    assert _Odgovor.klici_read == 0
    assert ura[0] < 100.0 + P.SKUPNI_ROK_S + 5


def test_straza_prekine_kapljanje_glav(omrezje, monkeypatch):
    """Streznik poslje glave po bajt: getresponse visi - straza mora prekiniti povezavo ob skupnem roku."""
    monkeypatch.setattr(P, "SKUPNI_ROK_S", 0.3)

    def visi(povezava):
        if not povezava.sock.prekinjena.wait(5):
            raise AssertionError("straza ni prekinila povezave")
        raise OSError("prekinjeno")
    omrezje.odgovor = staticmethod(visi)
    zacetek = time.monotonic()
    assert P._beri(URL % 8) is None
    assert time.monotonic() - zacetek < 2.0
    assert omrezje.ustvarjene[0].sock.prekinjena.is_set()


def test_404_velja_za_sejo(omrezje, cisto):
    omrezje.odgovor = staticmethod(lambda _p: _Odgovor(404, b""))
    konec, izidi = threading.Event(), []
    assert P.pridobi(URL % 9, lambda o: (izidi.append(o), konec.set()))
    _pocakaj(konec)
    assert P.pridobi(URL % 9, izidi.append)          # iz predpomnilnika seje, brez nove zahteve
    assert izidi == [[], []] and len(omrezje.ustvarjene) == 1


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
    assert len(P.razcleni(besedilo)) == 2

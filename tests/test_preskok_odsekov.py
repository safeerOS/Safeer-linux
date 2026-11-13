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


def test_odjemalec_samo_nas_gostitelj(monkeypatch):
    klici = []
    monkeypatch.setattr(P._odpiralnik, "open", lambda *a, **k: klici.append(a) or (_ for _ in ()).throw(OSError()))
    assert P._beri("https://napadalec.example/v4/media?imdb_id=tt0133093") is None
    assert P._beri("http://api.theintrodb.org/v4/media?imdb_id=tt0133093") is None
    assert klici == []
    assert P._beri("https://api.theintrodb.org/v4/media?imdb_id=tt0133093") is None   # napaka omrezja -> None
    assert len(klici) == 1


def test_preusmeritve_ne_sledimo():
    assert P._BrezPreusmeritev().redirect_request(None, None, 302, "", {}, "https://drugje.example/") is None


# ---- slepi pregled 13. 11. 2026: globok JSON, kapljanje, zasedena mesta, cakajoci klicatelji

import threading  # noqa: E402


@pytest.fixture
def cisto(monkeypatch):
    monkeypatch.setattr(P, "_seja", {})
    monkeypatch.setattr(P, "_v_teku", {})


def _pocakaj(dogodek):
    assert dogodek.wait(5)


def test_globok_json_ni_napaka():
    assert P.razcleni("[" * 16000) == []


def test_napaka_v_vlaknu_sprosti_mesto_in_odgovori(cisto, monkeypatch):
    def pade(_url):
        raise RecursionError
    monkeypatch.setattr(P, "_beri", pade)
    konec, izidi = threading.Event(), []
    assert P.pridobi("https://api.theintrodb.org/v4/media?tmdb_id=1", lambda o: (izidi.append(o), konec.set()))
    _pocakaj(konec)
    assert izidi == [[]] and P._v_teku == {}


def test_isti_url_dobijo_vsi_klicatelji(cisto, monkeypatch):
    spust = threading.Event()
    monkeypatch.setattr(P, "_beri", lambda _u: (spust.wait(5), '{"intro": [{"start_ms": 1000, "end_ms": 61000}]}')[1])
    url, izidi, oba = "https://api.theintrodb.org/v4/media?tmdb_id=2", [], threading.Event()

    def izid(o):
        izidi.append(o)
        if len(izidi) == 2:
            oba.set()
    assert P.pridobi(url, izid) and P.pridobi(url, izid)
    spust.set()
    _pocakaj(oba)
    assert len(izidi) == 2 and izidi[0] and izidi[0] == izidi[1]


def test_prevec_hkratnih_vrne_false_in_kasneje_uspe(cisto, monkeypatch):
    spust = threading.Event()
    monkeypatch.setattr(P, "_beri", lambda _u: (spust.wait(5), "{}")[1])
    konci = [threading.Event() for _ in range(3)]
    assert P.pridobi("https://api.theintrodb.org/v4/media?tmdb_id=3", lambda o: konci[0].set())
    assert P.pridobi("https://api.theintrodb.org/v4/media?tmdb_id=4", lambda o: konci[1].set())
    assert P.pridobi("https://api.theintrodb.org/v4/media?tmdb_id=5", lambda o: konci[2].set()) is False
    spust.set()
    _pocakaj(konci[0]), _pocakaj(konci[1])
    assert P.pridobi("https://api.theintrodb.org/v4/media?tmdb_id=5", lambda o: konci[2].set())
    _pocakaj(konci[2])


def test_obviseli_zapis_ne_zaseda_mesta(cisto, monkeypatch):
    monkeypatch.setattr(P, "_beri", lambda _u: "{}")
    star = P.time.monotonic() - P._MRTEV_S - 1
    P._v_teku.update({"a": (star, []), "b": (star, [])})
    konec = threading.Event()
    assert P.pridobi("https://api.theintrodb.org/v4/media?tmdb_id=6", lambda o: konec.set())
    _pocakaj(konec)


class _Kapljanje:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    klici_read = 0

    def read(self, *_a):   # read(n) caka na n bajtov - pri kapljanju skupni rok ne velja
        _Kapljanje.klici_read += 1
        return b"["

    def read1(self, *_a):
        return b"["


def test_kapljanje_ustavi_skupni_rok(monkeypatch):
    ura = [100.0]

    def monotonic():
        ura[0] += 1.0
        return ura[0]
    monkeypatch.setattr(P._odpiralnik, "open", lambda *_a, **_k: _Kapljanje())
    monkeypatch.setattr(P.time, "monotonic", monotonic)
    _Kapljanje.klici_read = 0
    assert P._beri("https://api.theintrodb.org/v4/media?tmdb_id=7") is None
    assert _Kapljanje.klici_read == 0
    assert ura[0] < 100.0 + P.SKUPNI_ROK_S + 5

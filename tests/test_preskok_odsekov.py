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

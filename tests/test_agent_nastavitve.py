"""Nastavitve Safeer Agenta v Nastavitvah Safeer OS (lastnik, 19. 10. 2026): naslov lokalnega modela (samo http(s)),
izklop, privzeto trajanje seje in dosegljivost brez laznih podatkov; iskalna lupa poslje stavek istemu agentu."""
import http.server
import json
import os
import threading

import pytest

from core.agent import izvajanje, nastavitve, razumevanje, seja, storitev

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def mapa(monkeypatch, tmp_path):
    monkeypatch.setattr(nastavitve, "MAPA", str(tmp_path / "safeer-agent"))
    monkeypatch.delenv("SAFEER_AGENT", raising=False)
    storitev._seje.clear()
    yield tmp_path / "safeer-agent"
    storitev._seje.clear()


def test_shrani_naslov_in_ga_agent_uporabi(mapa):
    izid = nastavitve.nastavi_naslov("  HTTP://192.0.2.7:8085/  ")
    assert izid["ok"] and izid["naslov"] == "http://192.0.2.7:8085" and izid["na_voljo"]
    assert (mapa / "naslov").read_text() == "http://192.0.2.7:8085\n"
    assert razumevanje.naslov_modela() == "http://192.0.2.7:8085"
    # Pot (obratni posrednik) ostane, poseven / na koncu ne - llama_server doda /v1/chat/completions.
    assert nastavitve.nastavi_naslov("https://model.lan/llm/")["naslov"] == "https://model.lan/llm"
    # Prazen naslov izbrise datoteko: agent ni vec na voljo.
    izid = nastavitve.nastavi_naslov("")
    assert izid["ok"] and izid["naslov"] == "" and not izid["na_voljo"] and not (mapa / "naslov").exists()


@pytest.mark.parametrize("naslov,koda", [
    ("ftp://192.0.2.7/", "shema"), ("file:///etc/passwd", "shema"), ("javascript:alert(1)", "shema"),
    ("192.0.2.7:8085", "shema"), ("http://uporabnik:geslo@192.0.2.7:8085", "geslo"),
    ("http://192.0.2.7:8085/?x=1", "naslov"), ("http://192.0.2.7:8085/#a", "naslov"), ("http://192.0.2.7:99999", "naslov"),
    ("http://192.0.2.7:8085/a b", "naslov"), ("http://192.0.2.7\n:8085", "naslov"), ("http://", "naslov"),
    ("http://x.si/" + "a" * 200, "dolzina"),
])
def test_zavrne_ne_http(mapa, naslov, koda):
    nastavitve.nastavi_naslov("http://192.0.2.9:8085")
    izid = nastavitve.nastavi_naslov(naslov)
    assert not izid["ok"] and izid["napaka"] == koda
    # Zavrnjen naslov ne prepise shranjenega.
    assert (mapa / "naslov").read_text() == "http://192.0.2.9:8085\n"
    assert razumevanje.naslov_modela() == "http://192.0.2.9:8085"


def test_rocno_vpisan_neveljaven_naslov_ne_velja(mapa):
    mapa.mkdir(parents=True)
    (mapa / "naslov").write_text("ftp://192.0.2.7\n")
    assert nastavitve.stanje()["naslov"] == "" and razumevanje.naslov_modela() == ""


def test_izklop_ohrani_naslov(mapa, monkeypatch):
    nastavitve.nastavi_naslov("http://192.0.2.7:8085")
    izid = nastavitve.nastavi_vklop(False)
    assert izid["ok"] and not izid["vklopljen"] and izid["naslov"] == "http://192.0.2.7:8085" and not izid["na_voljo"]
    assert razumevanje.naslov_modela() == ""
    # Izklop velja tudi za naslov iz okolja (SAFEER_AGENT).
    monkeypatch.setenv("SAFEER_AGENT", "http://192.0.2.8:8085")
    assert razumevanje.naslov_modela() == ""
    assert nastavitve.nastavi_vklop(True)["na_voljo"]
    assert razumevanje.naslov_modela() == "http://192.0.2.8:8085"
    assert nastavitve.stanje()["okolje"] == "http://192.0.2.8:8085"


def test_trajanje_seje(mapa):
    assert nastavitve.stanje()["trajanje"] == 0 and nastavitve.TRAJANJA[0] == 1 and 0 in nastavitve.TRAJANJA
    for m in nastavitve.TRAJANJA:
        assert nastavitve.nastavi_trajanje(m)["trajanje"] == m
    for slabo in (7, -1, True, "abc", None):
        assert not nastavitve.nastavi_trajanje(slabo)["ok"]
    assert nastavitve.trajanje() == 0
    nastavitve.nastavi_trajanje(5)
    s = storitev._seja("n-tel", None)
    assert s.trajanje_min == 5, "naprava trajanja ni povedala: privzeto iz Nastavitev"
    assert storitev._seja("n-tel", 0).trajanje_min is None, "izrecno trajanje naprave velja (0 = neomejeno)"


class _Streznik:
    def __init__(self, odgovori):
        odg = odgovori

        class Rokovalnik(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                koda, telo = odg.get(self.path, (404, b""))
                self.send_response(koda)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(telo)

            def log_message(self, *_a):
                pass
        self.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Rokovalnik)
        self.nit = threading.Thread(target=self.streznik.serve_forever, daemon=True)
        self.nit.start()
        self.naslov = "http://127.0.0.1:%d" % self.streznik.server_address[1]

    def ustavi(self):
        self.streznik.shutdown()
        self.streznik.server_close()
        self.nit.join(5)


def test_dosegljivost_brez_laznih_podatkov(mapa):
    assert nastavitve.dosegljivost() == {"dosegljiv": False, "model": "", "napaka": "ni_naslova"}
    s = _Streznik({"/v1/models": (200, json.dumps({"data": [{"id": "/modeli/gemma-3-4b-it.gguf"}]}).encode())})
    try:
        nastavitve.nastavi_naslov(s.naslov)
        assert nastavitve.dosegljivost() == {"dosegljiv": True, "model": "gemma-3-4b-it.gguf", "napaka": ""}
    finally:
        s.ustavi()
    # Streznik brez /v1/models, a z /health (starejsi llama-server).
    s = _Streznik({"/health": (200, b'{"status": "ok"}')})
    try:
        assert nastavitve.dosegljivost(s.naslov)["dosegljiv"] is True
    finally:
        s.ustavi()
    s = _Streznik({"/v1/models": (401, b"")})
    try:
        assert nastavitve.dosegljivost(s.naslov) == {"dosegljiv": False, "model": "", "napaka": "kljuc"}
    finally:
        s.ustavi()
    # Ustavljen streznik: zaprta vrata, ni dosegljiv (in nic ne caka predolgo).
    izid = nastavitve.dosegljivost(s.naslov, cas=2.0)
    assert izid["dosegljiv"] is False and izid["napaka"]
    assert nastavitve.dosegljivost("ftp://x")["napaka"] == "shema"


def test_lupa_brez_modela_pove_razlog(mapa):
    assert storitev.vprasaj_tukaj("utisaj televizor") == {"ok": False, "koda": "ni_modela", "koraki": [], "povzetek": ""}
    assert storitev.vprasaj_tukaj("   ")["koda"] == "prazno"


def test_lupa_tukaj_je_ta_racunalnik(mapa, monkeypatch):
    nastavitve.nastavi_naslov("http://192.0.2.7:8085")
    klici = []
    naprave = [{"id": "n-tv", "ime": "Dnevna soba", "platforma": "tv"},
               {"id": "n-pc", "ime": "Racunalnik", "platforma": "linux", "vrsta": "control", "ta": True}]
    izv = izvajanje.Izvajalec(lambda: naprave, lambda n, d, p: klici.append((n, d, p)) or {"ok": True})
    model = lambda s, shema: {"naloge": [{"dejanje": "pavza", "naprava": "tukaj", "kaj": ""},
                                         {"dejanje": "utisaj", "naprava": "tv", "kaj": ""}]}
    monkeypatch.setattr(storitev, "nova_seja", lambda **k: seja.Seja(klic_modela=model, **k))
    izid = storitev.vprasaj_tukaj("pavza tukaj in utisaj televizor", izv)
    assert izid["ok"] and len(izid["koraki"]) == 2, izid
    assert klici == [("n-pc", "key", {"key": "pause"}), ("n-tv", "volume", {"direction": "mute"})]


def test_lupa_model_ni_dosegljiv(mapa, monkeypatch):
    nastavitve.nastavi_naslov("http://192.0.2.7:8085")

    def ne_odgovori(s, shema):
        raise OSError("timed out")
    monkeypatch.setattr(storitev, "nova_seja", lambda **k: seja.Seja(klic_modela=ne_odgovori, **k))
    izid = storitev.vprasaj_tukaj("glasneje", izvajanje.Izvajalec(lambda: [], lambda *a: {"ok": True}))
    assert not izid["ok"] and izid["koda"] == "model_ni_dosegljiv"


def test_most_in_dogodek():
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
        so = f.read()
    for metoda in ("agentStanje", "agentNastavi", "agentVklop", "agentTrajanje", "agentDosegljivost", "agentVprasaj"):
        assert '"%s": lambda: self._agent(' % metoda in so, metoda
    # Sprememba gre vsem pogledom (iskalna lupa) - samo uspesna.
    assert 'if izid.get("ok"):\n            self._dogodek("agent", {"na_voljo": bool(izid.get("na_voljo"))})' in so
    assert '"agent": {"na_voljo": bool(self._agent("stanje").get("na_voljo"))},' in so

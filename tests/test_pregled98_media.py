"""Popravki pregleda Grok 98 (K1-K4), ki jih je imel samo Windows (26. 10. 2026), preneseni v skupno jedro (22. 11. 2026,
zdruzitev Medijskega centra Linux - Windows). Lastnik: nevarnost zaklepa racuna je prioriteta; o vsebinah te naprave
odloca samo ta naprava. Naslovi in racuni so izmisljeni (.test); vsak preizkus brez svojega popravka pade."""
import tempfile
import threading

import pytest

from core import os_media

RACUN = "http://ponudnik.test:8080/get.php?username=uporabnik&password=geslo&type=m3u_plus"
SEZNAM = b"#EXTM3U\n#EXTINF:-1,Kanal ena\nhttp://ponudnik.test:8080/live/uporabnik/geslo/1.ts\n"


def _mc():
    """MediaCenter z laznim _download (stejemo klice, vedno vrne seznam z enim kanalom)."""
    mc = os_media.MediaCenter(tempfile.mkdtemp(), roots=[])
    klici = []

    def prenesi(url):
        klici.append(url)
        return SEZNAM, "audio/x-mpegurl", url
    mc._download = prenesi
    mc._izmeri_ping = lambda *_a: None
    return mc, klici


def _vir(mc, url=RACUN, **polja):
    data = mc._load()
    vir = dict({"id": "v1", "url": url, "ime": "Ponudnik", "posodobljeno": 0, "napaka": "", "stevilo": 0, "vnosi": []},
               **polja)
    data.setdefault("viri", []).append(vir)
    mc._save(data)
    return vir["id"]


def test_k1_samodejna_osvezitev_ne_odpre_vira_z_racunom():
    mc, klici = _mc()
    _vir(mc)                                             # posodobljeno=0: zastarel, ni premora, ne caka
    assert mc.refresh_stale(max_age=60)["osvezenih"] == 0
    assert klici == [], "vir z racunom se v ozadju ne odpre"
    assert mc.refresh_source("v1")["ok"] and len(klici) == 1, "uporabnikov Osvezi ga odpre"


def _hkrati(mc, prvi, drugi):
    """Drugi refresh_source, medtem ko prvi caka v prenosu; vrne odgovor drugega."""
    vstop, sprosti = threading.Event(), threading.Event()
    pravi = mc._download

    def pocasen(url):
        if not vstop.is_set():
            vstop.set()
            sprosti.wait(5)
        return pravi(url)
    mc._download = pocasen
    t = threading.Thread(target=mc.refresh_source, args=(prvi,))
    t.start()
    try:
        assert vstop.wait(5)
        return mc.refresh_source(drugi)
    finally:
        sprosti.set()
        t.join(10)


def test_k2_ena_osvezitev_na_racun_naenkrat():
    mc, klici = _mc()
    _vir(mc)
    _vir(mc, url=RACUN.replace("m3u_plus", "m3u").replace(":8080", ":8081"), id="v2")   # isti racun, drug naslov in vrata
    assert _hkrati(mc, "v1", "v2") == {"ok": False, "napaka": "", "ze_tece": True}
    assert len(klici) == 1, "nikoli dve hkratni prijavi istega racuna"


def test_k2_drug_racun_istega_ponudnika_ni_blokiran():
    mc, klici = _mc()
    _vir(mc)
    _vir(mc, url=RACUN.replace("username=uporabnik", "username=drug"), id="v2")
    assert _hkrati(mc, "v1", "v2")["ok"], "kontrola: drug racun pri istem ponudniku sme hkrati"
    assert len(klici) == 2


def test_k3_poverilnice_niso_platforma_brez_racuna(monkeypatch):
    monkeypatch.setattr(os_media, "_je_predvajalni_vir", lambda _u: True)    # panel ujame vzorec predvajalnega vira
    assert not os_media._platforma_brez_racuna(RACUN)
    assert not os_media._platforma_brez_racuna("https://www.youtube.com/get.php?username=u&password=g")
    assert not os_media._platforma_brez_racuna("http://u:g@www.youtube.com/x")
    assert not os_media._platforma_brez_racuna("http://panel.test/live/u/g/1.ts")
    assert os_media.MediaCenter._racun_vira({"url": RACUN}), "vir z geslom ostane vir z racunom"
    monkeypatch.setattr(os_media, "_je_predvajalni_vir", lambda _u: False)
    assert os_media._platforma_brez_racuna("https://www.youtube.com/watch?v=abc"), "kontrola: javna platforma"


def test_k4_prejem_ne_potrdi_tujega_tipa():
    mc, klici = _mc()
    potrjeni = []
    mc._vir_potrjen = lambda tip, naslov: potrjeni.append((tip, naslov))
    r = mc.add_source(RACUN, "Ponudnik", prevzet={"tip": "kljuc-torbox", "naslov": "drugo", "cas": 1})
    assert r.get("caka") is True and klici == []
    assert ("kljuc-torbox", "drugo") not in potrjeni, "dohodno sporocilo ne izbira, kaj ta naprava potrdi"
    assert all(naslov == os_media.canonical_url(RACUN) for _tip, naslov in potrjeni), potrjeni
    potrjeni.clear()
    drug = RACUN.replace("m3u_plus", "m3u")
    mc.add_source(drug, "Ponudnik", prevzet={"tip": "url", "naslov": "http://tuj.test/seznam.m3u", "cas": 1})
    assert ("url", "http://tuj.test/seznam.m3u") not in potrjeni, "tuj naslov (ne ta vir) se ne potrdi"


@pytest.mark.parametrize("pot,vrsta", [
    ("/media/Serije/TVShows/Nekaj/01.mkv", "serija"),
    ("/media/tv shows/x/01.mkv", "serija"),
    ("/media/Latvia/potovanje.mkv", "film"),
    ("/tmp/tvxq3/film.mkv", "film"),
])
def test_tvshows_beseda_ne_podniz(pot, vrsta):
    """Mapa TVShows je serija; podniz tv (Latvia, nakljucno ime zacasne mape) ni (iz Windows, zdruzitev 22. 11.)."""
    assert os_media._kind("", url=pot) == vrsta

"""Pregled 881d60f6 (bot telefon): Povezava._odpri ob 401, _poslusaj, podpis izziva.

Brez omrezja in brez huba: omrezne klice zamenjamo z namisljenimi. Izidi so izracunani rocno (NI pognano).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import core.link_hub as lh  # noqa: E402

NASLOV = "wss://hub.lan:8443/ws"
ODTIS = "ab12cd"


def _povezava():
    return lh.Povezava(NASLOV, "zeton", "n-0123456789abcdef", "racunalnik", odtis=ODTIS)


class _BrezVticnice:
    """WsOdjemalec, ki se ne odpre: _odpri se konca po odlocitvi o vpisu, brez omrezja."""

    def __init__(self, *a, **k):
        pass

    def odpri(self):
        raise OSError("brez omrezja")

    def zapri(self):
        pass


# ------------------------------------------------------------------ N3: zanka 401 -> vpis -> 401

def test_ponovni_vpis_ob_401_ni_ob_vsaki_povezavi(monkeypatch):
    vpisi = []
    monkeypatch.setattr(lh.link_krog, "lahko_s_podpisom", lambda d: True)
    monkeypatch.setattr(lh, "vzemi_vstopnico_s_podpisom", lambda *a, **k: (None, 401))
    monkeypatch.setattr(lh, "vzemi_vstopnico_s_kodo", lambda *a, **k: ("vstopnica", 200))
    monkeypatch.setattr(lh, "vpisi_v_krog", lambda *a, **k: vpisi.append(a) or True)
    monkeypatch.setattr(lh, "WsOdjemalec", _BrezVticnice)
    p = _povezava()
    assert p._odpri() is False
    assert p._odpri() is False
    # Brez popravka: 2 vpisa (vsaka ponovna povezava). S popravkom: 1 v POPRAVEK_PREMOR_S.
    assert len(vpisi) == 1
    assert p.koda_podpisa == 401 and p.prijava_s_podpisom is False


def test_po_premoru_spet_poskusi(monkeypatch):
    vpisi = []
    ura = [1000.0]
    monkeypatch.setattr(lh.time, "monotonic", lambda: ura[0])
    monkeypatch.setattr(lh.link_krog, "lahko_s_podpisom", lambda d: True)
    monkeypatch.setattr(lh, "vzemi_vstopnico_s_podpisom", lambda *a, **k: (None, 401))
    monkeypatch.setattr(lh, "vzemi_vstopnico_s_kodo", lambda *a, **k: ("vstopnica", 200))
    monkeypatch.setattr(lh, "vpisi_v_krog", lambda *a, **k: vpisi.append(a) or True)
    monkeypatch.setattr(lh, "WsOdjemalec", _BrezVticnice)
    p = _povezava()
    p._odpri()
    ura[0] += lh.POPRAVEK_PREMOR_S
    p._odpri()
    assert len(vpisi) == 2


def test_403_se_vedno_brez_vpisa(monkeypatch):
    vpisi = []
    monkeypatch.setattr(lh.link_krog, "lahko_s_podpisom", lambda d: True)
    monkeypatch.setattr(lh, "vzemi_vstopnico_s_podpisom", lambda *a, **k: (None, 403))
    monkeypatch.setattr(lh, "vzemi_vstopnico_s_kodo", lambda *a, **k: ("vstopnica", 200))
    monkeypatch.setattr(lh, "vpisi_v_krog", lambda *a, **k: vpisi.append(a) or True)
    monkeypatch.setattr(lh, "WsOdjemalec", _BrezVticnice)
    _povezava()._odpri()
    assert vpisi == []


# ------------------------------------------------------------------ N4: izjema v prvem poskusu s podpisom

def test_izjema_pri_podpisu_ne_konca_odpiranja(monkeypatch):
    def pade(*a, **k):
        raise AttributeError("'list' object has no attribute 'get'")

    monkeypatch.setattr(lh.link_krog, "lahko_s_podpisom", lambda d: True)
    monkeypatch.setattr(lh, "vzemi_vstopnico_s_podpisom", pade)
    monkeypatch.setattr(lh, "vzemi_vstopnico_s_kodo", lambda *a, **k: (None, 503))
    p = _povezava()
    # Brez popravka izjema prileti iz _odpri (in v _zanka konca nit povezave).
    assert p._odpri() is False
    assert p.koda_podpisa == 0 and p.prijava_s_podpisom is False


# ------------------------------------------------------------------ N2: sporocilo, ki ga json ne prebavi

class _Odjemalec:
    def __init__(self, sporocila):
        self.sporocila = list(sporocila)

    def prejmi(self):
        return self.sporocila.pop(0) if self.sporocila else None

    def zapri(self):
        pass


def test_pregloboko_gnezdenje_ne_zapre_povezave():
    p = _povezava()
    prejeto = []
    p.ob_sporocilu = prejeto.append
    p.tece = True
    p.odjemalec = _Odjemalec(["[" * 200000 + "]" * 200000, '{"type": "x"}'])
    p._poslusaj()
    # Brez popravka RecursionError konca _poslusaj in {"type": "x"} ne pride.
    assert prejeto == [{"type": "x"}]


def test_predolgo_stevilo_ne_zapre_povezave():
    meja = sys.get_int_max_str_digits() if hasattr(sys, "get_int_max_str_digits") else 0
    if not 0 < meja < 5000:
        return  # Python brez meje stevk (ali izklopljena): json stevilo sprejme, ni kaj preizkusiti
    p = _povezava()
    prejeto = []
    p.ob_sporocilu = prejeto.append
    p.tece = True
    p.odjemalec = _Odjemalec(['{"payload": {"params": {"maxsize": {"hevc": [' + "9" * 5000 + ', 1]}}}}',
                              '{"type": "x"}'])
    p._poslusaj()
    assert prejeto == [{"type": "x"}]


# ------------------------------------------------------------------ N1: odtis v izzivu izbere hub

def _izziv(monkeypatch, fp):
    podpisani = []
    zahteve = []

    def zahteva(url, telo=None, zeton=None, timeout=5.0, odtis=None):
        zahteve.append(url)
        if url.endswith("/cast/auth/challenge"):
            return 200, {"nonce": "n1", "fp": fp}
        return 200, {"ticket": "vstopnica", "session_token": "seja"}

    monkeypatch.setattr(lh, "_zahteva", zahteva)
    monkeypatch.setattr(lh.link_krog, "podatki_za_podpis", lambda f, n, d: (f, n, d))
    monkeypatch.setattr(lh.link_krog, "podpisi", lambda podatki: podpisani.append(podatki) or "podpis")
    monkeypatch.setattr(lh.link_krog, "sprejmi", lambda krog: None)
    return podpisani, zahteve


def test_tuj_odtis_v_izzivu_ni_podpisan(monkeypatch):
    podpisani, zahteve = _izziv(monkeypatch, "ff" * 32)
    # Main (_odtis_za_podpis) ob tujem odtisu v izzivu vrne (None, koda izziva); pomembno je, da vstopnice ni in podpisa ni.
    assert lh.vzemi_vstopnico_s_podpisom(NASLOV, "n-0123456789abcdef", ODTIS)[0] is None
    assert lh.seja_s_podpisom(NASLOV, "n-0123456789abcdef", ODTIS) is None
    # Brez popravka podpisemo ("ff"*32, "n1", id) - podpis za drug hub.
    assert podpisani == []
    assert not any(u.endswith("/cast/auth/ticket") for u in zahteve)


def test_lasten_odtis_ali_brez_odtisa_se_podpise(monkeypatch):
    podpisani, _ = _izziv(monkeypatch, ODTIS.upper())
    assert lh.vzemi_vstopnico_s_podpisom(NASLOV, "n-0123456789abcdef", ODTIS) == ("vstopnica", 200)
    podpisani2, _ = _izziv(monkeypatch, "")
    assert lh.seja_s_podpisom(NASLOV, "n-0123456789abcdef", ODTIS) == "seja"
    # Main podpise vedno pripet odtis (male crke), ne tistega iz izziva.
    assert podpisani == [(ODTIS.lower(), "n1", "n-0123456789abcdef")]
    assert podpisani2 == [(ODTIS, "n1", "n-0123456789abcdef")]

"""Klicatelj zaslona: screen.start -> Zaslon.zacni (core/link_daljinec.py, izvedi_control).

"codecs" (list, najvec 8 nizov do 16 znakov) in "maxsize" (dict) gresta v zacni kot kodeki= in
najvecja=; napacen tip se prezre in klic je enak kot doslej (H.264 do 1080p). Odgovor screen.start
vrne "codec" izbranega kodeka. Brez omrezja, ffmpeg, GPU in televizorja.
"""

import importlib.util
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _nadomestek(ime, **imena):
    # Samo ce modula v drevesu ni; pravih modulov ne skrivamo.
    try:
        if importlib.util.find_spec(ime) is not None:
            return
    except (ImportError, ValueError):
        pass
    m = types.ModuleType(ime)
    for k, v in imena.items():
        setattr(m, k, v)
    sys.modules[ime] = m


class _Prazen:
    mozno = False

    def __init__(self, *a, **k):
        pass

    def sprosti_vse(self):
        pass

    def zapri(self):
        pass


_nadomestek("core.link_datoteke", TLS_MAPA="/nikjer", zagotovi_potrdilo=None)
_nadomestek("core.link_mediji", dogodek_v_tipko=lambda d: None)
_nadomestek("core.link_plosek", Plosek=_Prazen)
_nadomestek("core.link_vnos", Vnos=_Prazen)

import pytest  # noqa: E402

import core.link_daljinec as ld  # noqa: E402
import core.link_zaslon as lz  # noqa: E402

VAAPI = "/dev/dri/renderD128"


class _LazniZaslon:
    """Zapise natancen klic zacni (pozicijski in poimenovani argumenti) in vrne izbran kodek."""

    def __init__(self, kodek="h264"):
        self.klici = []
        self.kodek = kodek

    def na_voljo(self):
        return {"dovoljeno": True, "mozno": True}

    def zacni(self, *a, **k):
        self.klici.append((a, k))
        return {"codec": self.kodek, "width": 1920, "height": 1080}


def _start(zaslon, **parametri):
    izidi = []
    ld.izvedi_control("screen.start", parametri, lambda u: None, izidi.append, posiljatelj="tv", zaslon=zaslon)
    assert len(izidi) == 1
    return izidi[0]


def test_brez_zmoznosti_klic_kot_doslej():
    z = _LazniZaslon()
    izid = _start(z, quality="najvisja", screen="")
    # Natanko klic s HEAD (vrstica 160): trije pozicijski argumenti, brez poimenovanih.
    assert z.klici == [(("tv", "najvisja", ""), {})]
    assert izid["ok"] is True and izid["data"]["codec"] == "h264"


def test_veljavne_zmoznosti_gredo_v_zacni():
    z = _LazniZaslon("hevc")
    izid = _start(z, quality="najvisja", codecs=["hevc", "h264"], maxsize={"hevc": [3840, 2160]})
    assert z.klici == [(("tv", "najvisja", ""), {"kodeki": ["hevc", "h264"], "najvecja": {"hevc": [3840, 2160]}})]
    assert izid["data"]["codec"] == "hevc"


def test_meje_seznama_8_vnosov_in_16_znakov():
    z = _LazniZaslon()
    _start(z, codecs=["h264"] * 8)
    _start(z, codecs=["x" * 16, "hevc"])
    _start(z, codecs=[])
    assert [k for _, k in z.klici] == [{"kodeki": ["h264"] * 8}, {"kodeki": ["x" * 16, "hevc"]}, {"kodeki": []}]


@pytest.mark.parametrize("codecs", [
    "hevc",                         # niz ni seznam
    ("hevc", "h264"),               # terka ni seznam (JSON da samo list)
    {"hevc": 1},                    # slovar ni seznam
    ["hevc", 5],                    # element ni niz
    ["hevc", None],
    [b"hevc"],                      # bajti niso niz
    [["hevc"]],                     # gnezden seznam
    ["hevc"] + ["h264"] * 8,        # 9 vnosov
    ["x" * 17, "hevc"],             # niz daljsi od 16 znakov
    7,
    True,
    None,
])
def test_napacen_tip_codecs_prezri(codecs):
    z = _LazniZaslon()
    izid = _start(z, quality="najvisja", codecs=codecs)
    assert z.klici == [(("tv", "najvisja", ""), {})]
    assert izid["ok"] is True and izid["data"]["codec"] == "h264"


@pytest.mark.parametrize("maxsize", [[3840, 2160], "3840x2160", 3840, None, True, ("hevc", [3840, 2160])])
def test_napacen_tip_maxsize_prezri(maxsize):
    z = _LazniZaslon()
    _start(z, codecs=["hevc"], maxsize=maxsize)
    assert z.klici == [(("tv", "srednja", ""), {"kodeki": ["hevc"]})]


def test_seznam_in_slovar_sta_kopiji():
    # Zacni ne dobi istih objektov kot sporocilo (spreminjanje v zacni ne vpliva na parametre).
    z = _LazniZaslon()
    codecs, maxsize = ["hevc"], {"hevc": [3840, 2160]}
    _start(z, codecs=codecs, maxsize=maxsize)
    _, k = z.klici[0]
    assert k["kodeki"] == codecs and k["kodeki"] is not codecs
    assert k["najvecja"] == maxsize and k["najvecja"] is not maxsize


# ------------------------------------------------------------------ s pravim Zaslon.zacni (brez TLS in niti)

def _pravi_zaslon(monkeypatch, vaapi=VAAPI, hevc=True):
    lz._HEVC_MOZEN.clear()
    zagoni = []

    class _Ctx:
        minimum_version = None

        def __init__(self, *a):
            pass

        def load_cert_chain(self, *a):
            pass

    class _Plosek(_Prazen):
        def mozno(self):
            return False

    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(lz, "zagotovi_potrdilo", lambda mapa: ("k", "p", "odtis"))
    monkeypatch.setattr(lz.ssl, "SSLContext", _Ctx)
    monkeypatch.setattr(lz, "_zaslon_geometrija", lambda d: (3840, 2160))
    monkeypatch.setattr(lz, "vaapi_naprava", lambda: vaapi)
    monkeypatch.setattr(lz, "privzeti_monitor", lambda: None)
    monkeypatch.setattr(lz, "kms_na_voljo", lambda: False)
    monkeypatch.setattr(lz, "hevc_vaapi_mozen", lambda f, n, w, h: bool(n) and hevc)
    monkeypatch.setattr(lz.Zaslon, "_streci", lambda self, *a: zagoni.append(a))
    z = lz.Zaslon(ffmpeg="ffmpeg", vklopljeno=True)
    z._plosek = _Plosek()
    return z, zagoni


def _pravi_start(monkeypatch, vaapi=VAAPI, hevc=True, **parametri):
    z, zagoni = _pravi_zaslon(monkeypatch, vaapi, hevc)
    try:
        izid = _start(z, **parametri)
        if z._nit is not None:
            z._nit.join(5)
    finally:
        z.ustavi()
    return izid, zagoni


def test_pravi_zacni_hevc_4k_codec_v_odgovoru(monkeypatch):
    izid, zagoni = _pravi_start(monkeypatch, quality="najvisja", codecs=["hevc", "h264"],
                                maxsize={"hevc": [3840, 2160]})
    d = izid["data"]
    assert izid["ok"] is True and (d["codec"], d["width"], d["height"]) == ("hevc", 3840, 2160)
    ukaz = zagoni[0][2]
    assert ukaz[ukaz.index("-c:v") + 1] == "hevc_vaapi"
    assert "au" not in d


@pytest.mark.parametrize("parametri", [
    {"codecs": "hevc", "maxsize": {"hevc": [3840, 2160]}},
    {"codecs": ["hevc", 1], "maxsize": {"hevc": [3840, 2160]}},
    {"codecs": ["hevc"] * 9, "maxsize": {"hevc": [3840, 2160]}},
    {"codecs": ["hevc", "y" * 17]},
    {"codecs": None, "maxsize": [3840, 2160]},
    {},
])
def test_pravi_zacni_napacen_tip_h264_1080p(monkeypatch, parametri):
    izid, zagoni = _pravi_start(monkeypatch, quality="najvisja", **parametri)
    d = izid["data"]
    assert izid["ok"] is True and (d["codec"], d["width"], d["height"]) == ("h264", 1920, 1080)
    ukaz = zagoni[0][2]
    assert ukaz[ukaz.index("-c:v") + 1] == "h264_vaapi" and ukaz[-3:] == ["-f", "h264", "-"]


def test_pravi_zacni_hevc_brez_kodirnika_h264(monkeypatch):
    izid, _ = _pravi_start(monkeypatch, hevc=False, quality="najvisja", codecs=["hevc"],
                           maxsize={"hevc": [3840, 2160]})
    assert (izid["data"]["codec"], izid["data"]["width"]) == ("h264", 1920)

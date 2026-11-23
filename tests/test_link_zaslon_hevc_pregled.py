"""Pregled fa376944 (bot telefon): meja preizkusov hevc_vaapi (N5). Brez ffmpeg in GPU; NI pognano."""

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


_nadomestek("core.link_datoteke", TLS_MAPA="/nikjer", zagotovi_potrdilo=None)
_nadomestek("core.link_mediji", dogodek_v_tipko=lambda d: None)
_nadomestek("core.link_plosek", Plosek=_Prazen)
_nadomestek("core.link_vnos", Vnos=_Prazen)

import core.link_zaslon as lz  # noqa: E402

VAAPI = "/dev/dri/renderD128"


class _R:
    returncode = 0


def test_televizor_ne_more_zaganjati_neomejeno_preizkusov():
    lz._HEVC_MOZEN.clear()
    klici = []

    def zazeni(ukaz, **k):
        klici.append(ukaz)
        return _R()

    try:
        # Izjave maxsize, ki jih izberi_tok na namizju 3840x2160 spremeni v razlicne velikosti.
        izidi = [lz.hevc_vaapi_mozen("ffmpeg", VAAPI, w, w * 9 // 16 // 2 * 2, zazeni)
                 for w in (3840, 3838, 3836, 3834, 3832, 3830)]
        # Brez popravka: 6 zagonov ffmpeg (vsak do HEVC_PREIZKUS_S) in 6 vnosov v slovarju.
        assert len(klici) == 4
        assert izidi == [True, True, True, True, False, False]
        assert len(lz._HEVC_MOZEN) == 4
        # Ze preizkusena velikost ostane znana brez novega zagona.
        assert lz.hevc_vaapi_mozen("ffmpeg", VAAPI, 3840, 2160, zazeni) is True and len(klici) == 4
    finally:
        lz._HEVC_MOZEN.clear()


def test_izberi_tok_po_meji_h264():
    lz._HEVC_MOZEN.clear()
    try:
        for w in (3840, 3838, 3836, 3834):
            lz._HEVC_MOZEN[("ffmpeg", VAAPI, w, 2160)] = True
        kodek, sirina, visina = lz.izberi_tok(
            ["hevc"], {"hevc": [3000, 2160]}, (3840, 2160), (1920, 1080),
            lambda w, h: lz.hevc_vaapi_mozen("ffmpeg", VAAPI, w, h, lambda *a, **k: _R()))
        assert (kodek, sirina, visina) == ("h264", 1920, 1080)
    finally:
        lz._HEVC_MOZEN.clear()

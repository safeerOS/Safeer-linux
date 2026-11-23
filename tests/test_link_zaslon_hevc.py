"""Preizkus HEVC in 4K v zajemu zaslona (core/link_zaslon.py).

Brez omrezja, brez ffmpeg, brez GPU in brez televizorja: ciste funkcije, zacni/_streci/_crpaj z namisljenimi
procesi in vticnico. Kar je odvisno od strojne opreme (hevc_vaapi, dekoder TV), tu NI preverjeno.
"""

import importlib.util
import io
import json
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

import core.link_zaslon as lz  # noqa: E402
from core.link_zaslon import (OKVIR_SLIKA, OKVIR_ZIG, ZIG_GLAVA, Zaslon, ZigiSlike,  # noqa: E402
                              glava_toka, izberi_tok, ukaz_ffmpeg, zakasnitev_slike)

VAAPI = "/dev/dri/renderD128"


# ------------------------------------------------------------------ pomocniki HEVC

def _hnal(vrsta, prva=True, dolzina=20, stiri=True):
    """Enota NAL H.265: 2 bajta glave (vrsta << 1, temporal_id_plus1 = 1), nato prvi bajt vsebine.

    Za rezino je prvi bit vsebine first_slice_segment_in_pic_flag. Drugi bajt glave je 0x01, da preizkus
    loci branje bita na i+5 (prav) od i+4 (H.264, narobe)."""
    koda = b"\x00\x00\x00\x01" if stiri else b"\x00\x00\x01"
    return koda + bytes([(vrsta << 1) & 0x7E, 0x01]) + bytes([0x80 if prva else 0x40]) + b"\x11" * dolzina


DOLZINA = 4 + 2 + 1 + 20         # _hnal s stirimi bajti zacetne kode


def _hslika(irap=False, rezin=1, aud=True):
    deli = [_hnal(35)] if aud else []
    if irap:
        deli += [_hnal(32), _hnal(33), _hnal(34), _hnal(39), _hnal(19)]
    else:
        deli += [_hnal(1)]
    deli += [_hnal(19 if irap else 1, prva=False, stiri=False) for _ in range(rezin - 1)]
    return b"".join(deli)


class _Vticnica:
    def __init__(self, vrstica=b""):
        self.klici = []
        self._vhod = io.BytesIO(vrstica)

    def sendall(self, b):
        self.klici.append(bytes(b))

    def recv(self, n):
        return self._vhod.read(n)

    def settimeout(self, t):
        pass

    def shutdown(self, how):
        pass

    def close(self):
        pass


class _Proces:
    def __init__(self, kosi):
        self._kosi = list(kosi)
        self.stdout = self
        self.svez = True  # od 42004c09 zig samo za vir s svezimi paketi

    def read(self, n):
        return self._kosi.pop(0) if self._kosi else b""


def _stari_bralnik(tok, znane=(1, 2, 3)):
    i, izid = 0, []
    while i < len(tok):
        vrsta, n = tok[i], int.from_bytes(tok[i + 1:i + 5], "big")
        if vrsta in znane:
            izid.append((vrsta, tok[i + 5:i + 5 + n]))
        i += 5 + n
    return izid


# ------------------------------------------------------------------ meje slik HEVC

def test_hevc_meje_z_aud_in_nastavitvami():
    s = ZigiSlike(None, "hevc")
    prva = _hslika(irap=True, rezin=3)
    druga = _hslika(rezin=2)
    assert s.zacetki(prva + druga) == [0, len(prva)]


def test_hevc_meje_brez_aud_po_first_slice_flag():
    # Brez AUD in brez nastavitev: novo sliko pove samo first_slice_segment_in_pic_flag (bajt i+5).
    s = ZigiSlike(None, "hevc")
    tok = _hnal(1) + _hnal(1, prva=False) + _hnal(1) + _hnal(1, prva=False)
    assert s.zacetki(tok) == [0, 2 * DOLZINA]


def test_h264_first_mb_ostane_na_i_plus_4():
    # H.264 ima en bajt glave enote NAL: first_mb_in_slice je v bajtu i+4. Bajt i+5 je tu namenoma 0x00,
    # da bi branje kot pri HEVC (i+5) zgresilo drugo sliko brez AUD.
    rezina = b"\x00\x00\x00\x01\x41\x80\x00" + b"\x11" * 6
    nadaljnja = b"\x00\x00\x00\x01\x41\x40\x80" + b"\x11" * 6
    s = ZigiSlike(None)
    assert s.zacetki(rezina + nadaljnja + rezina) == [0, 2 * len(rezina)]


def test_hevc_vrsta_iz_bitov_1_do_6():
    # SPS (33) ima prvi bajt 0x42: maska H.264 (& 0x1F) bi dala 2, kar ni nic. Rezina 1 ima 0x02.
    s = ZigiSlike(None, "hevc")
    tok = _hnal(1) + _hnal(33) + _hnal(34) + _hnal(1)
    assert s.zacetki(tok) == [0, DOLZINA]


def test_hevc_pripenski_sei_ne_odpre_slike():
    s = ZigiSlike(None, "hevc")
    tok = _hnal(1) + _hnal(40) + _hnal(1, prva=False) + _hnal(38) + _hnal(1)
    assert s.zacetki(tok) == [0, 4 * DOLZINA]


def test_hevc_predponski_sei_odpre_sliko():
    s = ZigiSlike(None, "hevc")
    tok = _hnal(1) + _hnal(39) + _hnal(1)
    assert s.zacetki(tok) == [0, DOLZINA]


@pytest.mark.parametrize("vrsta", [0, 9, 16, 21])
def test_hevc_meje_rezin_vseh_vrst(vrsta):
    # Rezine 0..9 in 16..21 (tudi BLA 16 in CRA 21) stejejo; prva rezina za rezino odpre novo sliko.
    s = ZigiSlike(None, "hevc")
    tok = _hnal(1) + _hnal(vrsta)
    assert s.zacetki(tok) == [0, DOLZINA]


@pytest.mark.parametrize("vrsta", [10, 15, 22, 31])
def test_hevc_rezervirane_niso_rezine(vrsta):
    s = ZigiSlike(None, "hevc")
    tok = _hnal(1) + _hnal(vrsta) + _hnal(1, prva=False)
    assert s.zacetki(tok) == [0]


@pytest.mark.parametrize("rez", range(1, 7))
def test_hevc_zacetna_koda_in_glava_razdeljeni_med_kosa(rez):
    # Kos se konca v zacetni kodi, v 2-bajtni glavi ali pred bajtom s first_slice_segment_in_pic_flag:
    # mejo najdemo sele v naslednjem kosu (negativen odmik), ne prej in ne dvakrat.
    prva, druga = _hslika(), _hslika(aud=False)
    s = ZigiSlike(None, "hevc")
    assert s.zacetki(prva + druga[:rez]) == [0]
    assert s.zacetki(druga[rez:]) == [-rez]


def test_hevc_cela_glava_in_prvi_bajt_v_kosu():
    prva, druga = _hslika(), _hslika(aud=False)
    s = ZigiSlike(None, "hevc")
    assert s.zacetki(prva + druga[:7]) == [0, len(prva)]
    assert s.zacetki(druga[7:]) == []


def test_hevc_brez_ziga_tudi_z_zakasnitvijo_v_crpaj():
    # Seja HEVC: zig slike ni izmerjen, zato okvirja 4 za sliko ni, tudi ce je _zakasnitev_slike zastarela.
    z = Zaslon()
    z._zakasnitev_slike = 13.5
    kosi = [_hslika(irap=True), _hslika(), _hslika()]
    v = _Vticnica()
    z._crpaj(_Proces(kosi), OKVIR_SLIKA, v, 32 * 1024, kodek="hevc")
    tok = b"".join(v.klici)
    assert not any(t == OKVIR_ZIG for t, _ in _stari_bralnik(tok, (OKVIR_ZIG,)))
    assert _stari_bralnik(tok) == [(OKVIR_SLIKA, k) for k in kosi]


def test_h264_crpaj_z_zakasnitvijo_se_vedno_zig():
    # Nadzor: ista pot z H.264 ziga se (okvir 4 z "bajt" kot prej).
    z = Zaslon()
    z._zakasnitev_slike = 13.5
    idr = (b"\x00\x00\x00\x01\x67\x80" + b"\x11" * 8 + b"\x00\x00\x00\x01\x65\x80" + b"\x11" * 8)
    v = _Vticnica()
    stara = lz.ura_ms
    lz.ura_ms = lambda: 100.0
    try:
        z._crpaj(_Proces([idr]), OKVIR_SLIKA, v, 32 * 1024)
    finally:
        lz.ura_ms = stara
    zigi = [json.loads(b) for _, b in _stari_bralnik(b"".join(v.klici), (OKVIR_ZIG,))]
    assert zigi == [{"vrsta": OKVIR_SLIKA, "zig_ms": 86, "bajt": 0}]


def test_zakasnitev_slike_hevc_none():
    assert zakasnitev_slike(None, 1920, 1080, (1920, 1080)) == 13.5
    assert zakasnitev_slike(None, 1920, 1080, (1920, 1080), "hevc") is None
    assert zakasnitev_slike(VAAPI, 3840, 2160, (3840, 2160), "hevc") is None


# ------------------------------------------------------------------ izbor kodeka in velikosti

class _Mozen:
    def __init__(self, izid=True):
        self.izid = izid
        self.klici = []

    def __call__(self, w, h):
        self.klici.append((w, h))
        return self.izid


IZVOR_4K = (3840, 2160)
OSNOVA = (1920, 1080)


def test_stari_televizor_brez_seznama_ostane_h264_1080p():
    m = _Mozen()
    assert izberi_tok(None, None, IZVOR_4K, OSNOVA, m) == ("h264", 1920, 1080)
    assert izberi_tok(None, {"hevc": [3840, 2160]}, IZVOR_4K, OSNOVA, m) == ("h264", 1920, 1080)
    assert m.klici == []        # preizkusa kodirnika brez zelje televizorja ne zaganjamo


def test_h264_pred_hevc_v_seznamu():
    m = _Mozen()
    assert izberi_tok(["h264", "hevc"], {"hevc": [3840, 2160]}, IZVOR_4K, OSNOVA, m) == ("h264", 1920, 1080)
    assert izberi_tok(["vp9", "h264", "hevc"], None, IZVOR_4K, OSNOVA, m) == ("h264", 1920, 1080)
    assert m.klici == []


def test_hevc_brez_kodirnika_ostane_h264():
    m = _Mozen(False)
    assert izberi_tok(["hevc", "h264"], {"hevc": [3840, 2160]}, IZVOR_4K, OSNOVA, m) == ("h264", 1920, 1080)
    assert m.klici == [(3840, 2160)]


def test_hevc_brez_izjave_velikosti_ostane_1080p():
    m = _Mozen()
    assert izberi_tok(["hevc", "h264"], None, IZVOR_4K, OSNOVA, m) == ("hevc", 1920, 1080)
    assert m.klici == [(1920, 1080)]


def test_hevc_4k_samo_ob_izjavi_in_polni_kakovosti():
    m = _Mozen()
    assert izberi_tok(["hevc", "h264"], {"hevc": [3840, 2160]}, IZVOR_4K, OSNOVA, m) == ("hevc", 3840, 2160)
    assert izberi_tok(["hevc", "h264"], {"hevc": [3840, 2160]}, IZVOR_4K, OSNOVA, m, polna=False) == \
        ("hevc", 1920, 1080)
    # Izjava za drug kodek ne velja za HEVC.
    assert izberi_tok(["hevc", "h264"], {"h264": [3840, 2160]}, IZVOR_4K, OSNOVA, m) == ("hevc", 1920, 1080)


def test_hevc_4k_omejen_na_najvec_hevc_in_brez_povecave():
    m = _Mozen()
    assert izberi_tok(["hevc"], {"hevc": [7680, 4320]}, (7680, 4320), OSNOVA, m) == ("hevc", 3840, 2160)
    # Izvor 2560x1440: brez prevzorcenja (ne povecamo in ne pomanjsamo, ker je pod mejo).
    assert izberi_tok(["hevc"], {"hevc": [3840, 2160]}, (2560, 1440), OSNOVA, m) == ("hevc", 2560, 1440)
    # Izjava manjsa od 4K: meja je izjava.
    assert izberi_tok(["hevc"], {"hevc": [2560, 1440]}, IZVOR_4K, OSNOVA, m) == ("hevc", 2560, 1440)


def test_hevc_izjava_pod_osnovo_pomeni_h264():
    m = _Mozen()
    assert izberi_tok(["hevc", "h264"], {"hevc": [1280, 720]}, IZVOR_4K, OSNOVA, m) == ("h264", 1920, 1080)
    assert m.klici == []


@pytest.mark.parametrize("izjava", [{"hevc": ["3840", "2160"]}, {"hevc": [True, 2160]}, {"hevc": [3840]},
                                    {"hevc": [3840, 2160, 60]}, {"hevc": [3840.0, 2160.0]}, {"hevc": [-1, 2160]},
                                    {"hevc": [99999, 99999]}, [3840, 2160], "4k"])
def test_neveljavna_izjava_ne_da_4k(izjava):
    m = _Mozen()
    assert izberi_tok(["hevc", "h264"], izjava, IZVOR_4K, OSNOVA, m) == ("hevc", 1920, 1080)


def test_seznam_kodekov_brez_ugibanja():
    m = _Mozen()
    assert izberi_tok([" HEVC ", "h264"], None, IZVOR_4K, OSNOVA, m)[0] == "hevc"
    assert izberi_tok("hevc", None, IZVOR_4K, OSNOVA, m)[0] == "h264"          # niz ni seznam
    assert izberi_tok([None, 5, "h265"], None, IZVOR_4K, OSNOVA, m)[0] == "h264"
    assert izberi_tok(["x"] * 8 + ["hevc"], None, IZVOR_4K, OSNOVA, m)[0] == "h264"   # najvec 8 vnosov


def test_hevc_vaapi_mozen_preizkus_in_spomin():
    lz._HEVC_MOZEN.clear()
    klici = []

    class _R:
        returncode = 0

    def zazeni(ukaz, **k):
        klici.append(ukaz)
        return _R()

    assert lz.hevc_vaapi_mozen("ffmpeg", None, 3840, 2160, zazeni) is False
    assert lz.hevc_vaapi_mozen("", VAAPI, 3840, 2160, zazeni) is False
    assert klici == []
    assert lz.hevc_vaapi_mozen("ffmpeg", VAAPI, 3840, 2160, zazeni) is True
    assert lz.hevc_vaapi_mozen("ffmpeg", VAAPI, 3840, 2160, zazeni) is True
    assert len(klici) == 1
    u = klici[0]
    assert u[u.index("-c:v") + 1] == "hevc_vaapi" and "color=black:size=3840x2160:rate=30" in u
    assert "libx265" not in u

    def pade(ukaz, **k):
        raise OSError("ni ffmpeg")

    assert lz.hevc_vaapi_mozen("ffmpeg", VAAPI, 1920, 1080, pade) is False

    class _Napaka:
        returncode = 1

    assert lz.hevc_vaapi_mozen("ffmpeg", VAAPI, 2560, 1440, lambda u, **k: _Napaka()) is False
    lz._HEVC_MOZEN.clear()


# ------------------------------------------------------------------ ukaz ffmpeg

H264_VAAPI_4K_V_1080 = [
    'ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-f', 'x11grab', '-draw_mouse', '1', '-framerate',
    '60', '-video_size', '3840x2160', '-i', ':0', '-vaapi_device', '/dev/dri/renderD128', '-vf',
    'scale=1920:1080:flags=lanczos,format=nv12,hwupload', '-c:v', 'h264_vaapi', '-profile:v', 'high', '-rc_mode',
    'CQP', '-qp', '16', '-g', '60', '-bf', '0', '-flags', '+low_delay', '-f', 'h264', '-']
H264_X264_1080 = [
    'ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-f', 'x11grab', '-draw_mouse', '1', '-framerate',
    '60', '-video_size', '1920x1080', '-i', ':0', '-vf', 'format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast',
    '-tune', 'zerolatency', '-profile:v', 'high', '-b:v', '24M', '-maxrate', '24M', '-bufsize', '1M', '-g', '60',
    '-bf', '0', '-flags', '+low_delay', '-f', 'h264', '-']


def test_ukaz_h264_enak_kot_prej():
    # Seznama sta izpisana iz osnove (priloga 689dac5c): za H.264 se ukaz ne spremeni niti za en argument.
    assert ukaz_ffmpeg(":0", 1920, 1080, 3840, 2160, 60, "24M", VAAPI, "ffmpeg", 16) == H264_VAAPI_4K_V_1080
    assert ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", None, "ffmpeg", 16) == H264_X264_1080


def test_ukaz_hevc_vaapi_4k():
    u = ukaz_ffmpeg(":0", 3840, 2160, 3840, 2160, 60, "24M", VAAPI, "ffmpeg", 16, "hevc")
    assert u[u.index("-c:v") + 1] == "hevc_vaapi"
    assert u[u.index("-profile:v") + 1] == "main"
    assert u[u.index("-vf") + 1] == "format=nv12,hwupload"          # brez lestvice pri 4K izvoru
    assert u[-3:] == ["-f", "hevc", "-"]
    assert u[u.index("-qp") + 1] == "16" and u[u.index("-bf") + 1] == "0" and u[u.index("-g") + 1] == "60"
    # Razen kodirnika, profila in oblike enako kot H.264 (zajem, CQP, GOP, brez B-slik).
    h = ukaz_ffmpeg(":0", 3840, 2160, 3840, 2160, 60, "24M", VAAPI, "ffmpeg", 16)
    zamenjave = {"h264_vaapi": "hevc_vaapi", "high": "main", "h264": "hevc"}
    assert [zamenjave.get(x, x) for x in h] == u


def test_ukaz_hevc_brez_vaapi_ni_libx265():
    # Mainov dogovor: brez VAAPI je tok H.264 (x264), libx265 nikoli; izbira kodeka (izberi_tok) HEVC brez naprave sploh ne da.
    u = ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", None, "ffmpeg", 16, "hevc")
    assert u[u.index("-c:v") + 1] == "libx264" and "libx265" not in u and u[-3:] == ["-f", "h264", "-"]


# ------------------------------------------------------------------ glava

GLAVA_H264 = ('{"v": 2, "w": 1920, "h": 1080, "fps": 60, "zvok": {"hz": 48000, "kanali": 2, "oblika": "s16le"}, '
              '"vnos": false, "plosek": false, "zig": {"okvir": 4, "ura": "monotonic_ms"}}')


def test_glava_h264_bajt_za_bajtom_kot_prej():
    g = glava_toka({"width": 1920, "height": 1080, "fps": 60}, True, False, False)
    assert json.dumps(g) == GLAVA_H264
    assert "kodek" not in glava_toka({"width": 1920, "height": 1080, "fps": 60}, True, False, False, "h264")


def test_glava_hevc_ima_kodek():
    g = glava_toka({"width": 3840, "height": 2160, "fps": 60}, False, False, False, "hevc")
    assert g["kodek"] == "hevc" and (g["w"], g["h"]) == (3840, 2160)
    assert g["zig"] == ZIG_GLAVA and g["zvok"] is None


def _streci(kodek):
    z = Zaslon()
    z._zeton = "zeton"
    z._slika = {"width": 3840, "height": 2160, "fps": 60}

    class _Plosek(_Prazen):
        def mozno(self):
            return False

    z._plosek = _Plosek()
    v = _Vticnica(b"SAFEER-ZASLON zeton\n")

    class _Posluh:
        def accept(self):
            return v, None

        def shutdown(self, how):
            pass

        def close(self):
            pass

    class _Ctx:
        def wrap_socket(self, s, server_side):
            return s

    stari = lz._ProcesSlike

    def _brez_procesa(*a, **k):
        raise OSError("v preizkusu ni ffmpeg")

    lz._ProcesSlike = _brez_procesa
    posluh = _Posluh()
    # Mainov _streci: sprejem povezave (_sprejmi), stevilka seje in vrata seje; kodek seje je z.\_kodek.
    z._seja_st = 1
    z._posluh = posluh
    z._kodek = kodek or "h264"
    z._sprejmi = lambda p, c: (v, None)
    try:
        z._streci(posluh, _Ctx(), ["nic"], 1)
    finally:
        lz._ProcesSlike = stari
    return json.loads(v.klici[0].decode("utf-8"))


def test_streci_glava_po_kodeku_seje():
    assert _streci("hevc")["kodek"] == "hevc"
    # Mainova glava ima "kodek" vedno (tudi h264); stari televizor ga prezre.
    assert _streci(None)["kodek"] == "h264"
    assert _streci("h264")["kodek"] == "h264"
    assert _streci("hevc")["zig"] == ZIG_GLAVA


# ------------------------------------------------------------------ zacni (brez TLS, brez niti)

def _zacni(monkeypatch, vaapi=VAAPI, hevc=True, kms=False, **kw):
    lz._HEVC_MOZEN.clear()
    zagoni = []

    class _Ctx:
        minimum_version = None

        def __init__(self, *a):
            pass

        def load_cert_chain(self, *a):
            pass

    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(lz, "zagotovi_potrdilo", lambda mapa: ("k", "p", "odtis"))
    monkeypatch.setattr(lz.ssl, "SSLContext", _Ctx)
    monkeypatch.setattr(lz, "_zaslon_geometrija", lambda d: IZVOR_4K)
    monkeypatch.setattr(lz, "_deljeni_monitor", lambda: None)
    monkeypatch.setattr(lz, "gpu_lestvica_mozna", lambda *a, **k: False)    # preizkus graficne je odvisen od racunalnika
    monkeypatch.setattr(lz, "vaapi_naprava", lambda *a, **k: vaapi)
    monkeypatch.setattr(lz, "privzeti_monitor", lambda: None)
    monkeypatch.setattr(lz, "hevc_vaapi_mozen", lambda f, n, w, h: bool(n) and hevc)
    monkeypatch.setattr(Zaslon, "_streci", lambda self, *a: zagoni.append(a))

    class _Plosek(_Prazen):
        def mozno(self):
            return False

    z = Zaslon(ffmpeg="ffmpeg", vklopljeno=True, kms=kms)
    z._plosek = _Plosek()
    try:
        odgovor = z.zacni("tv", **kw)
        z._nit.join(5)
    finally:
        z.ustavi()
    return z, odgovor, zagoni[0]


def test_zacni_privzeto_h264_1080p(monkeypatch):
    z, odgovor, args = _zacni(monkeypatch)
    ukaz, kms, kodek = args[2], args[5], z._kodek
    assert kms is None
    assert (odgovor["codec"], odgovor["width"], odgovor["height"]) == ("h264", 1920, 1080)
    assert kodek == "h264" and z._kodek == "h264"
    assert ukaz == H264_VAAPI_4K_V_1080


def test_zacni_hevc_4k_ob_izrecni_zmoznosti(monkeypatch):
    z, odgovor, args = _zacni(monkeypatch, kodeki=["hevc", "h264"], najvecja={"hevc": [3840, 2160]})
    ukaz, kms, kodek = args[2], args[5], z._kodek
    assert (odgovor["codec"], odgovor["width"], odgovor["height"]) == ("hevc", 3840, 2160)
    assert kodek == "hevc" and kms is None and z._hevc_veliki
    assert ukaz[ukaz.index("-c:v") + 1] == "hevc_vaapi" and ukaz[-3:] == ["-f", "hevc", "-"]
    assert z._zakasnitev_slike is None


def test_zacni_hevc_brez_vaapi_h264(monkeypatch):
    z, odgovor, args = _zacni(monkeypatch, vaapi=None, kodeki=["hevc", "h264"], najvecja={"hevc": [3840, 2160]})
    assert (odgovor["codec"], odgovor["width"], odgovor["height"]) == ("h264", 1920, 1080)
    assert "libx264" in args[2] and "libx265" not in args[2]


def test_zacni_nizja_kakovost_brez_4k(monkeypatch):
    z, odgovor, args = _zacni(monkeypatch, kakovost="srednja", kodeki=["hevc"], najvecja={"hevc": [3840, 2160]})
    assert (odgovor["codec"], odgovor["width"], odgovor["height"]) == ("hevc", 1920, 1080)


def test_zacni_kms_samo_h264(monkeypatch):
    monkeypatch.setattr(lz, "kms_na_voljo", lambda: True)
    monkeypatch.setattr(lz, "kms_monitorji", lambda: 1)
    monkeypatch.setattr(lz, "seja_aktivna", lambda: True)
    _, _, args = _zacni(monkeypatch, kms=True)
    assert args[5] == {"sirina": 1920, "visina": 1080, "fps": 60, "kodek": "h264", "qp": 16}
    z, _, args = _zacni(monkeypatch, kms=True, kodeki=["hevc"], najvecja={"hevc": [3840, 2160]})
    assert args[5] is None and z._kodek == "hevc"


def _streci_z_bralnikom(monkeypatch, kodek, velika):
    z = Zaslon()
    z._zeton = "zeton"
    z._slika = {"width": 3840 if velika else 1920, "height": 2160 if velika else 1080, "fps": 60}

    class _Plosek(_Prazen):
        def mozno(self):
            return False

    z._plosek = _Plosek()
    v = _Vticnica(b"SAFEER-ZASLON zeton\n")

    class _Posluh:
        def shutdown(self, how):
            pass

        def close(self):
            pass

    class _Slika:
        def poll(self):
            return 0

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    klici = []
    z._crpaj = lambda *a, **k: klici.append((a, k))
    # Lazni bralnik ne da slike: _preveri_hevc bi zapahnil HEVC za ves proces (hevc_odpovedal) - stanje je samo v tem preizkusu.
    monkeypatch.setattr(lz, "_HEVC", {})
    monkeypatch.setattr(lz, "odpri_sliko", lambda zazeni, kms, seja=0: (_Slika(), False))
    posluh = _Posluh()
    z._seja_st, z._posluh, z._kodek, z._hevc_veliki = 1, posluh, kodek, velika
    z._sprejmi = lambda p, c: (v, None)
    z._streci(posluh, object(), ["nic"], 1)
    return [(a, k) for a, k in klici if a[1] == OKVIR_SLIKA]


def test_streci_poda_kodek_bralniku_slike(monkeypatch):
    # Bralnik slike (_crpaj) mora dobiti kodek seje, sicer bi meje slik HEVC iskal kot H.264.
    # Velika slika (4K) je mogoca samo s HEVC: kodek_za_pot je v domacem omrezju ne znizi na H.264.
    slika = _streci_z_bralnikom(monkeypatch, "hevc", True)
    assert len(slika) == 1 and slika[0][1]["kodek"] == "hevc"


def test_streci_h264_bralnik_dobi_kodek_h264(monkeypatch):
    slika = _streci_z_bralnikom(monkeypatch, "h264", False)
    assert len(slika) == 1 and slika[0][1]["kodek"] == "h264" and slika[0][0][3] == 32 * 1024


def test_brez_kljuca_au():
    g = glava_toka({"width": 3840, "height": 2160, "fps": 60}, True, False, False, "hevc")
    assert "au" not in g
    assert "au" not in glava_toka({"width": 1920, "height": 1080, "fps": 60}, True, False, False)


def test_zacni_hevc_odgovor_brez_au(monkeypatch):
    _, odgovor, _ = _zacni(monkeypatch, kodeki=["hevc"], najvecja={"hevc": [3840, 2160]})
    assert odgovor["codec"] == "hevc" and "au" not in odgovor


# ------------------------------------------------------------------ primerjava s HEAD (3a65bfd1, main 1.0.128)
#
# HEAD se nalozi iz git (git show <ref>:core/link_zaslon.py) ali iz datoteke v SAFEER_HEAD_LINK_ZASLON.
# Ce ni ne enega ne drugega, se preizkusa preskocita (skip) - takrat H.264 varujeta le zlata seznama zgoraj.

KOREN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HEAD_REF = os.environ.get("SAFEER_HEAD_REF", "3a65bfd1")


@pytest.fixture(scope="module")
def head():
    import subprocess
    pot = os.environ.get("SAFEER_HEAD_LINK_ZASLON")
    if pot:
        with open(pot, encoding="utf-8") as f:
            vir = f.read()
    else:
        try:
            r = subprocess.run(["git", "show", HEAD_REF + ":core/link_zaslon.py"], cwd=KOREN,
                               capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            pytest.skip("ni git za HEAD")
        if r.returncode != 0:
            pytest.skip("HEAD %s ni na voljo" % HEAD_REF)
        vir = r.stdout
    m = types.ModuleType("core._head_link_zaslon")
    m.__file__ = "<head %s>" % HEAD_REF
    sys.modules[m.__name__] = m
    exec(compile(vir, m.__file__, "exec"), m.__dict__)
    assert not hasattr(m, "izberi_tok")         # res stara razlicica, ne ta
    return m


VELIKOSTI = [(1920, 1080, 1920, 1080), (1920, 1080, 3840, 2160), (1280, 720, 2560, 1440),
             (1366, 768, 1366, 768), (1600, 900, 3200, 1800)]


def test_head_ukaz_h264_argument_za_argumentom(head):
    n = 0
    for display in (":0", ":1"):
        for s, v, iz_s, iz_v in VELIKOSTI:
            for fps in (30, 60):
                for bitrate in ("8M", "24M"):
                    for vaapi in (None, VAAPI, "/dev/dri/renderD129"):
                        for ffmpeg in ("ffmpeg", "/usr/bin/ffmpeg"):
                            for qp in (16, 20, 24, 28):
                                a = (display, s, v, iz_s, iz_v, fps, bitrate, vaapi, ffmpeg, qp)
                                pricakovano = head.ukaz_ffmpeg(*a)
                                assert ukaz_ffmpeg(*a) == pricakovano, a
                                assert ukaz_ffmpeg(*a, "h264") == pricakovano, a
                                assert ukaz_ffmpeg(*a, kodek="h264") == pricakovano, a
                                n += 1
    assert n == 2 * len(VELIKOSTI) * 2 * 2 * 3 * 2 * 4
    # Privzeti argumenti (brez ffmpeg in qp) enaki kot na HEAD.
    assert ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", None) == \
        head.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", None)


def _zacni_v(mod, monkeypatch, vaapi, kms, kakovost, izvor, **kw):
    if hasattr(mod, "_HEVC_MOZEN"):
        mod._HEVC_MOZEN.clear()
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
    monkeypatch.setattr(mod, "zagotovi_potrdilo", lambda mapa: ("k", "p", "odtis"))
    monkeypatch.setattr(mod.ssl, "SSLContext", _Ctx)
    monkeypatch.setattr(mod, "_zaslon_geometrija", lambda d: izvor)
    monkeypatch.setattr(mod, "vaapi_naprava", lambda *a, **k: vaapi)
    monkeypatch.setattr(mod, "privzeti_monitor", lambda: None)
    monkeypatch.setattr(mod, "_deljeni_monitor", lambda: None)
    monkeypatch.setattr(mod, "gpu_lestvica_mozna", lambda *a, **k: False)
    if hasattr(mod, "kms_na_voljo"):
        monkeypatch.setattr(mod, "kms_na_voljo", lambda: True)
        monkeypatch.setattr(mod, "kms_monitorji", lambda: 1)
        monkeypatch.setattr(mod, "seja_aktivna", lambda: True)
    if hasattr(mod, "hevc_vaapi_mozen"):
        monkeypatch.setattr(mod, "hevc_vaapi_mozen", lambda f, n, w, h: True)
    monkeypatch.setattr(mod.Zaslon, "_streci", lambda self, *a: zagoni.append(a))
    z = mod.Zaslon(ffmpeg="ffmpeg", vklopljeno=True, **({"kms": kms} if hasattr(mod, "kms_na_voljo") else {}))
    z._plosek = _Plosek()
    try:
        odgovor = z.zacni("tv", kakovost, **kw)
        if z._nit is not None:
            z._nit.join(5)
    finally:
        z.ustavi()
    odgovor = {k: v for k, v in odgovor.items() if k not in ("port", "fp", "token")}
    kms_arg = zagoni[0][5] if len(zagoni[0]) > 5 else None
    return odgovor, zagoni[0][2], kms_arg


@pytest.mark.parametrize("vaapi", [None, VAAPI])
@pytest.mark.parametrize("kms", [False, True])
@pytest.mark.parametrize("izvor", [(3840, 2160), (1920, 1080), (2560, 1440), (1920, 1200), (1280, 1024)])
@pytest.mark.parametrize("zmoznosti", [{}, {"kodeki": None, "najvecja": None}, {"kodeki": ["h264", "hevc"]},
                                       {"kodeki": "hevc"}, {"najvecja": {"hevc": [3840, 2160]}}])
def test_head_zacni_h264_enako(head, monkeypatch, vaapi, kms, izvor, zmoznosti):
    for kakovost in sorted(lz.KAKOVOSTI):
        star = _zacni_v(head, monkeypatch, vaapi, kms, kakovost, izvor)
        nov = _zacni_v(lz, monkeypatch, vaapi, kms, kakovost, izvor, **zmoznosti)
        # Odgovor in ukaz (args[2]) enaka kot na HEAD (main brez KMS in 4K); zahteva KMS samo, kjer jo main ne pozna.
        assert nov[:2] == star[:2], (kakovost, zmoznosti)
        assert star[2] is None and (nov[2] is None or kms), (kakovost, zmoznosti)

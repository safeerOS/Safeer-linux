"""Preizkus zigov zajema (okvir 4) za sliko in zvok.

Brez omrezja, brez ffmpeg in brez zaslona: ciste funkcije z uro, ki jo poda preizkus, ter _crpaj in
_streci z namisljenimi procesi in vticnico.
"""

import importlib.util
import io
import json
import os
import ssl
import subprocess
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _nadomestek(ime, **imena):
    # Samo ce modula v drevesu ni (npr. preizkus izven projekta); pravih modulov ne skrivamo.
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

import core.link_zaslon as lz  # noqa: E402
from core.link_zaslon import (OKVIR_SLIKA, OKVIR_ZIG, OKVIR_ZVOK, ZIG_GLAVA, Zaslon,  # noqa: E402
                              ZigiSlike, ZigiZvoka, _okvir_z_zigom)

KOS = 1920          # 10 ms zvoka 48 kHz, 2 kanala, s16le


# ------------------------------------------------------------------ pomocniki

def _stari_bralnik(tok: bytes, znane=(1, 2, 3)):
    """Bralnik starega televizorja: okvirje neznane vrste preskoci."""
    i, izid = 0, []
    while i < len(tok):
        vrsta, n = tok[i], int.from_bytes(tok[i + 1:i + 5], "big")
        if vrsta in znane:
            izid.append((vrsta, tok[i + 5:i + 5 + n]))
        i += 5 + n
    return izid


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
    #: Navaden proces brez zamenjave: vsak kos je sveze prebran (_crpaj brez svez ziga slike ne da).
    svez = True

    def __init__(self, kosi):
        self._kosi = list(kosi)
        self.stdout = self

    def read(self, n):
        return self._kosi.pop(0) if self._kosi else b""


def _crpaj(kosi, vrsta, casi, zakasnitev=None):
    z = Zaslon()
    z._zakasnitev_slike = zakasnitev
    ura = iter(casi)
    stara = lz.ura_ms
    lz.ura_ms = lambda: next(ura)
    try:
        v = _Vticnica()
        z._crpaj(_Proces(kosi), vrsta, v, 32 * 1024, fps=None)
    finally:
        lz.ura_ms = stara
    return v.klici


def _zigi(tok):
    return [json.loads(v) for t, v in _stari_bralnik(tok, (OKVIR_ZIG,))]


# ------------------------------------------------------------------ zvok

def test_zvok_zig_iz_stetja_ne_iz_ure_branja():
    z = ZigiZvoka()
    # Enakomerno branje: zig = cas branja - 10 ms (trajanje kosa), naprej natanko po 10 ms.
    zigi = [z.zig(KOS, 1000.0 + 10 * k) for k in range(50)]
    assert zigi[0] is None                              # prvi kos: sunek ali ne, ne vemo
    assert all(abs(zigi[k] - (990.0 + 10 * k)) < 1e-9 for k in range(1, 50))


def test_zvok_tresenje_ne_premakne_ziga():
    z = ZigiZvoka()
    tres = [0, 7, 3, 15, 1, 9, 0, 30, 2, 5] * 20      # zakasnitev branja do 30 ms
    zigi = [z.zig(KOS, 1000.0 + 10 * k + tres[k]) for k in range(len(tres))]
    assert all(abs(zigi[k] - (990.0 + 10 * k)) < 1e-9 for k in range(1, len(tres)))
    assert z.poravnav == 0


def test_zvok_sunek_ob_zagonu_ne_zamakne_ziga():
    z = ZigiZvoka()
    # Prvih 20 kosov pride naenkrat (zaostanek pulse) ob t=1200; nato tok v realnem casu.
    zigi = [z.zig(KOS, 1200.0) for _ in range(20)]
    zigi += [z.zig(KOS, 1200.0 + 10 * k) for k in range(1, 60)]
    # Med sunkom zig ni znan (vsak kos premakne zacetek nazaj); po njem je tocen.
    assert zigi[:20] == [None] * 20
    assert all(abs(zigi[k] - (1000.0 + 10 * k)) < 1e-9 for k in range(20, len(zigi)))


def test_zvok_vrzel_poravna_zig_med_zaostankom_brez_ziga():
    z = ZigiZvoka()
    for k in range(30):
        z.zig(KOS, 1000.0 + 10 * k)
    # Pulse izpusti 100 ms: od zdaj vsak kos pride 100 ms pozneje, kot pravi stetje.
    zigi = [z.zig(KOS, 1400.0 + 10 * k) for k in range(60)]
    assert z.poravnav == 1
    assert z.zadnja_poravnava_ms == 100.0
    # Dokler stetje zaostaja (> ZVOK_PORAVNAJ_MS), zig ni znan: prej je bil 100 ms prezgodnji (1290
    # namesto 1390). Po poravnavi (po ZVOK_OKNO_MS) je zig spet cas branja - 10 ms.
    assert zigi[:20] == [None] * 20
    assert all(abs(zigi[k] - (1390.0 + 10 * k)) < 1e-9 for k in range(20, 60))
    # Zig ne gre nikoli nazaj.
    assert all(b > a for a, b in zip(zigi[20:], zigi[21:]))


def test_zvok_zastoj_pisanja_ni_vrzel_nad_mejo_brez_ziga():
    z = ZigiZvoka()
    for k in range(30):
        z.zig(KOS, 1000.0 + 10 * k)
    # Vticnica zastane 80 ms, nato se zaostanek prebere v sunku in tok se ujame.
    sunek = [z.zig(KOS, 1380.0) for _ in range(9)]
    zigi = [z.zig(KOS, 1390.0 + 10 * k) for k in range(40)]
    assert z.poravnav == 0
    # Zaostanek 80, 70, 60, 50 ms (> ZVOK_PORAVNAJ_MS): od vrzeli se ne loci, zato zig ni znan.
    assert sunek[:4] == [None] * 4
    # Od zaostanka <= 40 ms naprej so zigi pravi (stetje), ne cas branja.
    assert all(abs(sunek[k] - (1290.0 + 10 * k)) < 1e-9 for k in range(4, 9))
    assert abs(zigi[0] - 1380.0) < 1e-9


def test_zvok_zig_ms_po_zaokrozitvi_ne_gre_nazaj():
    z = ZigiZvoka()
    # Kratko branje (96 B = 0,5 ms): drugi kos ima zig 999,5 (na TV 1000), tretji 999,0 (na TV 999).
    zigi = [z.zig(KOS, 1000.0), z.zig(96, 1000.0), z.zig(KOS, 1009.0), z.zig(KOS, 1019.0)]
    assert zigi[0] is None
    assert abs(zigi[1] - 999.5) < 1e-9
    assert zigi[2] is None                      # 999 < 1000: zig_ms bi sel nazaj
    assert abs(zigi[3] - 1009.0) < 1e-9         # nato spet znan
    poslani = [int(round(x)) for x in zigi if x is not None]
    assert poslani == sorted(poslani)


def test_zvok_po_velikem_popravku_navzdol_zig_takoj_znan():
    # Kontrola N3 (brez popravka kode): ura branja je monotona, zato pravi padec zacetka nastane
    # samo s sunkom. Zakasnitev 90 ms izgine: 9 kosov naenkrat ob 1160, nato spet realni cas.
    z = ZigiZvoka()
    zigi = [z.zig(KOS, 1100.0 + 10 * k) for k in range(7)]
    sunek = [z.zig(KOS, 1160.0) for _ in range(9)]
    po = [z.zig(KOS, 1170.0 + 10 * k) for k in range(5)]
    assert zigi[0] is None
    assert all(abs(zigi[k] - (1090.0 + 10 * k)) < 1e-9 for k in range(1, 7))   # zadnji poslan 1150
    assert sunek == [None] * 9                  # vsak kos sunka premakne zacetek nazaj za 10 ms
    assert z._zacetek == 1000.0                 # zacetek je padel za 90 ms (> ZVOK_TOCNOST_MS)
    # Prvi kos po sunku je takoj znan in vecji od zadnjega poslanega: varovalo Z3 ga ne zavrne.
    assert all(abs(po[k] - (1160.0 + 10 * k)) < 1e-9 for k in range(5))


def test_zvok_velik_padec_ne_izklopi_varovala_z3():
    # Kontrola N3: po velikem padcu je naslednji zig lahko manjsi od poslanega le za manj kot
    # ZVOK_TOCNOST_MS (kratko branje); tak zig varovalo se vedno zavrne (Z3 velja tudi po padcu).
    z = ZigiZvoka()
    zigi = [z.zig(KOS, 1000.0), z.zig(96, 1000.0), z.zig(KOS, 1000.0), z.zig(KOS, 1009.2)]
    assert zigi[0] is None
    assert abs(zigi[1] - 999.5) < 1e-9          # na TV 1000
    assert zigi[2] is None                      # zacetek pade za 10 ms: neznan
    assert zigi[3] is None                      # 999,2 -> 999 < 1000: zig_ms bi sel nazaj
    poslani = [int(round(x)) for x in zigi if x is not None]
    assert poslani == sorted(poslani)


def test_zvok_pocasno_praznjenje_zaloge_ne_da_poznih_zigov():
    z = ZigiZvoka()
    # 30 kosov enakomerno, nato bralec 100 ms obstane (sendall) in zalogo prazni po 9,5 ms na kos (10 ms zvoka).
    casi = [1000.0 + 10 * k for k in range(30)]
    casi += [1400.0 + 9.5 * (k - 30) for k in range(30, 231)]
    casi += [1000.0 + 10 * k for k in range(231, 300)]
    zigi = [z.zig(KOS, c) for c in casi]
    # Kos k je zajet ob 990 + 10 k. Brez popravka gre po lazni poravnavi (k = 49) kos 50 z zigom 1580 (90 ms pozno).
    assert all(abs(zigi[k] - (990.0 + 10 * k)) <= lz.ZVOK_TOCNOST_MS for k in range(300) if zigi[k] is not None)
    assert zigi[299] is not None


def test_zvok_poravnava_v_dnevniku_in_brez_okvirja_4(capsys):
    kosi = [b"\x01" * KOS] * 51
    casi = [1000.0 + 10 * k for k in range(30)] + [1400.0 + 10 * k for k in range(21)]
    tok = b"".join(_crpaj(kosi, OKVIR_ZVOK, casi))
    zigi = _zigi(tok)
    # Kosi 30..49 (zaostanek 100 ms) brez ziga; kos 50 po poravnavi spet z zigom.
    assert [x["bajt"] for x in zigi] == [KOS * k for k in range(1, 30)] + [KOS * 50]
    assert zigi[-1]["zig_ms"] == 1590
    err = capsys.readouterr().err
    assert "dogodek=zvok_poravnava" in err and " ms=100 stevilo=1" in err


def test_zvok_poravnava_v_dnevniku_enkrat(capsys):
    # Poravnava ob kosu 49; kosi 50..69 so brez zaostanka in nove vrstice v dnevniku ne dajo.
    kosi = [b"\x01" * KOS] * 70
    casi = [1000.0 + 10 * k for k in range(30)] + [1400.0 + 10 * k for k in range(40)]
    _crpaj(kosi, OKVIR_ZVOK, casi)
    assert capsys.readouterr().err.count("dogodek=zvok_poravnava") == 1


# ------------------------------------------------------------------ slika

def _nal(vrsta, prvi_mb0=True, dolzina=20, stiri=True):
    koda = b"\x00\x00\x00\x01" if stiri else b"\x00\x00\x01"
    telo = bytes([0x80 if prvi_mb0 else 0x40]) + b"\x11" * dolzina
    return koda + bytes([0x60 | vrsta]) + telo


def _slika(idr=False, rezin=1):
    deli = [_nal(9)]
    if idr:
        deli += [_nal(7), _nal(8), _nal(5)]
    else:
        deli += [_nal(1)]
    deli += [_nal(5 if idr else 1, prvi_mb0=False, stiri=False) for _ in range(rezin - 1)]
    return b"".join(deli)


def test_slika_meje_z_vec_rezinami_in_brez_aud():
    s = ZigiSlike(10.0)
    brez_aud = _nal(7) + _nal(8) + _nal(5) + _nal(5, prvi_mb0=False) + _nal(1) + _nal(1, prvi_mb0=False)
    assert s.zacetki(brez_aud) == [0, 4 * 26]


def test_slika_zig_samo_za_cist_kos():
    s = ZigiSlike(13.5)
    assert s.zig(_slika(idr=True, rezin=3), 1000.0) == 986.5
    dve = _slika() + _slika()
    assert s.zig(dve, 1010.0) is None                    # zaostanek: dve sliki v kosu
    velika = _slika(rezin=4)
    assert s.zig(velika[:40], 1020.0) == 1006.5
    assert s.zig(velika[40:], 1021.0) is None            # nadaljevanje iste slike


def test_slika_zacetna_koda_razdeljena_med_kosa():
    s = ZigiSlike(5.0)
    prva, druga = _slika(), _slika()
    assert s.zig(prva, 100.0) == 95.0
    tok = druga
    for rez in range(1, 6):
        s2 = ZigiSlike(5.0)
        s2.zig(prva + tok[:rez], 100.0)
        zac = s2.zacetki(tok[rez:])
        assert zac == [-rez], rez


def test_slika_brez_izmerjene_zakasnitve_brez_ziga():
    assert ZigiSlike(None).zig(_slika(idr=True), 1000.0) is None


def test_zakasnitev_slike_samo_x264_1080p_brez_prevzorcenja():
    assert lz.zakasnitev_slike(None, 1920, 1080, (1920, 1080)) == 13.5
    assert lz.zakasnitev_slike(None, 1280, 720, (1280, 720)) is None        # druga velikost
    assert lz.zakasnitev_slike(None, 1920, 1080, (2560, 1440)) is None      # prevzorcenje
    assert lz.zakasnitev_slike(None, 1280, 720, (1920, 1080)) is None       # kakovost nizka
    assert lz.zakasnitev_slike("/dev/dri/renderD128", 1920, 1080, (1920, 1080)) is None


def _zacni_z_izvorom(monkeypatch, izvor):
    """zacni() brez omrezja, zaslona, ffmpeg in KMS; vrne (Zaslon, args niti _streci)."""
    niti = []

    class _Nit:
        def __init__(self, *a, **k):
            niti.append(k.get("args"))

        def start(self):
            pass

    class _Ctx:
        minimum_version = None

        def __init__(self, *a):
            pass

        def load_cert_chain(self, potrdilo, kljuc):
            pass

    class _Posluh:
        def __init__(self, *a):
            pass

        def setsockopt(self, *a):
            pass

        def bind(self, naslov):
            pass

        def listen(self, n):
            pass

        def settimeout(self, t):
            pass

        def getsockname(self):
            return ("0.0.0.0", 40000)

    class _Plosek(_Prazen):
        def mozno(self):
            return False

    vticnice = types.SimpleNamespace(socket=_Posluh, AF_INET=2, SOCK_STREAM=1, SOL_SOCKET=1,
                                     SO_REUSEADDR=2, SHUT_RDWR=2)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(lz, "_zaslon_geometrija", lambda d: izvor)
    monkeypatch.setattr(lz, "_deljeni_monitor", lambda: None)
    monkeypatch.setattr(lz, "vaapi_naprava", lambda *a, **k: None)
    monkeypatch.setattr(lz, "kms_na_voljo", lambda: False)          # poti KMS v zacni ni
    monkeypatch.setattr(lz, "privzeti_monitor", lambda: None)
    monkeypatch.setattr(lz, "zagotovi_potrdilo", lambda mapa: ("kljuc", "potrdilo", "odtis"))
    monkeypatch.setattr(lz, "Vnos", _Prazen)
    monkeypatch.setattr(lz, "socket", vticnice)
    monkeypatch.setattr(lz.ssl, "SSLContext", _Ctx)
    monkeypatch.setattr(lz.threading, "Thread", _Nit)
    z = Zaslon(ffmpeg="ffmpeg", vklopljeno=True)
    z._vnos = _Prazen()
    z._plosek = _Plosek()
    z._zakasnitev_slike = -1.0                  # zacni mora vrednost nastaviti sam
    z.zacni("tv", "najvisja", "desktop")
    return z, niti


def test_zacni_brez_ziga_slike_pri_prevzorcenju(monkeypatch):
    z, niti = _zacni_z_izvorom(monkeypatch, (2560, 1440))
    assert z._slika == {"width": 1920, "height": 1080, "fps": 60} and z._izvor == (2560, 1440)
    assert z._zakasnitev_slike is None          # stari klic v zacni bi dal 13.5
    assert len(niti) == 1 and niti[0][5] is None                 # kms = None


def test_zacni_zig_slike_pri_izmerjeni_velikosti(monkeypatch):
    z, niti = _zacni_z_izvorom(monkeypatch, (1920, 1080))
    assert z._slika == {"width": 1920, "height": 1080, "fps": 60}
    assert z._zakasnitev_slike == 13.5
    assert len(niti) == 1 and niti[0][5] is None


# ------------------------------------------------------------------ zamenjava procesa slike

class _Cev:
    def __init__(self, kosi):
        self.kosi = list(kosi)

    def read(self, n):
        return self.kosi.pop(0) if self.kosi else b""

    def close(self):
        pass


class _NamisljenFfmpeg:
    """Kot Popen: wait() vrze TimeoutExpired, dokler v cevi se kaj je (proces tece)."""

    def __init__(self, kosi):
        self.stdout = _Cev(kosi)
        self.returncode = None

    def wait(self, timeout=None):
        if self.stdout.kosi:
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        self.returncode = 0
        return 0

    def terminate(self):
        pass

    kill = terminate

    def poll(self):
        return self.returncode


def _proces_slike(stari, novi):
    procesi = iter([_NamisljenFfmpeg(stari), _NamisljenFfmpeg(novi)])
    return lz._ProcesSlike(lambda: next(procesi))


def test_svez_ostanek_starega_toka_in_prvi_kos_novega():
    ostanek = _nal(1, stiri=False)              # nova slika s 3-bajtno kodo (P2)
    ps = _proces_slike([_slika(idr=True), ostanek], [_slika(), _slika()])
    assert ps.read(32 * 1024) == _slika(idr=True) and ps.svez is True
    assert ps.znova() is True
    # Stari tok: kos brez druge zacetne kode gre ves v ostanek in ven sele ob EOF (P2).
    assert ps.read(32 * 1024) == ostanek and ps.svez is False
    # Prvi kos novega procesa je cakal v cevi med praznjenjem starega (P1).
    assert ps.read(32 * 1024) == _slika() and ps.svez is False
    assert ps.read(32 * 1024) == _slika() and ps.svez is True
    assert ps.read(32 * 1024) == b""


def test_svez_konec_starega_toka():
    ps = _proces_slike([_slika(idr=True), _slika() + _nal(1, stiri=False)], [_slika()])
    assert ps.read(32 * 1024) == _slika(idr=True) and ps.svez is True
    assert ps.znova() is True
    # Do zadnje zacetne kode: zacetek je sicer sveze prebran, a je konec starega toka.
    assert ps.read(32 * 1024) == _slika() and ps.svez is False


def test_po_zamenjavi_brez_ziga_slike_za_stari_tok_in_prvi_kos_novega():
    ps = _proces_slike([_slika(idr=True)], [_slika(idr=True), _slika()])
    assert ps.znova() is True
    z = Zaslon()
    z._zakasnitev_slike = 13.5
    v = _Vticnica()
    # stari kos (do rezine IDR), ostanek starega ob EOF, prvi kos novega (cakal v cevi), nova P
    casi = iter([100.0, 200.0, 400.0, 416.0])
    stara = lz.ura_ms
    lz.ura_ms = lambda: next(casi)
    try:
        z._crpaj(ps, OKVIR_SLIKA, v, 32 * 1024, fps=None)
    finally:
        lz.ura_ms = stara
    tok = b"".join(v.klici)
    # Vsi bajti obeh tokov gredo naprej nespremenjeni (okvir 1 in "bajt").
    assert b"".join(k for t, k in _stari_bralnik(tok)) == _slika(idr=True) * 2 + _slika()
    # Brez popravka: [86, 386, 402] (386 = 400 - 13,5 bi bil za cas v cevi prepozen).
    zigi = _zigi(tok)
    assert [x["zig_ms"] for x in zigi] == [402]
    assert [x["bajt"] for x in zigi] == [2 * len(_slika(idr=True))]


# ------------------------------------------------------------------ pisanje

def test_okvir_4_v_istem_sendall_pred_okvirjem():
    kosi = [b"\x01" * KOS, b"\x02" * KOS]
    kosi = [b"\x00" * KOS] + kosi
    klici = _crpaj(kosi, OKVIR_ZVOK, [990.0, 1000.0, 1010.0])
    assert len(klici) == 3
    assert klici[0] == bytes([OKVIR_ZVOK]) + KOS.to_bytes(4, "big") + kosi[0]   # prvi kos brez ziga
    for k, klic in enumerate(klici[1:], 1):
        assert klic[0] == OKVIR_ZIG
        n = int.from_bytes(klic[1:5], "big")
        zig = json.loads(klic[5:5 + n])
        assert zig == {"vrsta": OKVIR_ZVOK, "zig_ms": 980 + 10 * k, "bajt": KOS * k}
        assert klic[5 + n] == OKVIR_ZVOK and klic[5 + n + 5:] == kosi[k]


def test_stari_bralnik_dobi_enake_bajte():
    kosi = [_slika(idr=True), _slika(), _slika() + _slika(), _slika()]
    z_zigi = b"".join(_crpaj(kosi, OKVIR_SLIKA, [100.0, 116.0, 140.0, 150.0], zakasnitev=13.5))
    brez = b"".join(_crpaj(kosi, OKVIR_SLIKA, [100.0, 116.0, 140.0, 150.0], zakasnitev=None))
    assert _stari_bralnik(z_zigi) == _stari_bralnik(brez) == [(OKVIR_SLIKA, k) for k in kosi]
    zigi = _zigi(z_zigi)
    # Kos z dvema slikama (zaostanek) nima ziga.
    assert [z["zig_ms"] for z in zigi] == [86, 102, 136]
    assert [z["bajt"] for z in zigi] == [0, len(kosi[0]), sum(map(len, kosi[:3]))]


def test_brez_ziga_ni_okvirja_4():
    kosi = [_slika(idr=True)]
    klici = _crpaj(kosi, OKVIR_SLIKA, [100.0], zakasnitev=None)
    assert klici == [bytes([OKVIR_SLIKA]) + len(kosi[0]).to_bytes(4, "big") + kosi[0]]
    assert _okvir_z_zigom(OKVIR_ZVOK, None, 0, b"ab") == b"\x02\x00\x00\x00\x02ab"


class _VirBrezSvez:
    """Vir slike, ki svezosti kosa ne pove (nima atributa svez)."""

    def __init__(self, kosi):
        self._kosi = list(kosi)
        self.stdout = self

    def read(self, n):
        return self._kosi.pop(0) if self._kosi else b""


def test_vir_slike_brez_podatka_o_svezosti_brez_ziga():
    kos = _slika(idr=True)
    z = Zaslon()
    z._zakasnitev_slike = 13.5
    v = _Vticnica()
    stara = lz.ura_ms
    lz.ura_ms = lambda: 100.0
    try:
        z._crpaj(_VirBrezSvez([kos]), OKVIR_SLIKA, v, 32 * 1024)
    finally:
        lz.ura_ms = stara
    tok = b"".join(v.klici)
    assert _stari_bralnik(tok) == [(OKVIR_SLIKA, kos)]
    assert _zigi(tok) == []                     # brez popravka: [{"vrsta": 1, "zig_ms": 86, "bajt": 0}]


def test_glava_ima_kljuc_zig(monkeypatch):
    z = Zaslon()
    z._zeton = "zeton"
    z._slika = {"width": 1920, "height": 1080, "fps": 60}

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

    def _brez_procesa(*a, **k):
        raise OSError("v preizkusu ni ffmpeg")

    monkeypatch.setattr(lz, "_ProcesSlike", _brez_procesa)
    posluh = _Posluh()
    z._seja_st, z._posluh = 1, posluh
    z._naprava, z.dostop = "tv", lambda naprava: True      # straza dostopa (najnovejsa veja): seja mora imeti napravo z dostopom
    z._sprejmi = lambda p, c, seja=None: (v, None)         # mainov _streci sprejme povezavo prek _sprejmi
    z._streci(posluh, _Ctx(), ["nic"], 1)
    glava = json.loads(v.klici[0].decode("utf-8"))
    assert glava["zig"] == ZIG_GLAVA == {"okvir": 4, "ura": "monotonic_ms"}

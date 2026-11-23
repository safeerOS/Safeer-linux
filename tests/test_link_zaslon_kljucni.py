"""Preizkus omejitve kljucnih okvirjev (IDR na zahtevo) in zamenjave procesa slike.

Brez omrezja, brez ffmpeg in brez zaslona: cisto pravilo in proces slike z namisljenimi procesi.
"""

import importlib.util
import io
import math
import os
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

from core.link_zaslon import (KLJUCNI_NAJVEC, KLJUCNI_OKNO_S, OmejevalnikKljucnih,  # noqa: E402
                                    _ProcesSlike, presodi_kljucni)


def _zaporedje(casi):
    sprejeti, izidi = (), []
    for t in casi:
        ok, sprejeti = presodi_kljucni(sprejeti, t)
        izidi.append(ok)
    return izidi


def test_privzeto_en_v_dveh_sekundah():
    assert (KLJUCNI_OKNO_S, KLJUCNI_NAJVEC) == (2.0, 1)


def test_prva_zahteva_gre_skozi():
    assert presodi_kljucni((), 100.0) == (True, (100.0,))


def test_poplava_100_na_sekundo_eno_sekundo():
    izidi = _zaporedje([100.0 + i / 100 for i in range(100)])
    assert izidi.count(True) == 1 and izidi[0] is True


def test_poplava_100_na_sekundo_deset_sekund():
    izidi = _zaporedje([i / 100 for i in range(1000)])
    # sprejete pri 0, 2, 4, 6, 8 s
    assert izidi.count(True) == 5
    assert [i for i, ok in enumerate(izidi) if ok] == [0, 200, 400, 600, 800]


def test_meja_okna_drsece():
    assert _zaporedje([0.0, 1.999, 2.0, 3.0, 4.0]) == [True, False, True, False, True]


def test_zavrnjena_ne_podaljsa_okna():
    # zavrnitve pri 1,5 in 1,9 ne smejo premakniti naslednje dovoljene zahteve za 2,0
    assert _zaporedje([0.0, 1.5, 1.9, 2.0]) == [True, False, False, True]


def test_cas_nazaj_se_steje_kot_zadnji_sprejeti():
    ok, sprejeti = presodi_kljucni((), 10.0)
    assert ok
    ok, sprejeti = presodi_kljucni(sprejeti, 3.0)
    assert not ok and sprejeti == (10.0,)
    ok, _ = presodi_kljucni(sprejeti, 12.0)
    assert ok


def test_neveljaven_cas_zavrnjen_in_ne_pokvari_okna():
    for slab in (math.nan, math.inf, -math.inf, None, "1"):
        ok, sprejeti = presodi_kljucni((), slab)
        assert not ok and sprejeti == ()
    _, sprejeti = presodi_kljucni((), 5.0)
    ok, sprejeti = presodi_kljucni(sprejeti, math.nan)
    assert not ok and sprejeti == (5.0,)
    assert presodi_kljucni(sprejeti, 6.0)[0] is False


def test_vec_v_oknu_ce_najvec_vecji():
    sprejeti, izidi = (), []
    for t in (0.0, 0.1, 0.2, 0.3):
        ok, sprejeti = presodi_kljucni(sprejeti, t, okno_s=1.0, najvec=3)
        izidi.append(ok)
    assert izidi == [True, True, True, False]


def test_omejevalnik_stevca_za_dnevnik():
    cas = [0.0]
    o = OmejevalnikKljucnih(ura=lambda: cas[0])
    for i in range(100):
        cas[0] = i / 100
        o.dovoli()
    assert (o.sprejetih, o.zavrnjenih) == (1, 99)
    cas[0] = 2.5
    assert o.dovoli() is True
    assert (o.sprejetih, o.zavrnjenih) == (2, 99)


class _NamisljenProces:
    """Kot subprocess.Popen: stdout z read, poll, terminate, wait, kill."""

    def __init__(self, podatki):
        self.stdout = io.BytesIO(podatki)
        self.koncan = None

    def poll(self):
        return self.koncan

    def terminate(self):
        self.koncan = -15

    def kill(self):
        self.koncan = -9

    def wait(self, timeout=None):
        # Kot pravi Popen: zivi proces ob izteku roka vrze TimeoutExpired.
        if self.koncan is None and timeout is not None:
            raise subprocess.TimeoutExpired("namisljen", timeout)
        return self.koncan

    @property
    def returncode(self):
        return self.koncan


class _TakojMrtev(_NamisljenProces):
    """Nov ffmpeg, ki takoj pade (zaseden zajem/kodirnik)."""

    def __init__(self):
        super().__init__(b"")
        self.koncan = 1


def test_nov_proces_ki_takoj_pade_ne_konca_seje():
    stari = _NamisljenProces(b"STARI")
    zagoni = iter([stari, _TakojMrtev()])
    slika = _ProcesSlike(lambda: next(zagoni))
    assert slika.znova() is False
    assert slika.poll() is None  # stari proces tece naprej
    assert _preberi_vse(slika) == b"STARI"


def _preberi_vse(slika):
    zbrano = b""
    while True:
        kos = slika.stdout.read(4)
        if not kos:
            return zbrano
        zbrano += kos


def test_zamenjava_ohrani_isti_objekt_in_vrstni_red():
    procesi = [_NamisljenProces(b"STARI-PRETOK"), _NamisljenProces(b"NOV-IDR")]
    zagoni = iter(procesi)
    slika = _ProcesSlike(lambda: next(zagoni))
    istovetnost = slika
    assert slika.znova() is True
    assert slika is istovetnost and slika.poll() is None
    # najprej ves stari pretok, nato nov, brez prepletanja
    assert _preberi_vse(slika) == b"STARI-PRETOKNOV-IDR"
    assert slika.zamenjav == 1


def test_brez_zamenjave_konec_pretoka_konca_branje():
    slika = _ProcesSlike(lambda: _NamisljenProces(b"ABC"))
    assert _preberi_vse(slika) == b"ABC"


def test_po_ustavitvi_ni_zamenjave():
    slika = _ProcesSlike(lambda: _NamisljenProces(b""))
    slika.terminate()
    assert slika.znova() is False
    assert slika.poll() == -15


def test_neuspel_zagon_obdrzi_stari_proces():
    stari = _NamisljenProces(b"X")
    zagoni = iter([stari])

    def zazeni():
        try:
            return next(zagoni)
        except StopIteration:
            raise OSError("ffmpeg ni")

    slika = _ProcesSlike(zazeni)
    assert slika.znova() is False
    assert _preberi_vse(slika) == b"X"

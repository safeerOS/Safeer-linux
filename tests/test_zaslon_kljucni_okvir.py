"""Preizkus pytest za tools/zaslon_kljucni_okvir.py (stran racunalnika, KLJUC1-4)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import zaslon_kljucni_okvir as zko  # noqa: E402

E = zko.Razlog.NAPAKA_DEKODIRNIKA
IZ = zko.Razlog.IZGUBA_PAKETA
R = zko.Razlog.ROCNO


def odl(poslji, cakaj_ms):
    return zko.Odlocitev(poslji=poslji, cakaj_ms=cakaj_ms)


# --- Presojevalec: ista pravila kot Kotlin ---


def test_konstante_enake_kotlinu():
    assert zko.NAJMANJ_RAZMIK_MS == 500
    assert zko.NAJVEC_RAZMIK_MS == 4000
    assert zko.ZACETNI_RAZMIK_MS == 500
    assert zko.TISINA_PO_USPEHU_MS == 2000
    assert zko.MIROVANJE_ZA_PONASTAVITEV_MS == 8000
    assert zko.OKNO_MS == 2000
    assert zko.OKNO_NAJVEC_IDR == 1


def test_eksponentni_zamik_500_1000_2000_4000_4000():
    p = zko.Presojevalec()
    assert p.presodi(E, 0) == odl(True, 0)
    assert p.presodi(E, 100) == odl(False, 400)
    assert p.presodi(E, 500) == odl(True, 0)
    assert p.presodi(E, 1000) == odl(False, 500)
    assert p.presodi(E, 1500) == odl(True, 0)
    assert p.presodi(E, 2500) == odl(False, 1000)
    assert p.presodi(E, 3500) == odl(True, 0)
    assert p.presodi(E, 7499) == odl(False, 1)
    assert p.presodi(E, 7500) == odl(True, 0)
    assert p.presodi(E, 11500) == odl(True, 0)
    assert p.presodi(E, 11600) == odl(False, 3900)
    assert p.zaporednih_neuspelih == 6


def test_uspeh_tisina_in_meje():
    p = zko.Presojevalec()
    p.uspeh(0)
    assert p.zaporednih_neuspelih == 0
    assert p.presodi(E, 1999) == odl(False, 1)
    assert p.presodi(E, 2000) == odl(True, 0)


def test_tisina_prevlada_nad_razmikom():
    p = zko.Presojevalec()
    assert p.presodi(E, 0) == odl(True, 0)
    p.uspeh(100)
    assert p.presodi(E, 200) == odl(False, 1900)
    assert p.presodi(E, 2099) == odl(False, 1)
    assert p.presodi(E, 2100) == odl(True, 0)
    assert p.presodi(R, 2130) == odl(False, 70)


def test_rocno_100_ms_in_steje_v_stevec():
    p = zko.Presojevalec()
    p.uspeh(1000)
    assert p.presodi(R, 1050) == odl(True, 0)
    assert p.presodi(R, 1149) == odl(False, 1)
    assert p.presodi(R, 1150) == odl(True, 0)
    assert p.zaporednih_neuspelih == 2
    # Dve ROCNO zahtevi podvojita razmik na 1000: pri 1200 prevlada tisina (1800).
    assert p.presodi(E, 1200) == odl(False, 1800)


def test_cas_nazaj_je_zadnji_znani_cas():
    p = zko.Presojevalec()
    assert p.presodi(E, 2000) == odl(True, 0)
    assert p.presodi(E, 2200) == odl(False, 300)
    assert p.presodi(E, 1800) == odl(False, 300)
    assert p.presodi(E, -100) == odl(False, 300)
    assert p.presodi(E, 2500) == odl(True, 0)
    assert p.presodi(R, 2000) == odl(False, 100)


def test_mirovanje_8000_ne_8001_da():
    p = zko.Presojevalec()
    for t in (0, 500, 1500, 3500, 7500):
        assert p.presodi(E, t) == odl(True, 0)
    assert p.presodi(E, 15500) == odl(True, 0)
    assert p.zaporednih_neuspelih == 6
    assert p.presodi(E, 15600) == odl(False, 3900)
    assert p.presodi(IZ, 23501) == odl(True, 0)
    assert p.zaporednih_neuspelih == 1
    assert p.presodi(E, 23601) == odl(False, 400)


def test_skrajni_casi_brez_preliva():
    p = zko.Presojevalec()
    assert p.presodi(E, zko.LONG_MIN) == odl(True, 0)
    assert p.presodi(E, zko.LONG_MAX) == odl(True, 0)
    assert p.presodi(E, zko.LONG_MAX) == odl(False, 500)
    assert p.presodi(E, zko.LONG_MIN) == odl(False, 500)
    p2 = zko.Presojevalec()
    p2.uspeh(zko.LONG_MAX - 10)
    assert p2.presodi(E, zko.LONG_MAX - 5) == odl(False, 1995)


def test_stevec_zadrzani_klici_ne_stejejo():
    p = zko.Presojevalec()
    assert p.presodi(E, 0) == odl(True, 0)
    for i in range(1, 51):
        assert p.presodi(IZ, 100 + i) == odl(False, 400 - i)
    assert p.zaporednih_neuspelih == 1
    p.ponastavi()
    assert p.zaporednih_neuspelih == 0


def test_napacni_vhodi():
    p = zko.Presojevalec()
    with pytest.raises(TypeError):
        p.presodi(E, 1.5)
    with pytest.raises(TypeError):
        p.presodi(E, True)
    with pytest.raises(TypeError):
        p.presodi("ROCNO", 0)
    with pytest.raises(ValueError):
        p.presodi(E, 2 ** 63)
    with pytest.raises(ValueError):
        zko.DrseceOkno(najvec=0)
    with pytest.raises(ValueError):
        zko.DrseceOkno(okno_ms=0)


# --- Drsece okno in zascita kodirnika (1 IDR v 2 s) ---


def test_okno_meja_1999_2000():
    o = zko.DrseceOkno()
    assert o.poskusi(0) == odl(True, 0)
    assert o.poskusi(1999) == odl(False, 1)
    assert o.poskusi(2000) == odl(True, 0)


def test_okno_preveri_ne_zapise():
    o = zko.DrseceOkno()
    assert o.preveri(0) == odl(True, 0)
    assert o.preveri(10) == odl(True, 0)
    assert o.poskusi(20) == odl(True, 0)
    assert o.preveri(30) == odl(False, 1990)


def test_okno_vec_dogodkov():
    o = zko.DrseceOkno(najvec=3, okno_ms=1000)
    assert o.poskusi(0) == odl(True, 0)
    assert o.poskusi(100) == odl(True, 0)
    assert o.poskusi(200) == odl(True, 0)
    assert o.poskusi(300) == odl(False, 700)
    assert o.poskusi(1000) == odl(True, 0)
    assert o.poskusi(1050) == odl(False, 50)


def test_okno_cas_nazaj_in_skrajni_casi():
    o = zko.DrseceOkno()
    assert o.poskusi(5000) == odl(True, 0)
    assert o.poskusi(1000) == odl(False, 2000)
    assert o.poskusi(7000) == odl(True, 0)
    o2 = zko.DrseceOkno()
    assert o2.poskusi(zko.LONG_MIN) == odl(True, 0)
    assert o2.poskusi(zko.LONG_MAX) == odl(True, 0)


def test_okno_omejen_pomnilnik():
    o = zko.DrseceOkno()
    dovoljeni = 0
    for t in range(10000):
        if o.poskusi(t).poslji:
            dovoljeni += 1
    assert dovoljeni == 5
    assert len(o._casi) <= 1


def test_zascita_poplava_rocno_100_v_1_s_da_en_idr():
    z = zko.ZascitaKodirnika()
    poslanih = 0
    for i in range(100):
        if z.zahteva(R, i * 10).poslji:
            poslanih += 1
    assert poslanih == 1
    assert z.zahteva(R, 1999) == odl(False, 1)
    assert z.zahteva(R, 2000) == odl(True, 0)


def test_zascita_zavrnjena_zahteva_ne_spremeni_presojevalca():
    z = zko.ZascitaKodirnika()
    assert z.zahteva(E, 0) == odl(True, 0)
    assert z.zahteva(E, 500) == odl(False, 1500)
    assert z.presojevalec.zaporednih_neuspelih == 1
    assert z.zahteva(E, 2000) == odl(True, 0)
    assert z.presojevalec.zaporednih_neuspelih == 2


def test_zascita_tisina_po_uspehu_velja_tudi_ko_okno_dovoli():
    z = zko.ZascitaKodirnika()
    z.uspeh(0)
    assert z.zahteva(E, 1000) == odl(False, 1000)
    assert z.zahteva(E, 2000) == odl(True, 0)


def test_zascita_ponastavi():
    z = zko.ZascitaKodirnika()
    assert z.zahteva(E, 0) == odl(True, 0)
    z.ponastavi()
    assert z.presojevalec.zaporednih_neuspelih == 0
    assert z.zahteva(E, 10) == odl(True, 0)

"""Preizkusi samo za cisti del tools/zaslon_zakasnitev_zvoka.py (brez pactl, ffmpeg, paplay)."""
import importlib.util
import math
import os
import random
import tempfile
import wave
from pathlib import Path

import pytest

_POT = Path(__file__).resolve().parent.parent / "tools" / "zaslon_zakasnitev_zvoka.py"
_spec = importlib.util.spec_from_file_location("zaslon_zakasnitev_zvoka", _POT)
z = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(z)

HZ, KAN = 48000, 2
BPMS = z.bajtov_na_ms(HZ, KAN)


def _razrezi(podatki, dolzine):
    kosi, i = [], 0
    for d in dolzine:
        kosi.append(podatki[i:i + d])
        i += d
    kosi.append(podatki[i:])
    return kosi


def test_bajtov_na_ms_192():
    assert BPMS == 192.0
    assert z.indeks_v_ms(1920, BPMS) == 10.0
    assert z.bajtov_na_ms(48000, 1) == 96.0


def test_okvir_impulza():
    assert z.okvir_impulza(2) == b"\xff\x7f\xff\x7f"


def test_ustvari_pcm_polozaji_in_dolzina():
    pcm = z.ustvari_pcm(HZ, KAN, 3, 1000, 500, 100)
    okv = 4
    assert len(pcm) % okv == 0
    polozaji = [i for i in range(0, len(pcm), okv) if pcm[i:i + okv] != b"\0" * okv]
    assert polozaji == [24000 * okv, 72000 * okv, 120000 * okv]
    assert len(pcm) == (24000 + 2 * 48000 + 1 + 4800) * okv


def test_ustvari_pcm_neveljavno():
    with pytest.raises(ValueError):
        z.ustvari_pcm(HZ, KAN, 0, 1000, 0, 0)


def test_pisi_wav():
    pcm = z.ustvari_pcm(HZ, KAN, 2, 300, 10, 10)
    fd, pot = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        z.pisi_wav(pot, pcm, HZ, KAN)
        with wave.open(pot, "rb") as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, 48000)
            assert w.readframes(w.getnframes()) == pcm
    finally:
        os.unlink(pot)


def test_iskalnik_cel_tok():
    pcm = z.ustvari_pcm(HZ, KAN, 3, 1000, 500, 100)
    isk = z.IskalnikImpulza(KAN)
    assert isk.dodaj(pcm) == [96000, 288000, 480000]


@pytest.mark.parametrize("seme", range(5))
def test_iskalnik_nakljucni_kosi_in_meja_kosa(seme):
    pcm = z.ustvari_pcm(HZ, KAN, 4, 250, 20, 20)
    rnd = random.Random(seme)
    kosi, i = [], 0
    while i < len(pcm):
        d = rnd.randint(1, 3000)
        kosi.append(pcm[i:i + d])
        i += d
    isk = z.IskalnikImpulza(KAN)
    najdeni = [x for k in kosi for x in isk.dodaj(k)]
    assert najdeni == z.IskalnikImpulza(KAN).dodaj(pcm)
    assert isk.prebranih_bajtov == len(pcm)


def test_impulz_razdeljen_cez_mejo_po_bajtu():
    # impulz na bajtih 4..7; meje kosov padejo na 5, 6, 7 (sredi vzorca in med kanaloma)
    tok = b"\0" * 4 + z.okvir_impulza(2) + b"\0" * 8
    for meja in range(1, len(tok)):
        isk = z.IskalnikImpulza(KAN)
        assert isk.dodaj(tok[:meja]) + isk.dodaj(tok[meja:]) == [4], meja


def test_poravnava_ni_napacna_kombinacija_bajtov():
    # bajta 0xFF 0x7F na lihem odmiku (sestavljena iz dveh vzorcev) NISTA impulz
    tok = bytes([0x00, 0xFF, 0x7F, 0x00]) + b"\0" * 4
    assert z.IskalnikImpulza(KAN, prag=0x7FFF).dodaj(tok) == []


def test_impulz_samo_v_desnem_kanalu_in_negativen():
    tok = b"\0\0" + (0x5000).to_bytes(2, "little") + b"\0\0" + (-0x5000).to_bytes(2, "little", signed=True)
    assert z.IskalnikImpulza(KAN).dodaj(tok) == [0, 4]


def test_prag_pod_pragom_ni_zaznave():
    tok = (0x3FFF).to_bytes(2, "little") * 2
    assert z.IskalnikImpulza(KAN, prag=0x4000).dodaj(tok) == []


def test_mrtvi_cas_cez_meje_kosov():
    imp = z.okvir_impulza(2)
    tok = imp + imp + b"\0" * 4 * 3 + imp
    isk = z.IskalnikImpulza(KAN, mrtvih_okvirjev=3)
    rez = []
    for kos in _razrezi(tok, [3, 5, 2, 7]):
        rez += isk.dodaj(kos)
    assert rez == [0, 20]


def test_iskalnik_neveljavno():
    with pytest.raises(ValueError):
        z.IskalnikImpulza(0)
    with pytest.raises(ValueError):
        z.IskalnikImpulza(2, prag=0)


def test_cas_bajta():
    # kos 1920 B (10 ms) prejet ob 1000 ms; bajt na zacetku kosa je bil na voljo 10 ms prej
    assert z.cas_bajta_ms(0, 1000.0, 1920, BPMS) == 990.0
    assert z.cas_bajta_ms(1920, 1000.0, 1920, BPMS) == 1000.0


def test_zaznave_iz_kosov_simulacija_zakasnitve():
    # tok: impulzi vsakih 1000 ms, uvod 500 ms; zajem zamuja 37 ms; kosi po 1920 B
    zac = 10000.0
    pcm = z.ustvari_pcm(HZ, KAN, 5, 1000, 500, 100)
    kosi = []
    for i in range(0, len(pcm), 1920):
        kos = pcm[i:i + 1920]
        konec_ms = (i + len(kos)) / BPMS
        kosi.append((zac + 37.0 + konec_ms, kos))
    zaznani = z.zaznave_iz_kosov(kosi, z.IskalnikImpulza(KAN), BPMS)
    zak = z.zdruzi(z.pricakovani_casi(zac, 500, 1000, 5), zaznani, 900)
    assert len(zak) == 5
    assert all(math.isclose(x, 37.0, abs_tol=1e-6) for x in zak)


def test_zdruzi_izgubljen_impulz_in_motnja():
    pric = [0.0, 1000.0, 2000.0]
    zaz = [-5.0, 40.0, 2045.0, 2100.0]  # motnja pred prvim, drugi izgubljen, dvojna zaznava tretjega
    assert z.zdruzi(pric, zaz, 900) == [40.0, 45.0]


def test_zdruzi_ne_pripise_sosednjemu():
    # zaznava 950 ms po prvem je izven okna 900 ms in pred drugim -> ni pripisana nobenemu
    assert z.zdruzi([0.0, 1000.0], [950.0], 900) == []


def test_percentil():
    v = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert z.percentil(v, 50) == 3.0
    assert z.percentil(v, 0) == 1.0 and z.percentil(v, 100) == 5.0
    assert math.isclose(z.percentil(v, 5), 1.2)
    assert math.isclose(z.percentil(v, 95), 4.8)
    assert z.percentil([7.0], 95) == 7.0
    assert math.isnan(z.percentil([], 50))
    with pytest.raises(ValueError):
        z.percentil(v, 101)


def test_vrstica_izpisa():
    assert z.vrstica_izpisa([10.0, 20.0, 30.0]) == \
        "ZAKASNITEV_ZVOKA_MS mediana=20.0 p5=11.0 p95=29.0 max=30.0 n=3"
    assert z.vrstica_izpisa([]) == "ZAKASNITEV_ZVOKA_MS mediana=nan p5=nan p95=nan max=nan n=0"


def test_zdruzi_okna_osnovno():
    t = [0.0, 1000.0, 2000.0]
    zaz = [-3.0, 45.0, 60.0, 1040.0, 2900.0, 3100.0]
    # -3 pred prvim (izpusceno), 60 je druga zaznava v oknu 0 (izpusceno),
    # 2900 je v zadnjem oknu [2000, 3000), 3100 izven
    assert z.zdruzi_okna(t, zaz, 1000) == [45.0, 40.0, 900.0]


def test_zdruzi_okna_izgubljen_impulz_ne_premakne_ostalih():
    t = [0.0, 1000.0, 2000.0]
    zaz = [50.0, 2050.0]  # drugi impulz izgubljen
    assert z.zdruzi_okna(t, zaz, 1000) == [50.0, 50.0]


def test_zdruzi_okna_neenakomerni_zagoni():
    # naslednji zagon je zamujal (predvajalnik je koncal pozneje): okno sega do naslednjega t
    t = [0.0, 1300.0]
    zaz = [1250.0, 1350.0]
    assert z.zdruzi_okna(t, zaz, 1000) == [1250.0, 50.0]


def test_zdruzi_okna_prazno():
    assert z.zdruzi_okna([], [1.0], 1000) == []
    assert z.zdruzi_okna([0.0], [], 1000) == []


def test_locen_nacin_wav_impulz_na_poziciji_0():
    pcm = z.ustvari_pcm(HZ, KAN, 1, 1000, 0, 100)
    assert pcm[:4] == z.okvir_impulza(2)
    assert len(pcm) == (1 + 4800) * 4
    assert z.IskalnikImpulza(KAN).dodaj(pcm) == [0]


def test_simulacija_locen_nacin():
    # zajem: tisina s kosi po 1920 B; impulz k se pojavi v toku 23 ms + k ms po t_k
    zac_toka = 5000.0
    trajanje_ms = 4000
    tok = bytearray(int(trajanje_ms * BPMS))
    t = [5100.0, 6100.0, 7100.0]
    pricakovano = []
    for k, tk in enumerate(t):
        zak = 23.0 + k
        idx = int((tk + zak - zac_toka) * BPMS) // 4 * 4
        tok[idx:idx + 4] = z.okvir_impulza(2)
        pricakovano.append(zac_toka + idx / BPMS - tk)
    kosi = []
    for i in range(0, len(tok), 1920):
        kos = bytes(tok[i:i + 1920])
        kosi.append((zac_toka + (i + len(kos)) / BPMS, kos))
    zaznani = z.zaznave_iz_kosov(kosi, z.IskalnikImpulza(KAN), BPMS)
    rez = z.zdruzi_okna(t, zaznani, 1000)
    assert len(rez) == 3
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(rez, pricakovano))
    assert all(math.isclose(a, 23.0 + k, abs_tol=0.01) for k, a in enumerate(rez))

"""Preizkus CISTEGA dela tools/zaslon_primerjava_zajema.py: statistika, /proc/PID/stat, meje slik.

Brez ffmpeg, zaslona, pomocnika in /proc: samo lazni podatki.
Pozeni iz korena projekta: python3 -m pytest -q tests/test_zaslon_primerjava_zajema.py
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
from pathlib import Path

import pytest

KOREN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOREN))
_spec = importlib.util.spec_from_file_location("zaslon_primerjava_zajema",
                                               KOREN / "tools" / "zaslon_primerjava_zajema.py")
pz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pz)


# ------------------------------------------------------------------ /proc/PID/stat

def test_stat_navaden_comm():
    s = pz.razcleni_stat("1234 (ffmpeg) S 1 1234 1234 0 -1 4194304 100 0 0 0 250 50 0 0 20 0 1 0 5000\n")
    assert s == {"pid": 1234, "comm": "ffmpeg", "stanje": "S", "utime": 250, "stime": 50}


def test_stat_comm_s_presledki_in_oklepaji():
    # comm "a) b (c)" - zakljucni ")" stat je zadnji v vrstici pred stanjem.
    s = pz.razcleni_stat("77 (a) b (c)) R 1 77 77 0 -1 0 0 0 0 0 7 3 0 0 20 0 1 0 1")
    assert s["pid"] == 77 and s["comm"] == "a) b (c)" and s["stanje"] == "R"
    assert (s["utime"], s["stime"]) == (7, 3)


def test_stat_prekratek_ali_pokvarjen():
    with pytest.raises(ValueError):
        pz.razcleni_stat("5 (x) S 1 2 3")
    with pytest.raises(ValueError):
        pz.razcleni_stat("brez oklepajev")


def test_proc_stat_in_cgroup():
    zasedeno, vse = pz.razcleni_proc_stat("cpu  100 5 50 1000 20 3 2 0 0 0\ncpu0 1 2 3 4 5 6 7 8 0 0\n")
    assert (zasedeno, vse) == (160, 1180)
    assert pz.razcleni_cpu_stat("usage_usec 123456\nuser_usec 100000\nsystem_usec 23456\n") == 123456
    with pytest.raises(ValueError):
        pz.razcleni_cpu_stat("user_usec 1\n")


def test_delez_jedra():
    assert pz.delez_jedra(0.5, 1.0) == 50.0
    assert pz.delez_jedra(3.0, 2.0) == 150.0          # vec jeder
    assert pz.delez_jedra(1.0, 0.0) is None


def test_ffmpeg_kms_po_ukazni_vrstici():
    argv = ["/usr/bin/ffmpeg", "-hide_banner", "-device", "/dev/dri/card0", "-f", "kmsgrab", "-framerate", "60",
            "-i", "-", "-vf", "hwmap=derive_device=vaapi,scale_vaapi=w=1920:h=1080:format=nv12", "-"]
    assert pz.je_ffmpeg_kms(argv, 1920, 1080) is True
    assert pz.je_ffmpeg_kms(argv, 1280, 720) is False
    assert pz.je_ffmpeg_kms(["/usr/bin/ffmpeg", "-f", "x11grab"], 1920, 1080) is False
    assert pz.je_ffmpeg_kms([], 1920, 1080) is False


# ------------------------------------------------------------------ statistika

def test_percentil_in_mediana():
    vrednosti = [float(v) for v in range(1, 101)]
    assert pz.percentil(vrednosti, 95) == 95.0 and pz.percentil(vrednosti, 99) == 99.0
    assert pz.percentil([7.0], 99) == 7.0 and pz.percentil([], 50) is None
    assert pz.mediana([1.0, 2.0, 3.0]) == 2.0 and pz.mediana([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert pz.mediana([]) is None


def test_statistika_razmikov_in_prekinitev():
    casi = [0.0, 16.0, 33.0, 50.0, 100.0, 116.0]          # en zastoj 50 ms pri 60 slikah/s
    s = pz.statistika(casi, [1000, 200, 300, 250, 220], 60)
    assert s["slik"] == 6.0
    assert abs(s["fps"] - 5 * 1000.0 / 116.0) < 1e-9
    assert s["razmik_med_ms"] == 17.0
    assert s["razmik_p95_ms"] == 50.0 and s["razmik_p99_ms"] == 50.0 and s["razmik_max_ms"] == 50.0
    assert s["prekinitev"] == 1.0                          # 50 > 2000/60 = 33,3; 17 ni
    assert s["slika_povp_b"] == 394.0 and s["slika_max_b"] == 1000.0


def test_statistika_brez_slik():
    s = pz.statistika([], [], 60)
    assert s["slik"] == 0.0 and s["fps"] is None and s["razmik_med_ms"] is None
    assert s["prekinitev"] == 0.0 and s["slika_povp_b"] is None


# ------------------------------------------------------------------ meje slik

def _nal(vrsta, prvi_mb0=True, dolzina=20, stiri=True):
    koda = b"\x00\x00\x00\x01" if stiri else b"\x00\x00\x01"
    telo = bytes([0x80 if prvi_mb0 else 0x40]) + b"\x11" * dolzina
    return koda + bytes([0x60 | vrsta]) + telo


def test_meje_slik_cez_kose_in_velikosti():
    s1 = _nal(9) + _nal(7) + _nal(8) + _nal(5)            # AUD SPS PPS IDR
    s2 = _nal(9) + _nal(1)
    s3 = _nal(9) + _nal(1)
    tok = s1 + s2 + s3
    m = pz.MejeSlik()
    # Prvi rez je sredi 4-bajtne zacetne kode slike 2, drugi takoj za prvim bajtom slike 3.
    r1, r2 = len(s1) + 2, len(s1) + len(s2) + 1
    assert [m.dodaj(tok[:r1], 10.0), m.dodaj(tok[r1:r2], 27.0), m.dodaj(tok[r2:], 43.0)] == [1, 1, 1]
    assert m.zacetki == [(0, 10.0), (len(s1), 27.0), (len(s1) + len(s2), 43.0)]
    assert m.velikosti == [len(s1), len(s2)]


def test_povzetek_samo_po_ogrevanju():
    s = _nal(9) + _nal(1)
    m = pz.MejeSlik()
    for i in range(5):
        m.dodaj(s, 100.0 * i)
    p = pz.povzetek_meja(m, 200.0, 30)
    assert p["slik"] == 3.0 and p["razmik_med_ms"] == 100.0
    assert p["prekinitev"] == 3.0 - 1.0                    # 100 > 2000/30 = 66,7
    assert p["slika_povp_b"] == float(len(s))               # zadnja slika nima velikosti


# ------------------------------------------------------------------ izpis

def test_preglednica_in_strojna_vrstica_brez_kms():
    a = pz.statistika([0.0, 16.0, 33.0], [100, 100], 60)
    a["ffmpeg_cpu_pct"] = 12.345
    besedilo = pz.preglednica(a, None)
    assert "A x11grab" in besedilo and "B KMS" in besedilo and "12.3" in besedilo
    vrstica = pz.vrstica_strojna({"w": 1920, "h": 1080, "fps": 60, "trajanje_s": 20.0,
                                  "kodirnik": "h264_vaapi"}, a, None, "ni_pomocnika")
    deli = vrstica.split()
    assert deli[0] == "KMS_PRIMERJAVA" and "kms=ni_pomocnika" in deli
    assert "x11_ffmpeg_cpu_pct=12.3" in deli and "kms_ffmpeg_cpu_pct=na" in deli
    assert all("=" in d for d in deli[1:])


# ------------------------------------------------------------------ varnost poti (najdbe B1, B2, B3, B6)

def test_x_streznik_za_display_ne_prvi_po_vrsti(monkeypatch):
    stat = {10: "10 (Xorg) S 1 10 10 0 -1 0 0 0 0 0 5 5 0 0 20 0 1 0 1",
            20: "20 (Xorg) S 1 20 20 0 -1 0 0 0 0 0 9 9 0 0 20 0 1 0 1"}
    argv = {10: ["/usr/lib/xorg/Xorg", ":1", "vt1"], 20: ["/usr/lib/xorg/Xorg", ":0", "vt2"]}
    monkeypatch.setattr(pz, "_pidi", lambda: [10, 20])        # prijavni zaslon (:1) je prvi v /proc
    monkeypatch.setattr(pz, "_beri", lambda pot: stat.get(int(pot.split("/")[2])))
    monkeypatch.setattr(pz, "_ukazna_vrstica", lambda pid: argv[pid])
    assert pz.najdi_x_streznik(":0") == 20 and pz.najdi_x_streznik(":0.0") == 20


class _Obstali:
    """Proces, ki SIGTERM prezre: read vrne EOF sele po kill (ali po 5 s brez njega)."""

    def __init__(self):
        self.ubit = threading.Event()

    def read(self, n):
        self.ubit.wait(5.0)
        return b""

    def terminate(self):
        pass

    def wait(self, timeout=None):
        if not self.ubit.wait(timeout):
            raise subprocess.TimeoutExpired("ffmpeg", timeout)

    def kill(self):
        self.ubit.set()


def test_varovalo_po_sigterm_poslje_sigkill(monkeypatch):
    monkeypatch.setattr(pz, "OGREVANJE_S", 0.0)
    monkeypatch.setattr(pz, "VAROVALO_REZERVA_S", 0.05)
    monkeypatch.setattr(pz, "VAROVALO_KILL_S", 0.05)
    s = _Obstali()
    pz.izmeri(s, None, None, 60, 0.01, storitev=False)
    assert s.ubit.is_set()


def test_trajanje_nan_in_inf_zavrnjeno(monkeypatch, capsys):
    monkeypatch.setattr(pz.shutil, "which", lambda ime: None)
    for vrednost in ("nan", "inf"):
        assert pz.main(["--display", ":0", "--trajanje", vrednost]) == 2
        assert "--trajanje" in capsys.readouterr().err


def test_strojna_vrstica_pove_izvor():
    a = pz.statistika([0.0, 16.0], [100], 60)
    nast = {"w": 1920, "h": 1080, "fps": 60, "trajanje_s": 1.0, "kodirnik": "libx264", "izvor": pz.NI}
    assert "izvor=na" in pz.vrstica_strojna(nast, a, None, "ni_pomocnika").split()
    nast["izvor"] = "3840x2160"
    assert "izvor=3840x2160" in pz.vrstica_strojna(nast, a, None, "ni_pomocnika").split()

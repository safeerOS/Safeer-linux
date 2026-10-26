"""Viri stroja za clane kroga (core/link_viri.py): meje odlocajo pravi viri, merjeni sproti; zavrnitev ni tiha.

Lastnik, 18. 10. 2026: clan kroga nima fiksne stevilke - ustavijo ga samo deskriptorji, pomnilnik ali niti, in takrat
dobi jasno sporocilo v svojem jeziku.
"""
import collections
import os
import resource
import threading

import pytest

from core import link_viri, pomnilnik


@pytest.fixture(autouse=True)
def cisto():
    link_viri.ponastavi()
    yield
    link_viri.ponastavi()


def test_pravi_viri_tega_procesa_zadoscajo():
    """Na zdravem racunalniku (ta preizkus) je dovolj virov za tisoc tunelov - brez nadomestkov."""
    assert link_viri.preveri(3 * 1000, 0) == "" or link_viri.meja_deskriptorjev() < 4000
    assert link_viri.preveri(1, 1024 * 1024) == ""
    assert pomnilnik.na_voljo() > 0 and pomnilnik.skupaj() >= pomnilnik.na_voljo()


def test_deskriptorji_nad_rezervo(monkeypatch):
    monkeypatch.setattr(link_viri, "meja_deskriptorjev", lambda: 1024)
    odprtih = len(os.listdir("/proc/self/fd"))
    # pri meji 1024 je rezerva cetrtina (256)
    assert link_viri.rezerva_deskriptorjev(1024) == 256
    assert link_viri.rezerva_deskriptorjev(65536) == link_viri.REZERVA_DESKRIPTORJEV
    prosti = link_viri.prostih_deskriptorjev()
    assert abs(prosti - (1024 - 256 - odprtih)) <= 2
    assert link_viri.preveri(prosti + 10) == link_viri.DESKRIPTORJI
    assert link_viri.preveri(max(1, prosti - 10)) == ""


def test_pomnilnik_nad_rezervo(monkeypatch):
    gib = 1024 ** 3
    monkeypatch.setattr(pomnilnik, "skupaj", lambda: 8 * gib)
    monkeypatch.setattr(pomnilnik, "na_voljo", lambda: int(0.06 * 8 * gib))
    # 5 % od 8 GiB = 410 MiB rezerve; na voljo 6 % = 492 MiB -> nad rezervo ~82 MiB
    assert link_viri.preveri(1, 64 * 1024 * 1024) == ""
    assert link_viri.preveri(1, 128 * 1024 * 1024) == link_viri.POMNILNIK
    monkeypatch.setattr(pomnilnik, "skupaj", lambda: 2 * gib)        # 5 % je manj kot 256 MiB: velja 256 MiB
    monkeypatch.setattr(pomnilnik, "na_voljo", lambda: 200 * 1024 * 1024)
    assert link_viri.preveri() == link_viri.POMNILNIK


def test_brez_podatka_sprejmemo(monkeypatch):
    """Sistem brez /proc in brez meje (Windows): ne vemo vec od sistema - sprejmemo, sistem sam zavrne, kar ne gre."""
    monkeypatch.setattr(link_viri, "meja_deskriptorjev", lambda: -1)
    monkeypatch.setattr(pomnilnik, "na_voljo", lambda: -1)
    assert link_viri.prostih_deskriptorjev() is None and link_viri.prostega_pomnilnika() is None
    assert link_viri.preveri(10 ** 6, 10 ** 12) == ""


def test_emfile_pomeni_nic_prostih(monkeypatch):
    def polno(_pot):
        raise OSError(24, "Too many open files")
    monkeypatch.setattr(link_viri.os, "listdir", polno)
    assert link_viri.prostih_deskriptorjev() < 0
    assert link_viri.preveri(1) == link_viri.DESKRIPTORJI


def test_pomanjkanje_v_stanju_dnevniku_in_obvestilu_redko(monkeypatch, capsys):
    klici = []
    monkeypatch.setattr(link_viri, "POSLUSALCI", [lambda r, k, n: klici.append((r, k, n))])
    for _ in range(5):
        link_viri.zabelezi(link_viri.POMNILNIK, "hub")
    st = link_viri.stanje()
    assert st["razlog"] == link_viri.POMNILNIK and st["kje"] == "hub" and st["zavrnjenih"] == 5
    assert klici == [(link_viri.POMNILNIK, "hub", 1)]           # obvestilo najvec enkrat na OBVESTILO_VSAKIH_S
    assert capsys.readouterr().out.count("[SafeerLink] viri:") == 1
    link_viri.ponastavi()
    assert link_viri.stanje() == {}


def test_druga_naprava_nas_zavrne(monkeypatch):
    imena = []
    monkeypatch.setattr(link_viri, "POSLUSALCI_DRUGIH", [imena.append])
    link_viri.zavrnila_druga("Pisarna\n2")
    link_viri.zavrnila_druga("Pisarna 2")
    assert link_viri.zavrnile_druge() == ["Pisarna 2"] and imena == ["Pisarna 2"]


def test_rezerva_diska_je_delez_diska(monkeypatch, tmp_path):
    gib = 1024 ** 3
    Disk = collections.namedtuple("Disk", "total used free")
    for skupaj, pricakovano in ((32 * gib, gib), (256 * gib, int(256 * gib * 0.02)), (4096 * gib, 10 * gib)):
        monkeypatch.setattr(link_viri.shutil, "disk_usage", lambda _m, s=skupaj: Disk(s, 0, s))
        assert link_viri.rezerva_diska(str(tmp_path)) == pricakovano


def test_jezik_iz_okolja(monkeypatch):
    for kljuc in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(kljuc, raising=False)
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert link_viri.jezik() == "de"
    monkeypatch.setenv("LANGUAGE", "sl:en")
    assert link_viri.jezik() == "sl"
    monkeypatch.setenv("LANGUAGE", "ja")
    assert link_viri.jezik() == "en"


def test_nit_ki_je_sistem_ne_da(monkeypatch):
    class Nit:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")
    monkeypatch.setattr(link_viri.threading, "Thread", Nit)
    monkeypatch.setattr(link_viri, "POSLUSALCI", [])
    assert link_viri.zazeni_nit(lambda: None, kje="preizkus") is False
    assert link_viri.stanje()["razlog"] == link_viri.NITI


def test_meja_procesa_je_prava():
    mehka, _trda = resource.getrlimit(resource.RLIMIT_NOFILE)
    assert link_viri.meja_deskriptorjev() in (mehka, -1)


def test_stetje_deskriptorjev_dalec_od_meje_redko_blizu_meje_vedno(monkeypatch):
    """Stetje /proc/self/fd stane (6,8 ms pri 10 000): dalec od meje velja meritev do SVEZE_S, blizu meje se steje
    ob vsakem vprasanju."""
    klici = []
    pravi = os.listdir
    # Samo klici te niti na /proc/self/fd: link_viri.os je modul os za ves proces; na CI (26. 10. 2026, 7 != 5) so
    # niti drugih preizkusov medtem brale /proc/<pid>/task in /proc/self/fd.
    glavna = threading.get_ident()

    def stej(pot):
        if threading.get_ident() == glavna and pot == "/proc/self/fd":
            klici.append(pot)
        return pravi(pot)
    monkeypatch.setattr(link_viri.os, "listdir", stej)
    monkeypatch.setattr(link_viri, "meja_deskriptorjev", lambda: 65536)
    for _ in range(5):
        link_viri.preveri(3)
    assert len(klici) == 1
    link_viri.ponastavi()
    klici.clear()
    monkeypatch.setattr(link_viri, "meja_deskriptorjev", lambda: len(pravi("/proc/self/fd")) + 600)
    for _ in range(5):
        link_viri.preveri(3)
    assert len(klici) == 5

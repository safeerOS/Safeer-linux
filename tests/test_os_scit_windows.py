"""Scit na Windows: platformni sloj (core/os_scit_windows.py) z lazljivim PowerShellom, delegacija iz os_scit.py (enotna koda)."""
import base64
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import os_scit, os_scit_windows as w  # noqa: E402


class LazniPs:
    """Zapomni si ukaze; odgovor po delu ukaza (prvi zadetek), privzeto (0, "")."""

    def __init__(self, odgovori=None):
        self.odgovori = odgovori or {}
        self.ukazi = []

    def __call__(self, ukaz, cas=15.0):
        self.ukazi.append(ukaz)
        for del_ukaza, odg in self.odgovori.items():
            if del_ukaza in ukaz:
                return odg
        return 0, ""


@pytest.fixture
def okolje(tmp_path, monkeypatch):
    monkeypatch.setenv("ProgramData", str(tmp_path / "pd"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "la"))
    (tmp_path / "pd" / "Safeer" / "ScitDns").mkdir(parents=True)
    return tmp_path


def test_vrata_na_linuxu_nespremenjena():
    assert sys.platform != "win32"
    assert os_scit.VRATA == (5354, 5355, 5356, 5357)


def test_indeks_samo_ascii_stevke():
    assert w.veljaven_indeks("12")
    for slab in ("", "1 2", "12;calc", "-1", "1234567", "١٢", "12\n", None):
        assert not w.veljaven_indeks(slab)


def test_skripta_regex_sprejme_samo_set_in_reset():
    izraz = re.search(r"-match '([^']+)'", w.SKRIPTA).group(1)
    for ok in ("SET 12", "RESET 3"):
        assert re.fullmatch(izraz, ok)
    for slab in ("SET 12; calc", "SET 1 2", "SET", "RESET abc", "SET 1234567", "DEL 5", "SET ١"):
        assert not re.fullmatch(izraz, slab)
    assert "127.0.0.1" in w.SKRIPTA and "-Physical" in w.SKRIPTA
    assert w.SKRIPTA.count("Set-DnsClientServerAddress") == 2


def test_zahteva_zavrne_slabe_vhode_brez_klica_ps(okolje, monkeypatch):
    ps = LazniPs()
    monkeypatch.setattr(w, "_ps", ps)
    assert not w._zahteva("DROP", "5")
    assert not w._zahteva("SET", "5; calc")
    assert not w._zahteva("SET", "")
    assert ps.ukazi == []


def test_usmeri_shrani_prvotni_dns_in_zahteva_set(okolje, monkeypatch):
    ps = LazniPs({"Get-DnsClientServerAddress": (0, "192.168.1.1\n8.8.8.8")})
    monkeypatch.setattr(w, "_ps", ps)
    assert w.usmeri("12", 53) == ""
    assert (okolje / "pd" / "Safeer" / "ScitDns" / "zahteva.txt").read_text() == "SET 12\n"
    assert any("Start-ScheduledTask -TaskName SafeerScitDns" in u for u in ps.ukazi)
    # po nastavitvi je DNS vmesnika 127.0.0.1: prvotni ostanejo v shrambi, posredujemo nanje
    monkeypatch.setattr(w, "_ps", LazniPs({"Get-DnsClientServerAddress": (0, "127.0.0.1")}))
    assert w.usmeri("12", 53) == ""
    assert w.upstream_strezniki("12") == ["192.168.1.1", "8.8.8.8"]


def test_usmeri_naloga_ne_steče_je_pravilo(okolje, monkeypatch):
    monkeypatch.setattr(w, "_ps", LazniPs({"Start-ScheduledTask": (1, ""), "Get-DnsClientServerAddress": (0, "10.0.0.1")}))
    assert w.usmeri("7", 53) == "pravilo"
    assert w.usmeri("x", 53) == "pravilo"


def test_povrni_zahteva_reset(okolje, monkeypatch):
    monkeypatch.setattr(w, "_ps", LazniPs())
    assert w.povrni("4")
    assert (okolje / "pd" / "Safeer" / "ScitDns" / "zahteva.txt").read_text() == "RESET 4\n"


def test_dns_vmesnika_nas_naslov_dobi_vrata(monkeypatch):
    monkeypatch.setattr(w, "_ps", LazniPs({"Get-DnsClientServerAddress": (0, "127.0.0.1\n9.9.9.9")}))
    assert w.dns_vmesnika("3") == "127.0.0.1:53 9.9.9.9"
    assert w.trenutni_streznik("3") == "127.0.0.1:53"


def test_vmesniki_povezani_samo_stevilke(monkeypatch):
    monkeypatch.setattr(w, "_ps", LazniPs({"Get-NetAdapter": (0, "12\nnapaka\n7\n")}))
    assert w.vmesniki_povezani() == ["12", "7"]
    monkeypatch.setattr(w, "_ps", LazniPs({"Get-NetAdapter": (1, "")}))
    assert w.vmesniki_povezani() == []


def test_vrata_nasa_zavrne_neveljavna_vrata(monkeypatch):
    ps = LazniPs()
    monkeypatch.setattr(w, "_ps", ps)
    for slaba in (0, -1, 70000, "53", None):
        assert not w.vrata_nasa(slaba)
    assert ps.ukazi == []
    monkeypatch.setattr(w, "_ps", LazniPs({"Get-NetUDPEndpoint": (0, "")}))
    assert w.vrata_nasa(53)
    monkeypatch.setattr(w, "_ps", LazniPs({"Get-NetUDPEndpoint": (4, "")}))
    assert not w.vrata_nasa(53)


def test_namestitev_je_fiksna_in_vsebuje_skripto():
    ps = w._namesti_ps()
    assert "Register-ScheduledTask -TaskName 'SafeerScitDns'" in ps
    assert "-RunLevel Highest" in ps and "'Users:(OI)(CI)RX'" in ps
    b64 = re.search(r"FromBase64String\('([^']+)'\)", ps).group(1)
    assert base64.b64decode(b64).decode("utf-8") == w.SKRIPTA
    assert base64.b64decode(w._kodiraj("a b")).decode("utf-16-le") == "a b"


def test_ni_powershella_razlog(monkeypatch):
    monkeypatch.setattr(w.shutil, "which", lambda _x: None)
    assert w.razlog_nemoznosti() == "ni_resolved"
    assert w._ps("x") == (1, "")


def test_delegacija_iz_os_scit_na_windows(monkeypatch):
    klici = []

    class Laz:
        def __getattr__(self, ime):
            def f(*a):
                klici.append((ime, a))
                return {"vmesniki_povezani": ["5"], "usmeri": "", "povrni": True}.get(ime, "x")
            return f

    monkeypatch.setattr(os_scit, "_windows", lambda: Laz())
    monkeypatch.setattr(sys, "platform", "win32")
    assert os_scit.vmesniki_povezani() == ["5"]
    assert os_scit.usmeri("5", 53) == ""
    assert os_scit.povrni("5") is True
    assert os_scit.za_vticnico("10.0.0.1", "5") == "10.0.0.1"
    assert os_scit.nm_domene("5") == []
    os_scit.upstream_strezniki("5")
    os_scit.nekdo_poslusa(53)
    os_scit.vrata_nasa(53)
    os_scit.tuj_scit("127.0.0.1:53", 53)
    imena = [i for i, _ in klici]
    for ime in ("vmesniki_povezani", "usmeri", "povrni", "upstream_strezniki", "nekdo_poslusa", "vrata_nasa", "tuj_scit"):
        assert ime in imena
    assert ("usmeri", ("5", 53, None)) in klici

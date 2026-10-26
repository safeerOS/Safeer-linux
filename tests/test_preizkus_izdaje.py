"""Preizkusi ovoja tools/preizkus_izdaje.py brez pravih naprav in paketov.

adb, readelf, dpkg-deb in dpkg-query so lazni programi v zacasni mapi na zacetku PATH; obstojeca preizkusa
(packaging/smoke_webkit_deb.py, tests/preizkus_po_gradnji.py) sta lazni skripti v laznem repozitoriju, ki se obnasata
po spremenljivkah okolja. Tako preverimo samo ovoj: tisino ob uspehu, napake z ukazom/kodo/30 vrsticami, kode izhoda.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

# Ovoj je v tools/, preizkus v tests/; pri plosci kopiji (oba v isti mapi) ga najdemo tudi zraven.
_TU = Path(__file__).resolve().parent
_KANDIDATI = [_TU.parent / "tools" / "preizkus_izdaje.py", _TU / "preizkus_izdaje.py"]
_POT = next(p for p in _KANDIDATI if p.is_file())
_spec = importlib.util.spec_from_file_location("preizkus_izdaje", _POT)
pi = importlib.util.module_from_spec(_spec)
sys.modules["preizkus_izdaje"] = pi
_spec.loader.exec_module(pi)

PY = sys.executable

# ---------------------------------------------------------------------- lazni programi

LAZNI_DPKG_DEB = r'''
import json, os, sys
a = sys.argv[1:]
if a[0] == "-x":
    opis = json.load(open(a[1]))
    if opis.get("pokvarjen"):
        print("dpkg-deb: error: not a debian format archive"); sys.exit(2)
    for rel, vsebina in opis["datoteke"].items():
        pot = os.path.join(a[2], rel)
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        with open(pot, "wb") as f:
            if vsebina.startswith("ELF:"):
                # glava ELF64 LE, e_type na odmiku 16, nato oznaka za lazni readelf
                tip = b"\x02\x00" if "EXEC" in vsebina else b"\x03\x00"
                f.write(b"\x7fELF\x02\x01" + b"\0" * 10 + tip + vsebina[4:].encode())
            else:
                f.write(vsebina.encode())
elif a[0] == "-f":
    print(json.load(open(a[1]))[a[2]])
'''

LAZNI_READELF = r'''
import sys
stikalo, pot = sys.argv[1], sys.argv[2]
oznaka = open(pot, "rb").read()[18:].decode()
polja = dict(d.split("=", 1) for d in oznaka.split(";") if "=" in d)
if stikalo == "-lW":
    print("Program Headers:")
    print("  LOAD           0x000000 0x0000000000000000 0x0000000000000000 0x001000 0x001000 R   0x1000")
    if polja.get("STACK", "brez") != "brez":
        print("  GNU_STACK      0x000000 0x0000000000000000 0x0000000000000000 0x000000 0x000000 %-3s 0x10" % polja["STACK"])
else:
    now = polja.get("NOW", "da")
    if now == "staticen":
        print("\nThere is no dynamic section in this file."); sys.exit(0)
    print("Dynamic section at offset 0x2d00 contains 3 entries:")
    print(" 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]")
    if now == "da":
        print(" 0x000000006ffffffb (FLAGS_1)            Flags: NOW PIE")
'''

LAZNI_DPKG_QUERY = r'''
import json, os, sys
paket = sys.argv[-1]
nam = json.loads(os.environ.get("FAKE_NAMESCENO", "{}"))
if paket not in nam:
    print("dpkg-query: no packages found matching " + paket, file=sys.stderr); sys.exit(1)
print("install ok installed|" + nam[paket], end="")
'''

LAZNI_ADB = r'''
import os, sys
with open(os.environ["FAKE_ADB_LOG"], "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\n")
a = sys.argv[1:]
if a[0] == "connect":
    print("already connected"); sys.exit(0)
if "get-state" in a:
    print(os.environ.get("FAKE_STANJE", "device")); sys.exit(0)
if "dumpsys" in a and "activity" in a:
    print("  topResumedActivity=ActivityRecord{1a2b u0 %s/.Glavna t12}" % os.environ.get("FAKE_OSPREDJE", "si.safeer.os"))
    sys.exit(0)
print("adb: neznan ukaz", file=sys.stderr); sys.exit(1)
'''

LAZNI_SMOKE = r'''
import os, sys
nacin = os.environ.get("FAKE_SMOKE", "ok")
with open(os.environ["FAKE_SMOKE_LOG"], "a") as f:
    f.write(sys.argv[1] + "\n")
if nacin == "fail":
    for i in range(40):
        print("smoke vrstica %d" % i)
    print("FAIL: libsoup-3.0 ni iz predpone"); print("FAIL: 1 napak"); sys.exit(1)
if nacin == "brez_pass":
    sys.exit(0)
if nacin == "opozorilo":
    print("OPOZORILO: libjavascriptcoregtk brez BOLT (gradnja.txt)")
print("PASS: nas WebKitGTK")
'''

LAZNI_ANDROID = r'''
import os, subprocess, sys, time
with open(os.environ["FAKE_ANDROID_LOG"], "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\n")
nacin = os.environ.get("FAKE_ANDROID", "ok")
if nacin == "napaka":
    for i in range(50):
        print("android vrstica %d" % i)
    print("NAPAKA  %s posodobitev je vzela dovoljenja: PROJECT_MEDIA allow -> default" % sys.argv[1])
    print("PREIZKUS PO GRADNJI: NAPAKA"); sys.exit(1)
if nacin == "spi":
    # vnuk v svoji seji: ubiti ga mora pospravljanje po PID, ne samo po skupini procesov
    vnuk = subprocess.Popen(["sleep", "300"], start_new_session=True)
    with open(os.environ["FAKE_PIDI"], "w") as f:
        f.write("%d %d" % (os.getpid(), vnuk.pid))
    time.sleep(300)
if nacin == "brez_potrdila":
    sys.exit(0)
print("OK      %s 1.2.3 | film: slika 800 ms | sesutij: 0" % sys.argv[1])
print("PREIZKUS PO GRADNJI: OK")
'''


def _program(mapa: Path, ime: str, koda: str) -> None:
    p = mapa / ime
    p.write_text("#!%s\n%s" % (PY, textwrap.dedent(koda)))
    p.chmod(0o755)


def _deb(mapa: Path, ime: str, paket: str, razl: str, datoteke: dict, **dodatno) -> Path:
    p = mapa / ime
    p.write_text(json.dumps({"Package": paket, "Version": razl, "datoteke": datoteke, **dodatno}))
    return p


@pytest.fixture
def okolje(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for ime, koda in (("dpkg-deb", LAZNI_DPKG_DEB), ("readelf", LAZNI_READELF), ("dpkg-query", LAZNI_DPKG_QUERY),
                      ("adb", LAZNI_ADB)):
        _program(bin_, ime, koda)
    repo = tmp_path / "repo"
    (repo / "packaging").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "packaging" / "smoke_webkit_deb.py").write_text(LAZNI_SMOKE)
    (repo / "tests" / "preizkus_po_gradnji.py").write_text(LAZNI_ANDROID)
    debi = tmp_path / "debi"
    debi.mkdir()
    _deb(debi, "safeer-webkit_2.50_amd64.deb", "safeer-webkit", "2.50", {
        "usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4": "ELF:STACK=RW;NOW=da",
        "usr/lib/safeer-webkit/libexec/webkitgtk-6.0/WebKitWebProcess": "ELF:STACK=RW;NOW=da",
        "usr/lib/safeer-webkit/share/webkitgtk-safeer/gradnja.txt": "clang version 22.",
        "usr/lib/debug/.build-id/ab/cdef.debug": "ELF:STACK=brez;NOW=ne",   # izpuscen
    })
    _deb(debi, "safeer-browser_1.0_amd64.deb", "safeer-browser", "1.0", {
        "usr/lib/safeer-browser/core/zasebni_webkit.py": "# lazno",
        "usr/lib/safeer-browser/safeer-browser.py": "print()",
    })
    apk = tmp_path / "app.apk"
    apk.write_text("apk")
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    dnevniki = {k: tmp_path / ("%s.log" % k) for k in ("adb", "smoke", "android")}
    monkeypatch.setenv("PATH", "%s%s%s" % (bin_, os.pathsep, os.environ["PATH"]))
    monkeypatch.setenv("FAKE_ADB_LOG", str(dnevniki["adb"]))
    monkeypatch.setenv("FAKE_SMOKE_LOG", str(dnevniki["smoke"]))
    monkeypatch.setenv("FAKE_ANDROID_LOG", str(dnevniki["android"]))
    monkeypatch.setenv("FAKE_PIDI", str(tmp_path / "pidi"))
    monkeypatch.setenv("FAKE_NAMESCENO", json.dumps({"safeer-webkit": "2.50", "safeer-browser": "1.0"}))
    monkeypatch.setattr(pi, "ZAKLEP", str(tmp_path / "safeer-naprava-{}.lock"))
    # Zacasne datoteke ovoja v nadzorovani mapi: po koncu mora biti prazna.
    monkeypatch.setattr("tempfile.tempdir", str(tmp))

    class Okolje:
        pass
    o = Okolje()
    o.pot, o.repo, o.debi, o.apk, o.tmp, o.dnevniki = tmp_path, repo, debi, apk, tmp, dnevniki
    o.izhod = tmp_path / "porocilo.json"

    def pozeni(*arg):
        return pi.main(["--repo", str(repo), "--izhod", str(o.izhod), *map(str, arg)])
    o.pozeni = pozeni
    o.json = lambda: json.loads(o.izhod.read_text())
    o.dnevnik = lambda k: dnevniki[k].read_text().splitlines() if dnevniki[k].exists() else []
    return o


# ---------------------------------------------------------------------- ciste funkcije

def test_razcleni_android_z_vrati_in_brez():
    assert pi.razcleni_android("192.168.1.5:5555=si.safeer.os:/a/b.apk") == ("192.168.1.5:5555", "si.safeer.os", "/a/b.apk")
    assert pi.razcleni_android("R58M=si.safeer.phone:app.apk") == ("R58M", "si.safeer.phone", "app.apk")
    for slab in ("192.168.1.5", "n=si.safeer.os", "=si.safeer.os:a.apk", "n=:a.apk"):
        with pytest.raises(argparse.ArgumentTypeError):
            pi.razcleni_android(slab)


def test_ime_zaklepa_brez_vrat(monkeypatch):
    monkeypatch.setattr(pi, "ZAKLEP", "/tmp/safeer-naprava-{}.lock")
    assert pi.ime_zaklepa("192.168.1.5:5555") == "/tmp/safeer-naprava-192.168.1.5.lock"
    assert pi.ime_zaklepa("192.168.1.5") == "/tmp/safeer-naprava-192.168.1.5.lock"
    assert pi.ime_zaklepa("../../etc/x") == "/tmp/safeer-naprava-.._.._etc_x.lock"


@pytest.mark.parametrize("ukaz", [["sudo", "dpkg", "-i", "x.deb"], ["/usr/bin/pkexec", "true"],
                                  ["/usr/bin/safeer-browser"], ["flock", "/tmp/x.lock", "sudo", "true"],
                                  ["python3", "/usr/bin/safeer-os"]])
def test_prepovedani_ukazi(ukaz):
    with pytest.raises(pi.PrepovedanUkaz):
        pi.preveri_ukaz(ukaz)


def test_prepovedan_ukaz_se_ne_zazene(tmp_path):
    with pytest.raises(pi.PrepovedanUkaz):
        pi.pozeni(["sudo", "touch", str(tmp_path / "ne")], 5, str(tmp_path))
    assert not (tmp_path / "ne").exists()


def test_gnu_stack_in_bind_now():
    rw = "  GNU_STACK      0x000000 0x0000000000000000 0x0000000000000000 0x000000 0x000000 RW  0x10\n"
    rwe = rw.replace("RW  0x10", "RWE 0x10")
    assert pi.gnu_stack(rw) == "RW "
    assert pi.gnu_stack(rwe) == "RWE"
    assert pi.gnu_stack("  LOAD 0x0 ...\n") is None
    dyn = "Dynamic section at offset 0x10 contains 2 entries:\n 0x1 (NEEDED) Shared library: [libc.so.6]\n"
    assert pi.bind_now(dyn + " 0x18 (BIND_NOW)\n") is True
    assert pi.bind_now(dyn + " 0x1e (FLAGS)  BIND_NOW\n") is True
    assert pi.bind_now(dyn + " 0x6ffffffb (FLAGS_1) Flags: NOW PIE\n") is True
    assert pi.bind_now(dyn + " 0x6ffffffb (FLAGS_1) Flags: PIE\n") is False
    assert pi.bind_now("\nThere is no dynamic section in this file.\n") is None


def test_ospredje():
    assert pi.ospredje("  topResumedActivity=ActivityRecord{1 u0 si.safeer.os/.A t1}") == "si.safeer.os"
    assert pi.ospredje("  mResumedActivity: ActivityRecord{1 u0 com.filmbox/.B t2}") == "com.filmbox"
    assert pi.ospredje("  mCurrentFocus=Window{9 u0 si.safeer.phone/si.safeer.X}") == "si.safeer.phone"
    assert pi.ospredje("nic") == ""


# ---------------------------------------------------------------------- celoten ovoj

def test_vse_ok_tiho_izhod_0(okolje, capsys):
    # Koraki: utrjenost x2, namescene razlicice, smoke safeer-browser, android = 5.
    koda = okolje.pozeni("--linux-deb", okolje.debi, "--android", "10.0.0.7:5555=si.safeer.os:%s" % okolje.apk)
    izpis = capsys.readouterr()
    assert koda == 0
    # Ob uspehu samo povzetek - nic izpisa obstojecih preizkusov.
    assert izpis.out.splitlines() == ["OK 5 / NAPAKA 0"]
    assert izpis.err == ""
    j = okolje.json()
    assert (j["ok"], j["napake"], j["opozorila"], j["najdbe"]) == (5, 0, 0, [])
    assert okolje.dnevnik("smoke") == ["/usr/lib/safeer-browser"]
    assert okolje.dnevnik("android") == ["10.0.0.7:5555=si.safeer.os --apk %s" % okolje.apk]
    assert list(okolje.tmp.iterdir()) == []   # TemporaryDirectory pospravljen


def test_android_napaka_ukaz_koda_30_vrstic(okolje, capsys):
    os.environ["FAKE_ANDROID"] = "napaka"
    try:
        koda = okolje.pozeni("--android", "R58M=si.safeer.phone:%s" % okolje.apk)
    finally:
        del os.environ["FAKE_ANDROID"]
    out = capsys.readouterr().out
    assert koda == 1
    assert "NAPAKA [android R58M=si.safeer.phone]: izhodna koda 1" in out
    skripta = okolje.repo / "tests" / "preizkus_po_gradnji.py"
    assert "  ukaz: %s %s R58M=si.safeer.phone --apk %s" % (PY, skripta, okolje.apk) in out
    assert "  izhodna koda: 1" in out
    vrstice = [v for v in out.splitlines() if v.startswith("  | ")]
    assert len(vrstice) == 30
    assert vrstice[-1] == "  | PREIZKUS PO GRADNJI: NAPAKA"
    assert "android vrstica 21" not in out and "android vrstica 22" in out
    assert out.splitlines()[-1] == "OK 0 / NAPAKA 1"
    n = okolje.json()["najdbe"][0]
    assert n["izhodna_koda"] == 1 and len(n["izpis"]) == 30 and "preizkus_po_gradnji.py" in n["ukaz"]


def test_android_brez_potrdila_je_napaka(okolje, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_ANDROID", "brez_potrdila")
    assert okolje.pozeni("--android", "R58M=si.safeer.os:%s" % okolje.apk) == 1
    assert "brez vrstice 'PREIZKUS PO GRADNJI: OK'" in capsys.readouterr().out


def test_casovna_meja_pospravi_procese_po_pid(okolje, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_ANDROID", "spi")
    zacetek = time.monotonic()
    koda = okolje.pozeni("--rok", "3", "--android", "R58M=si.safeer.os:%s" % okolje.apk)
    assert time.monotonic() - zacetek < 20
    out = capsys.readouterr().out
    assert koda == 1
    assert "casovna meja 3 s prekoracena" in out
    otrok, vnuk = map(int, (okolje.pot / "pidi").read_text().split())
    time.sleep(0.3)
    assert not pi._zivi(otrok) and not pi._zivi(vnuk)
    assert list(okolje.tmp.iterdir()) == []


def test_ospredje_tuja_aplikacija_se_ne_dotakne(okolje, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_OSPREDJE", "com.filmbox.plus")
    koda = okolje.pozeni("--android", "10.0.0.7:5555=si.safeer.os:%s" % okolje.apk)
    out = capsys.readouterr().out
    assert koda == 1
    assert "v ospredju je com.filmbox.plus, ne si.safeer.*" in out
    assert okolje.dnevnik("android") == []   # preizkus po gradnji ni bil zagnan
    # na napravi samo branje: connect, get-state, dumpsys
    assert all(v.split()[0] == "connect" or v.split()[2] in ("get-state", "shell") and "dumpsys" in v or "get-state" in v
               for v in okolje.dnevnik("adb"))
    assert not any("install" in v or " am " in v for v in okolje.dnevnik("adb"))


def test_tuj_paket_in_manjkajoc_apk(okolje, capsys):
    koda = okolje.pozeni("--android", "A=com.filmbox:%s" % okolje.apk, "--android", "B=si.safeer.os:/ni/tega.apk")
    out = capsys.readouterr().out
    assert koda == 1
    assert "paket com.filmbox ni si.safeer.*" in out and "APK /ni/tega.apk ne obstaja" in out
    assert okolje.dnevnik("adb") == [] and okolje.dnevnik("android") == []


def test_zasedena_naprava_zaklep(okolje, capsys):
    pot = pi.ime_zaklepa("10.0.0.7:5555")
    with open(pot, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)   # kot drug preizkus z »flock /tmp/safeer-naprava-10.0.0.7.lock«
        koda = okolje.pozeni("--rok", "1", "--android", "10.0.0.7:5555=si.safeer.os:%s" % okolje.apk)
    out = capsys.readouterr().out
    assert koda == 1 and "naprava zasedena" in out and "safeer-naprava-10.0.0.7.lock" in out
    assert okolje.dnevnik("adb") == []


def test_zaklep_flock1_izkljucuje(okolje, capsys):
    # Pravi flock(1) drzi zaklep 2 s; ovoj z rokom 10 s pocaka in nato uspe.
    pot = pi.ime_zaklepa("10.0.0.8")
    drzi = subprocess.Popen(["flock", pot, "sleep", "2"])
    time.sleep(0.5)
    zacetek = time.monotonic()
    koda = okolje.pozeni("--rok", "10", "--android", "10.0.0.8=si.safeer.os:%s" % okolje.apk)
    drzi.wait()
    assert koda == 0 and time.monotonic() - zacetek >= 1.0
    assert capsys.readouterr().out.splitlines() == ["OK 1 / NAPAKA 0"]


def test_naprava_ni_povezana(okolje, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_STANJE", "offline")
    assert okolje.pozeni("--android", "R58M=si.safeer.os:%s" % okolje.apk) == 1
    assert "naprava ni povezana" in capsys.readouterr().out
    assert okolje.dnevnik("android") == []


def test_utrjenost_rwe_manjka_bind_now(okolje, capsys):
    _deb(okolje.debi, "safeer-dav1d_1.5_amd64.deb", "safeer-dav1d", "1.5", {
        "usr/lib/safeer-webkit/lib/gstreamer-1.0/libgstdav1d.so": "ELF:STACK=RWE;NOW=da",
        "usr/lib/safeer-webkit/lib/libbolt.so": "ELF:STACK=brez;NOW=da",
        "usr/lib/safeer-webkit/bin/WebKitWebDriver": "ELF:EXEC;STACK=RW;NOW=ne",
        "usr/lib/safeer-webkit/bin/staticen": "ELF:EXEC;STACK=RW;NOW=staticen",
    })
    os.environ["FAKE_NAMESCENO"] = json.dumps({"safeer-webkit": "2.50", "safeer-browser": "1.0", "safeer-dav1d": "1.5"})
    koda = okolje.pozeni("--linux-deb", okolje.debi)
    out = capsys.readouterr().out
    assert koda == 1
    assert "NAPAKA [utrjenost safeer-dav1d_1.5_amd64.deb]: 3 od 4 ELF krsi pravilo utrjene gradnje" in out
    assert "libgstdav1d.so: GNU_STACK 'RWE', mora biti RW brez E" in out
    assert "libbolt.so: PT_GNU_STACK manjka" in out
    assert "WebKitWebDriver: brez BIND_NOW" in out
    assert "OPOZORILO [utrjenost safeer-dav1d_1.5_amd64.deb]" in out and "staticen" in out
    assert out.splitlines()[-1] == "OK 4 / NAPAKA 1 (opozoril 1)"
    # napake pred opozorili
    assert out.index("NAPAKA [") < out.index("OPOZORILO [")


def test_razlicica_ni_namescena_smoke_preskocen(okolje, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_NAMESCENO", json.dumps({"safeer-webkit": "2.49"}))
    assert okolje.pozeni("--linux-deb", okolje.debi) == 1
    out = capsys.readouterr().out
    assert "namescen ni paket iz te izdaje" in out
    assert "safeer-webkit: namesceno '2.49', v .deb '2.50'" in out and "safeer-browser: namesceno 'ni'" in out
    assert okolje.dnevnik("smoke") == []


def test_razpakirano_smoke_nad_zacasnim_drevesom(okolje, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_NAMESCENO", "{}")
    assert okolje.pozeni("--linux-deb", okolje.debi, "--razpakirano") == 0
    assert capsys.readouterr().out.splitlines() == ["OK 3 / NAPAKA 0"]   # brez koraka razlicic
    koren = okolje.dnevnik("smoke")[0]
    assert koren.startswith(str(okolje.tmp)) and koren.endswith("/deb/usr/lib/safeer-browser")
    assert list(okolje.tmp.iterdir()) == []


def test_smoke_fail_in_opozorilo_in_brez_pass(okolje, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_SMOKE", "fail")
    assert okolje.pozeni("--linux-deb", okolje.debi) == 1
    out = capsys.readouterr().out
    assert "NAPAKA [smoke_webkit_deb safeer-browser]: izhodna koda 1" in out
    assert "  | FAIL: libsoup-3.0 ni iz predpone" in out and "smoke vrstica 11" not in out

    monkeypatch.setenv("FAKE_SMOKE", "opozorilo")
    assert okolje.pozeni("--linux-deb", okolje.debi) == 0
    out = capsys.readouterr().out
    assert "OPOZORILO [smoke_webkit_deb safeer-browser]: OPOZORILO: libjavascriptcoregtk brez BOLT" in out
    assert out.splitlines()[-1] == "OK 4 / NAPAKA 0 (opozoril 1)"

    monkeypatch.setenv("FAKE_SMOKE", "brez_pass")
    assert okolje.pozeni("--linux-deb", okolje.debi) == 1
    assert "izhod 0, a brez vrstice 'PASS'" in capsys.readouterr().out


def test_smoke_brskalnik_ce_obstaja(okolje, capsys):
    (okolje.repo / "packaging" / "smoke_brskalnik.py").write_text("print('PASS brskalnik')\n")
    assert okolje.pozeni("--linux-deb", okolje.debi) == 0
    assert capsys.readouterr().out.splitlines() == ["OK 5 / NAPAKA 0"]
    assert "smoke_brskalnik safeer-browser" in okolje.json()["uspesni_koraki"]


def test_pokvarjen_deb_in_prazna_mapa(okolje, capsys, tmp_path):
    _deb(okolje.debi, "zlomljen_1_amd64.deb", "zlomljen", "1", {}, pokvarjen=True)
    assert okolje.pozeni("--linux-deb", okolje.debi) == 1
    out = capsys.readouterr().out
    assert "NAPAKA [deb zlomljen_1_amd64.deb]: razpakiranje ni uspelo" in out and "  izhodna koda: 2" in out
    prazna = tmp_path / "prazna"
    prazna.mkdir()
    assert okolje.pozeni("--linux-deb", prazna) == 1
    assert "ni paketov .deb" in capsys.readouterr().out


def test_manjkajoc_program_je_napaka_ne_sesutje(okolje, capsys, monkeypatch):
    # Brez readelf in dpkg-deb na PATH: izjema FileNotFoundError postane NAPAKA, ovoj vseeno zapise porocilo.
    monkeypatch.setenv("PATH", "/nikjer")
    assert okolje.pozeni("--linux-deb", okolje.debi) == 1
    out = capsys.readouterr().out
    assert "izjema FileNotFoundError" in out
    assert okolje.json()["napake"] >= 1


def test_napacni_argumenti_izhod_2(okolje, capsys):
    assert pi.main([]) == 2
    assert pi.main(["--android", "brez-paketa"]) == 2
    assert pi.main(["--linux-deb", "x", "--rok", "0"]) == 2


def test_ukazna_vrstica_sigterm_pospravi(okolje, tmp_path):
    # Pravi podproces ovoja: SIGTERM med preizkusom -> procesi pospravljeni, porocilo zapisano, izhod 130.
    env = dict(os.environ, FAKE_ANDROID="spi")
    p = subprocess.Popen([PY, str(_POT), "--repo", str(okolje.repo), "--izhod", str(okolje.izhod),
                          "--android", "R58M=si.safeer.os:%s" % okolje.apk], env=env,
                         stdout=subprocess.PIPE, text=True)
    pidi = tmp_path / "pidi"
    for _ in range(100):
        if pidi.exists() and pidi.read_text():
            break
        time.sleep(0.1)
    p.send_signal(signal.SIGTERM)
    out, _ = p.communicate(timeout=30)
    assert p.returncode == 130
    assert "prekinjeno" in out
    otrok, vnuk = map(int, pidi.read_text().split())
    time.sleep(0.3)
    assert not pi._zivi(otrok) and not pi._zivi(vnuk)
    assert okolje.json()["napake"] >= 1


def test_relativne_poti_repo_in_apk(okolje, capsys, monkeypatch):
    # Podprocesi tecejo v repo; relativni --repo in APK morata kljub temu delovati.
    monkeypatch.chdir(okolje.pot)
    koda = pi.main(["--repo", "repo", "--izhod", "rel.json", "--linux-deb", "debi", "--android", "R58M=si.safeer.os:app.apk"])
    assert koda == 0, capsys.readouterr().out
    assert okolje.dnevnik("android") == ["R58M=si.safeer.os --apk %s" % okolje.apk]
    assert json.loads((okolje.pot / "rel.json").read_text())["napake"] == 0

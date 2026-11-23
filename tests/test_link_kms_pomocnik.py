"""Preizkusi pomocnika KMS (core/link_kms_pomocnik.py) brez ffmpeg, DRM, systemd in logind.

loginctl je namisljen (skripta v tmp_path, ki belezi klice), ffmpeg nadomesca /bin/sleep,
povezava je socketpair ali pravi Unix vticnik (SO_PEERCRED vrne nas uid).
Pozeni iz korena projekta: python3 -m pytest -q tests/test_link_kms_pomocnik.py
"""

from __future__ import annotations

import errno
import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

KOREN = Path(__file__).resolve().parent.parent
POMOCNIK = KOREN / "core" / "link_kms_pomocnik.py"
UID = os.getuid()
TUJI_UID = UID + 4242
VELJAVNA = {"w": 1920, "h": 1080, "fps": 60, "kodek": "h264", "qp": 20}

NAMISLJENI_LOGINCTL = """\
#!{python}
import json, sys, time
from pathlib import Path
mapa = Path(__file__).resolve().parent
nastavitve = json.loads((mapa / "seja.json").read_text())
with open(mapa / "klici.log", "a") as dnevnik:
    dnevnik.write(" ".join(sys.argv[1:]) + "\\n")
time.sleep(nastavitve.get("zamik", 0))
argumenti = sys.argv[1:]
lastnosti = [argumenti[i + 1] for i, a in enumerate(argumenti) if a == "-p"]
vrednosti = {{"ActiveSession": "c1", "User": str(nastavitve["uid"]), "Type": nastavitve["tip"]}}
for ime in lastnosti:
    print(vrednosti[ime] if "--value" in argumenti else "%s=%s" % (ime, vrednosti[ime]))
"""


def namisljeni_loginctl(mapa: Path, uid: int = UID, tip: str = "x11", zamik: float = 0) -> Path:
    (mapa / "seja.json").write_text(json.dumps({"uid": uid, "tip": tip, "zamik": zamik}))
    skripta = mapa / "loginctl"
    skripta.write_text(NAMISLJENI_LOGINCTL.format(python=sys.executable))
    skripta.chmod(0o755)
    return skripta


def stevilo_klicev(mapa: Path) -> int:
    dnevnik = mapa / "klici.log"
    return len(dnevnik.read_text().splitlines()) if dnevnik.exists() else 0


@pytest.fixture
def pomocnik(tmp_path, monkeypatch):
    """Svez modul (brez stanja prejsnjih preizkusov) z namisljenim loginctl in ffmpeg."""
    spec = importlib.util.spec_from_file_location("kms_pomocnik_%d" % time.monotonic_ns(), POMOCNIK)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    modul.LOGINCTL = str(namisljeni_loginctl(tmp_path))
    modul.ukaz_kms = lambda z, kartica, ffmpeg=None: ["/bin/sleep", "30"]
    modul._kartica = lambda: "/dev/dri/card0"
    zagnani = []
    pravi_popen = subprocess.Popen

    def popen(*a, **k):
        p = pravi_popen(*a, **k)
        if a and a[0] and a[0][0] == "/bin/sleep":
            zagnani.append(p)
        return p

    monkeypatch.setattr(modul.subprocess, "Popen", popen)
    modul.zagnani = zagnani
    yield modul
    for p in zagnani:
        if p.poll() is None:
            p.kill()
            p.wait()


class Klic:
    """En klicatelj: socketpair, pomocnik obdeluje v svoji niti."""

    def __init__(self, modul, zahteva=None, uid: int = UID) -> None:
        self.nas, pomocnikov = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.nas.settimeout(5)
        self.uid = uid
        if zahteva is not None:
            self.poslji(zahteva)
        izvirni = modul._klicatelj
        klicatelj = (lambda s: (os.getpid(), uid, 0)) if uid != UID else izvirni
        self.nit = threading.Thread(target=self._obdelaj, args=(modul, pomocnikov, klicatelj),
                                    daemon=True)
        self.nit.start()

    @staticmethod
    def _obdelaj(modul, povezava, klicatelj) -> None:
        # _klicatelj zamenjamo samo za to povezavo (tuji uid), ne za ves modul.
        if klicatelj is not modul._klicatelj:
            izvirni = modul._klicatelj
            modul._klicatelj = lambda s: klicatelj(s) if s is povezava else izvirni(s)
        modul.obdelaj(povezava)

    def poslji(self, zahteva) -> None:
        besedilo = zahteva if isinstance(zahteva, str) else json.dumps(zahteva)
        self.nas.sendall(besedilo.encode("utf-8") + b"\n")

    def odgovor(self):
        sporocilo, fds, _, _ = socket.recv_fds(self.nas, 256, 1)
        for fd in fds:
            os.close(fd)
        return sporocilo.decode("utf-8", "replace").strip(), len(fds)

    def zapri(self) -> None:
        self.nas.close()
        self.nit.join(5)


# --- kontrola: veljaven zajem na X11 uspe (brez in s popravkom) ---------------------------

def test_kontrola_x11_zajem_uspe(pomocnik):
    klic = Klic(pomocnik, VELJAVNA)
    assert klic.odgovor() == ("ok", 1)
    assert len(pomocnik.zagnani) == 1
    klic.zapri()
    assert pomocnik.zagnani[0].poll() is not None  # pomocnik je "ffmpeg" ustavil


# --- K1: na Waylandu (ali neznani seji) KMS zavrne, klicatelj dobi napako brez "ok" -------

@pytest.mark.parametrize("tip", ["wayland", "tty", ""])
def test_k1_seja_ni_x11_zavrnjena(pomocnik, tmp_path, tip):
    namisljeni_loginctl(tmp_path, tip=tip)
    klic = Klic(pomocnik, VELJAVNA)
    besedilo, fds = klic.odgovor()
    klic.zapri()
    assert fds == 0 and besedilo.startswith("napaka:"), besedilo
    assert "kms samo x11" in besedilo
    assert pomocnik.zagnani == []


# --- K2: tuj uid ne zaganja loginctl; prepogoste poizvedbe; najvec 4 hkratne povezave ----

def test_k2_tuj_uid_ne_zaganja_loginctl_ob_svezem_lastniku(pomocnik, tmp_path):
    klic = Klic(pomocnik, VELJAVNA)
    assert klic.odgovor()[0] == "ok"
    klic.zapri()
    pred = stevilo_klicev(tmp_path)
    for _ in range(10):
        tuji = Klic(pomocnik, VELJAVNA, uid=TUJI_UID)
        assert tuji.odgovor()[0].startswith("napaka:")
        tuji.zapri()
    assert stevilo_klicev(tmp_path) == pred


def test_k2_prepogost_uid_zavrnjen_pred_loginctl(pomocnik, tmp_path, monkeypatch):
    # Predpomnilnik izklopljen: vsaka povezava bi sicer zagnala loginctl.
    monkeypatch.setattr(pomocnik, "PREDPOMNILNIK_SEJE_S", 0.0, raising=False)
    for _ in range(10):
        tuji = Klic(pomocnik, VELJAVNA, uid=TUJI_UID)
        assert tuji.odgovor()[0].startswith("napaka:")
        tuji.zapri()
    # Najvec ena poizvedba (show-seat + show-session) v PREMOR_ZAGONA_S za ta uid.
    assert stevilo_klicev(tmp_path) <= 2


ZAGON_GLAVNE = """\
import os, socket, sys
sys.path.insert(0, {koren!r})
import importlib.util
spec = importlib.util.spec_from_file_location("kms_pomocnik", {pomocnik!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.LOGINCTL = {loginctl!r}
m.ukaz_kms = lambda z, kartica, ffmpeg=None: ["/bin/sleep", "30"]
m._kartica = lambda: "/dev/dri/card0"
os.dup2(int(sys.argv[1]), 3)
os.environ["LISTEN_FDS"] = "1"
os.environ["LISTEN_PID"] = str(os.getpid())
sys.exit(m.main())
"""


def test_k2_najvec_stiri_hkratne_povezave(tmp_path):
    """Pravi main() s socket activation (fd 3): 8 hkratnih praznih povezav."""
    loginctl = namisljeni_loginctl(tmp_path)
    pot = str(tmp_path / "kms.sock")
    posluh = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    posluh.bind(pot)
    posluh.listen(16)
    skripta = tmp_path / "zagon.py"
    skripta.write_text(ZAGON_GLAVNE.format(koren=str(KOREN), pomocnik=str(POMOCNIK),
                                           loginctl=str(loginctl)))
    proces = subprocess.Popen([sys.executable, str(skripta), str(posluh.fileno())],
                              pass_fds=[posluh.fileno()])
    posluh.close()
    povezave = []
    try:
        for _ in range(8):
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(6)
            s.connect(pot)
            povezave.append(s)  # nic ne posljemo: pomocnik caka zahtevo (do 2 s)
        odgovori = []
        for s in povezave:
            try:
                odgovori.append(s.recv(256).decode("utf-8", "replace").strip())
            except socket.timeout:
                odgovori.append("")
        zasedeno = sum(1 for o in odgovori if o == "napaka: zasedeno")
        assert zasedeno >= 4, odgovori
    finally:
        for s in povezave:
            s.close()
        proces.kill()
        proces.wait()


# --- K3: neveljavna zahteva ne porabi premora pravemu uporabniku ---------------------------

def test_k3_neveljavna_zahteva_ne_porabi_premora(pomocnik):
    slaba = Klic(pomocnik, dict(VELJAVNA, w=1921))
    assert slaba.odgovor() == ("napaka: zahteva", 0)
    slaba.zapri()
    dobra = Klic(pomocnik, VELJAVNA)  # takoj, znotraj PREMOR_ZAGONA_S
    assert dobra.odgovor() == ("ok", 1)
    dobra.zapri()


# --- K4: "zajem ze tece" in rezervacija v istem zaklepu ------------------------------------

def test_k4_dva_hkratna_zajema_ne_zazeneta_dveh_ffmpeg(pomocnik, monkeypatch):
    monkeypatch.setattr(pomocnik, "PREMOR_ZAGONA_S", 0.0)  # premor ne sme skriti dirke
    prvi = Klic(pomocnik)  # poveze se, zahtevo poslje sele cez cas
    time.sleep(0.5)  # prvi je mimo preverb in bere zahtevo
    drugi = Klic(pomocnik, VELJAVNA)
    odgovor_drugega = drugi.odgovor()
    prvi.poslji(VELJAVNA)
    odgovor_prvega = prvi.odgovor()
    zagnanih = sum(1 for p in pomocnik.zagnani if p.poll() is None)
    prvi.zapri()
    drugi.zapri()
    assert [odgovor_prvega[0], odgovor_drugega[0]].count("ok") == 1, (odgovor_prvega, odgovor_drugega)
    assert zagnanih == 1


# --- KMS-1: menjava lastnika ali tipa seje med zajemom ustavi ffmpeg na strani pomocnika -----

@pytest.mark.parametrize("uid_po, tip_po", [(TUJI_UID, "x11"), (UID, "wayland"), (UID, "")])
def test_kms1_menjava_seje_med_zajemom_ustavi_zajem(pomocnik, tmp_path, monkeypatch, uid_po, tip_po):
    monkeypatch.setattr(pomocnik, "PREDPOMNILNIK_SEJE_S", 0.0)
    klic = Klic(pomocnik, VELJAVNA)
    assert klic.odgovor() == ("ok", 1)
    namisljeni_loginctl(tmp_path, uid=uid_po, tip=tip_po)   # drug uporabnik / Wayland na zaslonu
    klic.nas.settimeout(6)
    # Klicatelj vticnik namenoma pusti odprt (napadalec): pomocnik mora sam ustaviti zajem.
    assert klic.nas.recv(64) == b""
    assert pomocnik.zagnani[0].wait(timeout=5) is not None
    klic.zapri()


def test_kms1_ista_seja_zajem_tece_naprej(pomocnik, monkeypatch):
    # Kontrola: preverba seje med zajemom ne sme ustaviti zajema lastnika aktivne seje X11.
    monkeypatch.setattr(pomocnik, "PREDPOMNILNIK_SEJE_S", 0.0)
    klic = Klic(pomocnik, VELJAVNA)
    assert klic.odgovor() == ("ok", 1)
    time.sleep(2.5)                                         # vsaj dve preverbi seje
    assert pomocnik.zagnani[0].poll() is None
    klic.zapri()
    assert pomocnik.zagnani[0].poll() is not None


# --- KMS-3: utrditev enote systemd ----------------------------------------------------------

def test_kms3_enota_utrjena_brez_korena():
    nastavitve = {}
    besedilo = (KOREN / "packaging" / "systemd" / "safeer-kms.service").read_text()
    for vrstica in besedilo.splitlines():
        vrstica = vrstica.strip()
        if vrstica and not vrstica.startswith(("#", "[")) and "=" in vrstica:
            kljuc, _, vrednost = vrstica.partition("=")
            nastavitve.setdefault(kljuc, []).append(vrednost)
    for kljuc, vrednost in (("ProtectHostname", "yes"), ("ProtectClock", "yes"),
                            ("ProtectProc", "invisible"), ("PrivateIPC", "yes")):
        assert nastavitve.get(kljuc) == [vrednost], kljuc
    zaprti = set()
    for filter_ in nastavitve["SystemCallFilter"]:
        assert filter_.startswith("~")                      # samo prepovedi: zdruzijo se
        zaprti |= set(filter_[1:].split())
    assert {"bpf", "fanotify_init", "quotactl", "sethostname", "setdomainname", "keyctl", "add_key",
            "request_key", "@mount", "@module"} <= zaprti
    # Koren samo v ozki enoti: brez User=, DynamicUser in samo CAP_SYS_ADMIN.
    assert "User" not in nastavitve and nastavitve["DynamicUser"] == ["yes"]
    assert nastavitve["AmbientCapabilities"] == nastavitve["CapabilityBoundingSet"] == ["CAP_SYS_ADMIN"]


# --- KMS-4: rok velja za celo zahtevo, ne za posamezen recv -----------------------------------

def test_kms4_pocasna_zahteva_zavrnjena_v_roku(pomocnik, monkeypatch):
    monkeypatch.setattr(pomocnik, "ROK_ZAHTEVE_S", 0.5)
    klic = Klic(pomocnik)
    zacetek = time.monotonic()
    for znak in '{"w": 1920':                               # po en bajt na 0.1 s, nikoli "\n"
        try:
            klic.nas.sendall(znak.encode())
        except OSError:
            break
        time.sleep(0.1)
    klic.nit.join(3)
    assert not klic.nit.is_alive()
    assert time.monotonic() - zacetek < 2.0
    assert pomocnik.zagnani == []
    klic.zapri()


# --- KMS-5: zavrnitve tujega uid ne polnijo dnevnika s hitrostjo povezovanja -------------------

def test_kms5_zavrnitve_v_dnevniku_redcene(pomocnik, capsys):
    klic = Klic(pomocnik, VELJAVNA)
    assert klic.odgovor()[0] == "ok"
    klic.zapri()
    capsys.readouterr()
    for _ in range(10):
        tuji = Klic(pomocnik, VELJAVNA, uid=TUJI_UID)
        assert tuji.odgovor()[0].startswith("napaka:")
        tuji.zapri()
    assert capsys.readouterr().out.count("kms: zavrnjeno") == 1


# --- KMS-6: napaka accept() ne konca storitve; po kill() ni zombija ----------------------------

def test_kms6_prehodna_napaka_accept_ne_konca_zanke(pomocnik):
    class Konec(BaseException):
        pass

    klici = []

    class Posluh:
        def accept(self):
            klici.append(1)
            if len(klici) == 1:
                raise OSError(errno.EMFILE, "Too many open files")
            raise Konec()                                   # konec preizkusa, ne napaka storitve

    with pytest.raises(Konec):
        pomocnik._sprejemaj(Posluh())
    assert len(klici) == 2


def test_kms6_po_kill_ni_zombija(pomocnik, tmp_path, monkeypatch):
    # "ffmpeg", ki prezre SIGTERM: pomocnik ga po 3 s ubije s SIGKILL in mora pobrati.
    trmast = tmp_path / "trmast"
    trmast.write_text("#!/bin/sh\ntrap '' TERM\nexec /bin/sleep 30\n")
    trmast.chmod(0o755)
    pomocnik.ukaz_kms = lambda z, kartica, ffmpeg=None: [str(trmast)]
    zagnani = []
    prejsnji = pomocnik.subprocess.Popen

    def popen(*a, **k):
        p = prejsnji(*a, **k)
        if a and a[0] and a[0][0] == str(trmast):
            zagnani.append(p)
        return p

    monkeypatch.setattr(pomocnik.subprocess, "Popen", popen)
    klic = Klic(pomocnik, VELJAVNA)
    assert klic.odgovor() == ("ok", 1)
    time.sleep(0.3)                                         # sh nastavi trap in izvede exec
    klic.nas.close()
    klic.nit.join(10)
    assert not klic.nit.is_alive()
    assert zagnani[0].returncode == -signal.SIGKILL         # brez wait() bi ostal None (zombi)

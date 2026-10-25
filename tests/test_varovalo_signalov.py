"""Varovalo signalov (tests/varovalo_signalov.py): potomec dovoljen, tuj proces zavrnjen, signal ne odide."""
import os
import signal
import subprocess
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from varovalo_signalov import PRAVI_KILL, KrsitevSignala, Varovalo  # noqa: E402


@pytest.fixture
def varovalo(tmp_path):
    v = Varovalo(dnevnik=str(tmp_path / "krsitve.log"))
    v.namesti()
    yield v
    v.odstrani()


def _tuj_proces():
    """Proces, ki ni potomec: lupina ga zazene v ozadju in konca, tako da ga posvoji init (ali podpornik)."""
    # setsid: tujec je vodja svoje skupine (kill -<pid> zadene tujo skupino)
    p = subprocess.run(["sh", "-c", "setsid sleep 60 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True)
    pid = int(p.stdout.strip())
    _cakaj_exec(pid)
    rok = time.monotonic() + 5
    while Varovalo().potomec(pid) and time.monotonic() < rok:
        time.sleep(0.02)
    assert not Varovalo().potomec(pid), "tujec je se potomec (lupina se ni koncala)"
    return pid


def _cakaj_exec(pid, ime="sleep"):
    """Popen se vrne pred exec: do takrat je ime otroka se python (pkill ga ne bi nasel)."""
    rok = time.monotonic() + 5
    while time.monotonic() < rok:
        try:
            with open("/proc/%d/comm" % pid, encoding="utf-8") as f:
                if f.read().strip() == ime:
                    return
        except OSError:
            return
        time.sleep(0.01)


def _ziv(pid):
    """Tece (zombi, ki caka na init vsebnika, ne steje)."""
    try:
        with open("/proc/%d/stat" % pid, encoding="utf-8", errors="replace") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return False


def _pospravi(pid):
    """Pospravljanje preizkusa: tujca je zagnal preizkus sam, zato pravi os.kill mimo VSEH namescenih varoval
    (subprocess /bin/kill bi varovalo zavrnilo in `sleep 60` bi ostal - pregled 22. 10. 2026)."""
    try:
        PRAVI_KILL(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    rok = time.monotonic() + 5
    while _ziv(pid) and time.monotonic() < rok:
        time.sleep(0.02)


@pytest.fixture
def tujec():
    pid = _tuj_proces()
    yield pid
    _pospravi(pid)
    assert not _ziv(pid), "tujec %d ni pospravljen" % pid


def test_pospravljanje_res_ubije_tujca(varovalo):
    """Brez PRAVI_KILL je pospravljanje slo skozi varovalo (zavrnjeno, izjema pogoltnjena) in tujec je zivel 60 s."""
    pid = _tuj_proces()
    try:
        assert _ziv(pid)
        _pospravi(pid)
        assert not _ziv(pid)
        assert not varovalo.krsitve
    finally:
        if _ziv(pid):
            PRAVI_KILL(pid, signal.SIGKILL)


def test_pravi_kill_ni_ovit(varovalo):
    assert PRAVI_KILL is not os.kill
    assert getattr(PRAVI_KILL, "__module__", "") in ("posix", "nt")      # vgrajena funkcija, ne ovoj


def test_otrok_dovoljen(varovalo):
    otrok = subprocess.Popen(["sleep", "60"])
    try:
        assert varovalo.potomec(otrok.pid)
        os.kill(otrok.pid, signal.SIGTERM)
        assert otrok.wait(5) == -signal.SIGTERM
        assert not varovalo.krsitve
    finally:
        if otrok.poll() is None:
            otrok.kill()
            otrok.wait()


def test_vnuk_dovoljen(varovalo):
    otrok = subprocess.Popen(["sh", "-c", "sleep 60 & echo $!; wait"], stdout=subprocess.PIPE, text=True)
    try:
        vnuk = int(otrok.stdout.readline())
        assert varovalo.potomec(vnuk)
        os.kill(vnuk, signal.SIGTERM)
    finally:
        otrok.kill()
        otrok.wait()
        otrok.stdout.close()


def test_tuj_proces_zavrnjen_in_signal_ne_odide(varovalo, tujec):
    assert not varovalo.potomec(tujec)
    with pytest.raises(KrsitevSignala):
        os.kill(tujec, signal.SIGTERM)
    assert os.path.exists("/proc/%d" % tujec)           # signal ni odsel
    log = open(varovalo.dnevnik, encoding="utf-8").read()
    assert "test_tuj_proces_zavrnjen" in log and "sleep" in log   # preizkus in /proc/<pid>/comm cilja
    assert len(varovalo.krsitve) == 1


def test_signal_0_dovoljen(varovalo, tujec):
    os.kill(tujec, 0)
    os.kill(os.getpid(), 0)
    assert not varovalo.krsitve


def test_init_in_lastna_skupina_zavrnjena(varovalo):
    with pytest.raises(KrsitevSignala):
        os.kill(1, signal.SIGTERM)
    with pytest.raises(KrsitevSignala):
        os.killpg(os.getpgrp(), signal.SIGTERM)   # skupina vsebuje tudi starsa preizkusov


def test_skupina_otroka_dovoljena(varovalo):
    otrok = subprocess.Popen(["sleep", "60"], start_new_session=True)
    try:
        os.killpg(otrok.pid, signal.SIGTERM)
        otrok.wait(5)
    finally:
        if otrok.poll() is None:
            otrok.kill()
            otrok.wait()


ZAVRNJENI = [
    ["kill", "{pid}"], ["kill", "-9", "{pid}"], ["kill", "-s", "KILL", "{pid}"], ["kill", "-9", "-{pid}"],
    ["kill", "--", "-{pid}"],
    "kill -TERM {pid}", "echo a; kill {pid}", "echo a\nkill {pid}", "true && kill {pid}", "false || kill {pid}",
    "(kill {pid})", "{{ kill {pid}; }}", "if true; then kill {pid}; fi", "echo `kill {pid}`", "echo $(kill {pid})",
    "kill {pid} 2>/dev/null", "sleep 0 & kill {pid}",
    # niz za lupino
    ["sh", "-c", "kill {pid}"], ["bash", "-c", "echo a | kill -9 {pid}"], ["dash", "-ec", "true; kill {pid}"],
    ["bash", "--norc", "-c", "kill {pid}", "ime"], ["sh", "-c", "sh -c 'kill {pid}'"],
    # ovoji (env, xargs, setsid, nohup, timeout ...)
    ["env", "A=1", "kill", "{pid}"], ["env", "-i", "-u", "X", "kill", "{pid}"], ["setsid", "-f", "kill", "{pid}"],
    ["nohup", "kill", "{pid}"], ["timeout", "5", "kill", "{pid}"], ["timeout", "-s", "KILL", "5", "kill", "{pid}"],
    ["nice", "-n", "5", "kill", "{pid}"], ["stdbuf", "-oL", "kill", "{pid}"], ["/usr/bin/env", "/bin/kill", "{pid}"],
    ["env", "-S", "kill {pid}"], ["timeout", "5", "sh", "-c", "kill {pid}"],
    "env A=1 setsid nohup timeout 5 kill {pid}", "A=1 kill {pid}", "exec kill {pid}", "command kill {pid}",
    # cilji s standardnega vhoda ali iz spremenljivke
    "pgrep sleep | xargs kill", "echo {pid} | xargs -n1 kill -9", ["xargs", "kill"], "kill $PID", "kill %1",
    # pkill/killall v nizu za lupino s tujim istoimenskim procesom (prepisa niza ne delamo)
    "pkill -x sleep", "killall sleep", ["sh", "-c", "pkill sleep"],
    # pkill z izbirami, ki jih prepis ne zna posnemati
    ["pkill", "-u", "0", "sleep"], ["pkill", "-P", "1", "sleep"],
]


@pytest.mark.parametrize("ukaz", ZAVRNJENI)
def test_ukazi_kill_zavrnjeni(varovalo, tujec, ukaz):
    if isinstance(ukaz, str):
        ukaz = ukaz.format(pid=tujec)
    else:
        ukaz = [a.format(pid=tujec) for a in ukaz]
    with pytest.raises(KrsitevSignala):
        subprocess.Popen(ukaz, shell=isinstance(ukaz, str))
    assert _ziv(tujec)


@pytest.mark.parametrize("ukaz", ["kill {pid}", "sh -c 'kill -9 {pid}'", "pgrep sleep | xargs kill"])
def test_os_system_zavrnjen(varovalo, tujec, ukaz):
    with pytest.raises(KrsitevSignala):
        os.system(ukaz.format(pid=tujec))
    assert _ziv(tujec)


def test_os_system_navaden_dovoljen(varovalo):
    assert os.system("true") == 0
    assert not varovalo.krsitve


@pytest.mark.parametrize("ukaz", [["pkill", "-x", "sleep"], ["pkill", "sleep"], ["killall", "sleep"],
                                  ["pkill", "-KILL", "-x", "sleep"], ["killall", "-s", "KILL", "sleep"],
                                  ["timeout", "5", "pkill", "-f", "^sleep 60"]])
def test_pkill_istoimenski_tujec_ne_zavrne_in_prezivi(varovalo, tujec, ukaz):
    """Naloga 48: pkill/killall isce cilje samo med potomci. Lastnikov istoimenski proces zakonitega preizkusa ne
    zavrne in ga pravi pkill NE zadene (ukaz se zamenja s kill potomcev)."""
    otrok = subprocess.Popen(["sleep", "60"])
    try:
        _cakaj_exec(otrok.pid)
        izid = subprocess.run(ukaz, timeout=10)
        assert izid.returncode == 0
        assert otrok.wait(5) in (-signal.SIGTERM, -signal.SIGKILL)
        assert _ziv(tujec), "pkill je zadel tujca"
        assert not varovalo.krsitve
    finally:
        if otrok.poll() is None:
            otrok.kill()
            otrok.wait()


def test_pkill_brez_nasega_zadetka(varovalo, tujec):
    """Samo tujec se ujema: kot pkill brez zadetka (koda 1), tujec zivi, ni krsitve."""
    assert subprocess.run(["pkill", "-x", "sleep"], timeout=10).returncode == 1
    assert _ziv(tujec)
    assert not varovalo.krsitve


def test_pkill_v_lupini_samo_potomci_dovoljen(varovalo):
    """Brez tujega istoimenskega procesa je pkill v nizu za lupino dovoljen (zadene samo potomce)."""
    otrok = subprocess.Popen(["bash", "-c", "exec -a safeer-varovalo-48 sleep 60"])
    try:
        time.sleep(0.2)
        subprocess.run("pkill -f safeer-varovalo-48", shell=True, timeout=10)
        otrok.wait(5)
        assert not varovalo.krsitve
    finally:
        if otrok.poll() is None:
            otrok.kill()
            otrok.wait()


@pytest.mark.parametrize("ukaz", ["kill {pid} 2>/dev/null", ["sh", "-c", "kill -9 {pid} >&2"],
                                  ["timeout", "5", "kill", "{pid}"], "env A=1 kill -s TERM {pid}"])
def test_ukazi_kill_otroka_dovoljeni(varovalo, ukaz):
    """Preusmeritev (2>) ni cilj kill (pid 2), ovoji ne zmedejo potomca."""
    otrok = subprocess.Popen(["sleep", "60"])
    try:
        if isinstance(ukaz, str):
            ukaz = ukaz.format(pid=otrok.pid)
        else:
            ukaz = [a.format(pid=otrok.pid) for a in ukaz]
        subprocess.run(ukaz, shell=isinstance(ukaz, str), timeout=10)
        assert otrok.wait(5) in (-signal.SIGTERM, -signal.SIGKILL)
        assert not varovalo.krsitve
    finally:
        if otrok.poll() is None:
            otrok.kill()
            otrok.wait()


def test_ukaz_kill_otroka_dovoljen(varovalo):
    otrok = subprocess.Popen(["sleep", "60"])
    try:
        subprocess.run(["kill", str(otrok.pid)], check=True)
        otrok.wait(5)
    finally:
        if otrok.poll() is None:
            otrok.kill()
            otrok.wait()


def test_ukaz_kill_signal_0_dovoljen(varovalo, tujec):
    subprocess.run(["kill", "-0", str(tujec)], check=True)


@pytest.mark.parametrize("ukaz", [["echo", "kill"], ["sh", "-c", "echo kill 1"], "echo 'kill 1'",
                                  ["kill", "-l"], ["xargs", "echo"], ["timeout", "5", "true"], ["env"],
                                  ["sh", "-c", "true"], ["bash", "-c", "x=kill; echo $x"]])
def test_navadni_ukazi_niso_ovirani(varovalo, ukaz):
    assert subprocess.run(ukaz, shell=isinstance(ukaz, str), capture_output=True, input=b"",
                          timeout=10).returncode == 0
    assert not varovalo.krsitve

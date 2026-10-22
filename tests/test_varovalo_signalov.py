"""Varovalo signalov (tests/varovalo_signalov.py): potomec dovoljen, tuj proces zavrnjen, signal ne odide."""
import os
import signal
import subprocess
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from varovalo_signalov import KrsitevSignala, Varovalo  # noqa: E402


@pytest.fixture
def varovalo(tmp_path):
    v = Varovalo(dnevnik=str(tmp_path / "krsitve.log"))
    v.namesti()
    yield v
    v.odstrani()


def _tuj_proces():
    """Proces, ki ni potomec: lupina ga zazene v ozadju in konca, tako da ga posvoji init (ali podpornik)."""
    p = subprocess.run(["sh", "-c", "sleep 60 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True)
    pid = int(p.stdout.strip())
    for _ in range(100):
        if not os.path.exists("/proc/%d/stat" % pid) or Varovalo().potomec(pid) is False:
            break
        time.sleep(0.02)
    return pid


@pytest.fixture
def tujec():
    pid = _tuj_proces()
    yield pid
    try:
        _prvotni_kill(pid)
    except OSError:
        pass


def _prvotni_kill(pid):
    # pospravljanje preizkusa: pravi kill mimo varovala (zagnali smo ga mi)
    subprocess.run(["/bin/kill", "-9", str(pid)], check=False, env={})


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


@pytest.mark.parametrize("ukaz", [
    ["kill", "{pid}"], ["kill", "-9", "{pid}"], ["pkill", "-x", "sleep"], ["killall", "sleep"],
    "kill -TERM {pid}", "echo a; kill {pid}",
])
def test_ukazi_kill_zavrnjeni(varovalo, tujec, ukaz):
    if isinstance(ukaz, str):
        ukaz = ukaz.format(pid=tujec)
    else:
        ukaz = [a.format(pid=tujec) for a in ukaz]
    with pytest.raises(KrsitevSignala):
        subprocess.Popen(ukaz, shell=isinstance(ukaz, str))
    assert os.path.exists("/proc/%d" % tujec)


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


def test_navadni_ukazi_niso_ovirani(varovalo):
    assert subprocess.run(["echo", "kill"], capture_output=True).returncode == 0

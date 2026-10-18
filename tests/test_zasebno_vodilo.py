"""Preizkusi govorijo samo z zasebnim vodilom seje (tests/conftest.py), nikoli s pravim Safeer Control/OS lastnika.

Lastnik 18. 10. 2026: tek preizkusov na prenosniku je prej namenoma uporabil pravo vodilo seje (/run/user/UID/bus) -
imena org.gtk.Application, dejanja in obvestila preizkusov so sla do programov, ki jih lastnik uporablja.
"""
import importlib.util
import os
import shutil
import subprocess

import pytest

# tests/conftest.py po poti (ime »conftest« ima tudi korenski conftest.py - uvoz po imenu bi bil odvisen od sys.path).
_spec = importlib.util.spec_from_file_location("safeer_preizkusi_conftest",
                                               os.path.join(os.path.dirname(os.path.abspath(__file__)), "conftest.py"))
nastavitev_preizkusov = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nastavitev_preizkusov)


def _pravo_vodilo() -> str:
    return "unix:path=" + os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid(), "bus")


def test_tek_ima_zasebno_vodilo_seje():
    naslov = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    assert naslov, "naslov vodila mora biti nastavljen (sicer GLib poskusi dbus-launch in obvisi)"
    assert naslov != _pravo_vodilo()
    assert "/run/user/" not in naslov


@pytest.mark.skipif(not shutil.which("dbus-daemon") or not shutil.which("gdbus"), reason="ni dbus-daemon ali gdbus")
def test_zasebno_vodilo_deluje_in_se_ustavi():
    naslov, proces, mapa = nastavitev_preizkusov.zasebno_vodilo()
    try:
        assert proces is not None and proces.poll() is None
        okolje = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=naslov)
        r = subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path",
                            "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListActivatableNames"],
                           capture_output=True, text=True, timeout=20, env=okolje)
        assert r.returncode == 0, r.stderr
        # Brez storitvenih map: na zasebnem vodilu se ne zazene noben program sam (po teku ne ostane nic).
        assert r.stdout.strip() in ("(['org.freedesktop.DBus'],)",), r.stdout
    finally:
        proces.terminate()
        proces.wait(timeout=10)
        proces.stdout.close()
        shutil.rmtree(mapa, ignore_errors=True)
    assert proces.poll() is not None


def test_pre_push_testi_uporabijo_isti_conftest():
    """tools/pre_push_testi.sh poganja pytest nad tests/ (conftest z zasebnim vodilom) in ne nastavi pravega vodila."""
    koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(koren, "tools", "pre_push_testi.sh"), encoding="utf-8") as d:
        besedilo = d.read()
    assert "pytest" in besedilo and "tests/" in besedilo
    assert "DBUS_SESSION_BUS_ADDRESS=" not in besedilo
    assert "/run/user/" not in besedilo

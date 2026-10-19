"""Preizkusi govorijo samo z zasebnim vodilom seje (tests/conftest.py), nikoli s pravim Safeer Control/OS lastnika.

Lastnik 18. 10. 2026: tek preizkusov na prenosniku je prej namenoma uporabil pravo vodilo seje (/run/user/UID/bus) -
imena org.gtk.Application, dejanja in obvestila preizkusov so sla do programov, ki jih lastnik uporablja.
"""
import os
import re
import shutil
import subprocess

import pytest


def _pravo_vodilo() -> str:
    return "unix:path=" + os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid(), "bus")


def test_tek_ima_zasebno_vodilo_seje():
    naslov = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    assert naslov, "naslov vodila mora biti nastavljen (sicer GLib poskusi dbus-launch in obvisi)"
    assert naslov != _pravo_vodilo()
    assert "/run/user/" not in naslov


@pytest.mark.skipif(not shutil.which("dbus-daemon") or not shutil.which("gdbus"), reason="ni dbus-daemon ali gdbus")
def test_zasebno_vodilo_deluje_in_se_ustavi():
    from zasebno_vodilo import ZasebnoVodilo
    okolje_prej = dict(os.environ)
    with ZasebnoVodilo() as vodilo:
        proces = vodilo._proces
        assert proces is not None and proces.poll() is None and vodilo.naslov
        r = subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path",
                            "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListActivatableNames"],
                           capture_output=True, text=True, timeout=20, env=vodilo.okolje())
        assert r.returncode == 0, r.stderr
        # Brez storitvenih map: na zasebnem vodilu se ne zazene noben program sam (po teku ne ostane nic).
        assert r.stdout.strip() in ("(['org.freedesktop.DBus'],)",), r.stdout
        # Okolja procesa vodilo ne spreminja (setenv med getenv druge niti: segfault, tests/zasebno_vodilo.py).
        assert dict(os.environ) == okolje_prej
    assert proces.poll() is not None and not os.path.exists(vodilo.mapa)
    assert dict(os.environ) == okolje_prej


def test_noben_preizkus_ne_uporablja_gio_testdbus():
    """Gio.TestDBus.up()/down() spreminja okolje procesa (g_setenv/g_unsetenv), med tem ko niti drugih preizkusov
    okolje berejo: polni tek se je 19. 10. 2026 sesul v test_obvestila.setUp. Zasebno vodilo: tests/zasebno_vodilo.py."""
    mapa = os.path.dirname(os.path.abspath(__file__))
    tujci = []
    for ime in sorted(os.listdir(mapa)):
        if ime.endswith(".py") and ime != os.path.basename(__file__):
            with open(os.path.join(mapa, ime), encoding="utf-8") as d:
                if re.search(r"TestDBus\s*\.\s*new\b", d.read()):
                    tujci.append(ime)
    assert tujci == []


def test_pre_push_testi_uporabijo_isti_conftest():
    """tools/pre_push_testi.sh poganja pytest nad tests/ (conftest z zasebnim vodilom) in ne nastavi pravega vodila."""
    koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(koren, "tools", "pre_push_testi.sh"), encoding="utf-8") as d:
        besedilo = d.read()
    assert "pytest" in besedilo and "tests/" in besedilo
    assert "DBUS_SESSION_BUS_ADDRESS=" not in besedilo
    assert "/run/user/" not in besedilo

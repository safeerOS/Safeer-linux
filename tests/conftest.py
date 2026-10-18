"""Skupne nastavitve preizkusov.

Dostop naprav (core/link_dostop): zapis dovoljenj je v preizkusih VEDNO v zacasni datoteki - nikoli v pravih nastavitvah
uporabnika. Obstojeci preizkusi preverjajo druge stvari (usmerjanje, prenos datotek, predajo) z izmisljenimi napravami,
zato so te v njih v ozjem krogu racunalnika. Preizkus, ki preverja sama dovoljenja, se oznaci s
`@pytest.mark.pravi_dostop` in dobi prava pravila nad praznim zacasnim zapisom.
"""
import gc
import os
import shutil
import signal
import subprocess
import sys
import tempfile

import pytest

_izid = {}
_VODILO = "DBUS_SESSION_BUS_ADDRESS"

#: Nastavitev zasebnega vodila: brez storitvenih map (nic se ne zazene samo ob klicu imena, zato po teku ne ostane
#: noben proces), dovoljeno vse - enako kot Gio.TestDBus.
_NASTAVITEV_VODILA = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=%s</listen>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def _umri_s_starsem() -> None:
    """V otroku pred exec: ce pytest umre (tudi SIGKILL), jedro vodilu poslje SIGTERM - nic ne ostane teci."""
    try:
        import ctypes
        ctypes.CDLL(None, use_errno=True).prctl(1, int(signal.SIGTERM))   # PR_SET_PDEATHSIG
    except Exception:  # noqa: BLE001 - brez prctl vodilo pocisti pytest_unconfigure
        pass


def zasebno_vodilo() -> tuple:
    """Zazene zasebno vodilo seje za ves tek. Vrne (naslov, proces, mapa); proces je None, ce dbus-daemon ni.

    Lastnik 18. 10. 2026: tek preizkusov na prenosniku ne sme govoriti z njegovim pravim Safeer Control/OS (imena
    org.gtk.Application, dejanja, obvestila). Prej je conftest preizkuse namenoma povezal s pravim vodilom seje
    (/run/user/UID/bus). Brez dbus-daemon dobi tek naslov, ki ne vodi nikamor - nikoli pravega vodila."""
    mapa = tempfile.mkdtemp(prefix="safeer-vodilo-")
    program = shutil.which("dbus-daemon")
    if not program:
        return "unix:path=" + os.path.join(mapa, "ni-vodila"), None, mapa
    nastavitev = os.path.join(mapa, "vodilo.conf")
    with open(nastavitev, "w", encoding="utf-8") as d:
        d.write(_NASTAVITEV_VODILA % mapa)
    proces = subprocess.Popen([program, "--config-file=" + nastavitev, "--nofork", "--nopidfile", "--print-address=1"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                              preexec_fn=_umri_s_starsem)
    naslov = (proces.stdout.readline() or "").strip()
    if not naslov:
        proces.kill()
        proces.wait(timeout=5)
        return "unix:path=" + os.path.join(mapa, "ni-vodila"), None, mapa
    return naslov, proces, mapa


def ustavi_vodilo() -> None:
    proces, mapa = _izid.pop("vodilo_proces", None), _izid.pop("vodilo_mapa", None)
    if proces is not None:
        proces.terminate()
        try:
            proces.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proces.kill()
            proces.wait(timeout=5)
        if proces.stdout is not None:
            proces.stdout.close()
    if mapa:
        shutil.rmtree(mapa, ignore_errors=True)


def pytest_configure(config):
    config.addinivalue_line("markers", "pravi_dostop: preizkus s pravimi pravili dostopa naprav (core/link_dostop)")
    # Vsi preizkusi tecejo v enem procesu (GTK4 + WebKit, 18. 10. 2026). Samodejno zbiranje smeti bi lahko v delovni
    # niti (npr. doh_proxy._accept_loop) unicilo predmet GTK/WebKit - GObject sme koncati samo glavna nit, sicer
    # segfault (izmerjeno pri polnem teku). Zato smeti pobiramo sami, na glavni niti, po vsakem preizkusu.
    gc.disable()
    # Vodilo seje: zasebno za ves tek (glej zasebno_vodilo). Naslov mora biti nastavljen: brez njega in brez
    # XDG_RUNTIME_DIR GLib poskusi `dbus-launch --autolaunch` na zaslonu xvfb, ki obvisi in drzi zaklep vodila - vsi
    # Gio.bus_get_sync (tudi glavna nit) so cakali (gdb, 18. 10. 2026).
    _izid["vodilo_prej"] = os.environ.get(_VODILO)
    naslov, proces, mapa = zasebno_vodilo()
    _izid.update(vodilo_proces=proces, vodilo_mapa=mapa)
    os.environ[_VODILO] = naslov
    _izid["vodilo"] = naslov


@pytest.fixture(autouse=True)
def _smeti_na_glavni_niti():
    yield
    gc.collect()
    # Gio.TestDBus.down() (test_obvestila, test_pladenj_sni) naslov vodila seje izbrise (g_unsetenv), ne vrne prejsnjega.
    if _izid.get("vodilo"):
        os.environ[_VODILO] = _izid["vodilo"]


def pytest_sessionfinish(session, exitstatus):
    _izid["koda"] = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    # Po porocilu in pospravljanju (korenski conftest pobrise zacasno mapo) proces koncamo brez Py_Finalize: tam je
    # sprostitev predmeta GObject iz globalne spremenljivke modula (g_object_unref v _PyModule_Clear) obvisela na
    # futexu - polni tek je izpisal porocilo in nato visel do casovne omejitve (gdb na posnetku jedra, 18. 10. 2026).
    # Zasebno vodilo ustavimo po PID (in mapo pobrisemo), preden se proces konca.
    ustavi_vodilo()
    prej = _izid.pop("vodilo_prej", None)
    if prej is None:
        os.environ.pop(_VODILO, None)
    else:
        os.environ[_VODILO] = prej
    if "koda" in _izid:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_izid["koda"])


@pytest.fixture(autouse=True)
def _dostop_naprav(tmp_path, monkeypatch, request):
    from core import link_dostop
    link_dostop._za_preizkus(str(tmp_path / "dostop.json"))
    if request.node.get_closest_marker("pravi_dostop") is None:
        from core import link_hub_streznik
        monkeypatch.setattr(link_dostop, "zmoznosti",
                            lambda device_id: set(link_dostop.VSE_ZMOZNOSTI) if device_id else set())
        # Izmisljene naprave ne znajo zascite od naprave do naprave (pravilo »samo zasciteno« bi sicer bralo pravi krog).
        monkeypatch.setattr(link_dostop, "zahteva_zascito", lambda device_id: False)
        monkeypatch.setattr(link_hub_streznik, "OMEJENE_ODDAJE", {})
    yield
    link_dostop._za_preizkus(None)

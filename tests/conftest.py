"""Skupne nastavitve preizkusov.

Dostop naprav (core/link_dostop): zapis dovoljenj je v preizkusih VEDNO v zacasni datoteki - nikoli v pravih nastavitvah
uporabnika. Obstojeci preizkusi preverjajo druge stvari (usmerjanje, prenos datotek, predajo) z izmisljenimi napravami,
zato so te v njih v ozjem krogu racunalnika. Preizkus, ki preverja sama dovoljenja, se oznaci s
`@pytest.mark.pravi_dostop` in dobi prava pravila nad praznim zacasnim zapisom.
"""
import gc
import os
import signal
import sys

import pytest

_izid = {}
_VODILO = "DBUS_SESSION_BUS_ADDRESS"
# Okolje ob uvozu tega conftest (pred uvozom varoval in core/): korenski conftest.py mora izolacijo nastaviti PREJ
# (tests/test_izolacija_okolja.py, naloga 48).
_OKOLJE_OB_UVOZU = {k: os.environ.get(k) for k in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
                                                    "XDG_STATE_HOME", "TMPDIR", "GSETTINGS_BACKEND")}


@pytest.fixture
def okolje_ob_uvozu_conftest():
    return dict(_OKOLJE_OB_UVOZU)


def zasebno_vodilo():
    """Zasebno vodilo seje za ves tek (tests/zasebno_vodilo.py). Vrne (naslov, vodilo).

    Lastnik 18. 10. 2026: tek preizkusov na prenosniku ne sme govoriti z njegovim pravim Safeer Control/OS (imena
    org.gtk.Application, dejanja, obvestila). Prej je conftest preizkuse namenoma povezal s pravim vodilom seje
    (/run/user/UID/bus). Brez dbus-daemon dobi tek naslov, ki ne vodi nikamor - nikoli pravega vodila."""
    from zasebno_vodilo import ZasebnoVodilo
    vodilo = ZasebnoVodilo()
    return vodilo.naslov or "unix:path=" + os.path.join(vodilo.mapa, "ni-vodila"), vodilo


def ustavi_vodilo() -> None:
    vodilo = _izid.pop("vodilo_tek", None)
    if vodilo is not None:
        vodilo.ustavi()


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
    naslov, vodilo = zasebno_vodilo()
    _izid["vodilo_tek"] = vodilo
    os.environ[_VODILO] = naslov
    _izid["vodilo"] = naslov


# Vmesnik samo iz glavne niti (tests/varovalo_niti.py, naloga 42): klic Gtk/Gdk/WebKit ali okna Qt iz delovne niti
# preizkus podre. SAFEER_VAROVALO_NITI=porocilo samo zapise (povzetek na koncu teka), =0 izklopi.
from varovalo_niti import Varovalo  # noqa: E402

_varovalo = Varovalo.iz_okolja()

# Signali samo potomcem procesa preizkusov (tests/varovalo_signalov.py): preizkus ne sme ustaviti lastnikovega Planka.
from varovalo_signalov import Varovalo as VarovaloSignalov  # noqa: E402

_signali = VarovaloSignalov()
_signali.namesti()


@pytest.fixture(autouse=True)
def _signali_samo_potomcem():
    zacetek = len(_signali.krsitve)
    yield
    krsitve = _signali.od(zacetek)
    if krsitve:    # izjemo je preizkusena koda morda pogoltnila (siroko lovljenje napak)
        pytest.fail("Varovalo signalov (%d): %s" % (len(krsitve), "\n".join(krsitve[:5])), pytrace=False)


@pytest.fixture(autouse=True)
def _vmesnik_na_glavni_niti():
    _varovalo.namesti_nalozene()
    zacetek = _varovalo.oznaci()
    yield
    _varovalo.namesti_nalozene()      # tudi prostori, ki jih je ta preizkus sele uvozil (za naslednje preizkuse)
    krsitve = _varovalo.od(zacetek)
    if krsitve and _varovalo.nacin == "strogo":
        pytest.fail("Vmesnik izven glavne niti (%d): %s" % (len(krsitve), "\n".join(str(k) for k in krsitve[:5])),
                    pytrace=False)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    povzetek = _varovalo.povzetek()
    if povzetek:
        terminalreporter.write_sep("-", "varovalo niti")
        terminalreporter.write_line(povzetek)


@pytest.fixture(autouse=True)
def _smeti_na_glavni_niti():
    yield
    gc.collect()
    # Okolje procesa spreminjamo samo, ce ga je preizkus res spremenil: setenv med getenv druge niti (strezniki, GDBus,
    # WebKit prejsnjih preizkusov) je v glibc nedefiniran (tests/zasebno_vodilo.py).
    if _izid.get("vodilo") and os.environ.get(_VODILO) != _izid["vodilo"]:
        os.environ[_VODILO] = _izid["vodilo"]


def pytest_sessionfinish(session, exitstatus):
    _izid["koda"] = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    # Po porocilu in pospravljanju (korenski conftest pobrise zacasno mapo) proces koncamo brez Py_Finalize: tam je
    # sprostitev predmeta GObject iz globalne spremenljivke modula (g_object_unref v _PyModule_Clear) obvisela na
    # futexu - polni tek je izpisal porocilo in nato visel do casovne omejitve (gdb na posnetku jedra, 18. 10. 2026).
    # Zasebno vodilo ustavimo po PID (in mapo pobrisemo), preden se proces konca.
    if "koda" in _izid:
        # Deljena povezava vodila seje (Gio.bus_get, tudi Gtk.Application) ima exit-on-close: ko vodilo ustavimo, njena
        # delovna nit procesu poslje SIGTERM (raise). Ce pride pred os._exit, je izhodna koda 143 namesto izida
        # preizkusov - vsi preizkusi so uspeli, tek pa je padel (strace, 19. 10. 2026: tgkill iz niti GDBus po
        # kill(dbus-daemon)). Proces se tu tako ali tako konca z os._exit, zato SIGTERM do konca prezremo.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
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

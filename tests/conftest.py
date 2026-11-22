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

# Kljuc TLS niti Qt PRED kljucem GLib (sklad privzetih kontekstov, g_main_context_push_thread_default). Izmerjeno
# 5. 11. 2026 (gdb, najmanjsi poskus): niti bazena QtGui (»Thread (pooled)«, vzporedno polnjenje rastra v programskem
# izrisu QML) se iztecejo 30 s po zadnji uporabi; ob izhodu niti glibc klice destruktorje kljucev po vrsti nastanka. Ce je
# GLib svoj kljuc ustvaril prej (GTK/WebKit pred Qt), je sklad ze sproscen, ko ~QEventDispatcherGlib poklice pop ->
# »g_main_context_pop_thread_default: assertion 'stack != NULL'«, pripisano nakljucnemu kasnejsemu preizkusu. Z Qt prej
# opozorila ni (2 od 2 tekov z GLib prej ga imata, 0 od 2 z Qt prej). QThread.currentThread() ustvari kljuc Qt.
try:
    from PySide6.QtCore import QThread as _QThread
    _QThread.currentThread()
except ImportError:
    pass

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


# Pravi programi za skrbniske pravice (pkexec, sudo) in namesceni Safeer (/usr/bin/safeer-*) se v preizkusu ne zazenejo
# (tests/varovalo_programov.py; 25. 10. 2026: preizkus je na lastnikovem zaslonu odprl okno za skrbnisko geslo).
from varovalo_programov import Varovalo as VarovaloProgramov  # noqa: E402

_programi = VarovaloProgramov()
_programi.namesti()


@pytest.fixture(autouse=True)
def _brez_pravih_programov():
    zacetek = _programi.stevilo()
    yield
    krsitve = _programi.od(zacetek)
    if krsitve:
        pytest.fail("Varovalo programov (%d): %s" % (len(krsitve), "\n".join(krsitve[:5])), pytrace=False)


def _brez_controla(*_a, **_k):
    return None


_brez_controla.preizkus = True


def _zamenjaj_locen_control(so) -> None:
    if hasattr(so, "_ukaz_locenega_controla") and not getattr(so._ukaz_locenega_controla, "preizkus", False):
        so._ukaz_locenega_controla = _brez_controla


class _OkoUvozaSafeerOs:
    """Zivi preizkusi Safeer OS nimajo aplikacije, v katero bi se Control vgradil (en_proces.os_app() je None), zato je
    safeer_os._zagotovi_control zagnal locen Control: namesceni /usr/bin/safeer-control (varovalo programov ga je
    ustavilo, ~60 napak 4. 11. 2026) ali v CI safeer_control.py iz repozitorija, ki je po teku ostal v ozadju. Zamenjava
    se zgodi takoj ob uvozu safeer_os (tudi uvoz v telesu preizkusa) in velja do konca teka - niti prejsnjih preizkusov
    klicejo tudi pozneje. Preizkus, ki zagon locenega Controla preverja, funkcijo zamenja sam (mock.patch)."""

    def find_spec(self, ime, pot=None, cilj=None):
        if ime != "safeer_os":
            return None
        import importlib.machinery
        spec = importlib.machinery.PathFinder.find_spec(ime, pot)
        if spec is None or spec.loader is None or not hasattr(spec.loader, "exec_module"):
            return spec
        izvirni = spec.loader.exec_module

        def exec_module(modul, _izvirni=izvirni):
            _izvirni(modul)
            _zamenjaj_locen_control(modul)
        spec.loader.exec_module = exec_module
        return spec


if "safeer_os" in sys.modules:
    _zamenjaj_locen_control(sys.modules["safeer_os"])
sys.meta_path.insert(0, _OkoUvozaSafeerOs())


@pytest.fixture(autouse=True)
def _zaslon_brez_preizkusa_gonilnika(monkeypatch):
    """Zgornja meja hitrosti zivega zaslona (core/link_zaslon.omejitev_mozna) zazene ffmpeg tega racunalnika: izid bi bil
    odvisen od gonilnika, z laznim ffmpeg pa bi vsak preizkus cakal 20 s. Privzeto izklopljeno; test_zaslon_omejitev.py jo
    vklopi sam. Z atributom modula, ne z okoljem procesa (AGENTS.md: os.environ v procesu z nitmi; slepi pregled 22. 11.)."""
    monkeypatch.setattr("core.link_zaslon.VKLOP_V_PREIZKUSIH", False)
    yield


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


# ------------------------------------------------------------------ brez nasega WebKita (lokalni tek)
#: Lokalni tek brez WebKitGTK 6.0 (sistemski Python prenosnika ga nima): ~300 preizkusov je padlo z »Namespace WebKit
#: not available« (4. 11. 2026). Datoteke, ki WebKit rabijo (tests/razvrstitev_webkit.razvrsti, ~7 s analize samo
#: takrat), se preskocijo z jasnim razlogom in navodilom. Samo brez vticnika razvrstitev_webkit: CI izbere nacin (--safeer-webkit) in tam preskok
#: zaradi manjkajocega WebKita postane padec, posel z WebKitom pa mora pognati vse.
RAZLOG_BREZ_WEBKITA = ("ni WebKitGTK 6.0 (typelib WebKit-6.0): preizkus rabi nas WebKit - pozeni tools/pozeni-preizkuse.sh "
                       "(GI_TYPELIB_PATH na /usr/lib/safeer-webkit, xvfb-run)")
_brez_webkita = {"datoteke": None, "preskocene": set()}


def _ima_webkit() -> bool:
    try:
        import gi
        return "6.0" in gi.Repository.get_default().enumerate_versions("WebKit")
    except Exception:  # noqa: BLE001
        return False


def _datoteke_z_webkitom(config):
    if _brez_webkita["datoteke"] is None:
        _brez_webkita["datoteke"] = set()
        ima_nacin = config.pluginmanager.hasplugin("razvrstitev_webkit") and config.getoption("safeer_webkit", None)
        if not ima_nacin and not _ima_webkit():
            from pathlib import Path
            import razvrstitev_webkit
            koren = Path(__file__).resolve().parents[1]
            _brez_webkita["datoteke"] = {f for f, r in razvrstitev_webkit.razvrsti(koren)[0].items() if r}
    return _brez_webkita["datoteke"]


class _BrezWebkita(pytest.File):
    def collect(self):
        _brez_webkita["preskocene"].add(str(self.path))     # pytest 9 hook klice za vse datoteke mape, zbere izbrane
        pytest.skip(RAZLOG_BREZ_WEBKITA)


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makemodule(module_path, parent):
    datoteke = _datoteke_z_webkitom(parent.config)
    if not datoteke:
        return None
    from pathlib import Path
    try:
        rel = Path(module_path).resolve().relative_to(Path(__file__).resolve().parents[1]).as_posix()
    except ValueError:
        return None
    if rel not in datoteke:
        return None
    return _BrezWebkita.from_parent(parent, path=Path(module_path))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    povzetek = _varovalo.povzetek()
    if _brez_webkita["preskocene"]:
        terminalreporter.write_sep("-", "brez nasega WebKita")
        terminalreporter.write_line("%d datotek preskocenih: %s" % (len(_brez_webkita["preskocene"]), RAZLOG_BREZ_WEBKITA))
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


@pytest.fixture(autouse=True)
def _pozabi_manifeste_stremio():
    """Manifesti dodatkov Stremio so v pomnilniku procesa (core/media_servers._MANIFESTI, 30 min); vsak preizkus
    zacne brez njih. Enako je v korenskem conftest.py, ki pa se ne nalozi, ce pytest tece iz mape tests/ - tam je
    test glasbe/radia/TV dobil manifest prejsnjega preizkusa (samo katalog movie) pod istim naslovom (5. 11. 2026)."""
    ms = sys.modules.get("core.media_servers")
    if ms is not None and hasattr(ms, "_MANIFESTI"):
        ms._MANIFESTI.clear()
    yield

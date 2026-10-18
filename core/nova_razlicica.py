"""Nova razlicica tece takoj po namestitvi (lastnik, 18. 10. 2026: po `apt install` je stari Safeer OS tekel se dneve).

Paket .deb zamenja datoteke pod tekocim programom, Python pa ima staro kodo v pomnilniku - do odjave ali ponovnega zagona
racunalnika je tekla stara razlicica (in polovica nove: leni uvozi so brali nove module). Zdaj:

  * Spremljevalec: Gio.FileMonitor na mapi packaging/ namescenega programa (/usr/lib/safeer-os/packaging/VERSION_OS,
    /usr/lib/safeer-control/packaging/VERSION_CONTROL). dpkg datoteko zamenja s preimenovanjem iz .dpkg-new, zato
    spremljamo mapo. Ko je namestitev koncana (ni vec procesa dpkg/apt) in je razlicica v datoteki druga kot nasa, javi.
  * Cakanje: ponovni zagon samo, ko nic ne tece - predvajanje, klic (kamera, mikrofon ali deljenje zaslona v strani,
    gledanje ali deljenje zaslona v Linku), prenos (Splet, Link, posodobitev) - in ko ga uporabnik ne bo opazil: zaslon
    je zaklenjen ali uporabnik vsaj NEDEJAVEN_S ne dela nic (ce tega namizje ne pove, takoj, ko nic ne tece). Posodobitev,
    ki jo je uporabnik zagnal v Safeer OS, in gumb »Znova zazeni zdaj« ne cakata na nedejavnost.
  * Stanje: pred koncem se shranijo odprti zavihki Spleta in predvajanje (polozaj), nova razlicica jih obnovi. Datoteka je
    v XDG_RUNTIME_DIR (samo v pomnilniku, samo za uporabnika) in se po branju izbrise.
  * Zagon nove razlicice: proces pod zaganjalnikom (packaging/safeer-os-launcher, SAFEER_OS_NADZOR) konca s kodo
    KODA_ZNOVA in zaganjalnik zazene zaganjalnik nove razlicice (isti PID, profil AppArmor, nova pravila zaganjalnika);
    brez zaganjalnika se proces zamenja z novim (os.execv). Zapora je tekoca: konec gre skozi obicajni izhod (Scit vrne
    DNS, Link se pospravi, Mintov pult se vrne), kot bi uporabnik zaprl program.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Callable, Dict, Iterable, List, Optional, Sequence

#: Izhodna koda »zazeni novo razlicico« (EX_TEMPFAIL); zaganjalnik jo razume od 1.0.127 naprej.
KODA_ZNOVA = 75
#: Toliko sekund po zadnji spremembi mape packaging/ preverimo razlicico (dpkg zamenja vec datotek zaporedoma).
ZAMIK_S = 8
#: Kako pogosto cakanje preveri, ali je pravi trenutek za ponovni zagon.
POGLED_S = 20
#: Toliko sekund brez tipke in miske pomeni, da uporabnik ponovnega zagona ne bo opazil.
NEDEJAVEN_S = 120
#: Shranjeno stanje velja toliko sekund (stara datoteka ne sme obnoviti zavihkov ob naslednjem dnevu).
STANJE_VELJA_S = 600
NAJVEC_ZAVIHKOV = 50
#: Procesi, med katerimi namestitev paketov se tece (comm, najvec 15 znakov).
NAMESCANJE = ("dpkg", "apt", "apt-get", "aptitude", "unattended-upgr", "synaptic")
#: Nacini zagona, ki jih nova razlicica ohrani (enkratni ukazi, npr. --magnet, se ne ponovijo).
NACINI = ("--namizje", "--delovna", "--okno", "--predvajalnik", "--ozadje")

BESEDILA: Dict[str, Dict[str, str]] = {
    "sl": {"naslov": "{program} {razlicica} je nameščen",
           "besedilo": "Nova različica se zažene sama, ko je ne boste uporabljali. Odprti zavihki in predvajanje ostanejo.",
           "zdaj": "Znova zaženi zdaj"},
    "en": {"naslov": "{program} {razlicica} is installed",
           "besedilo": "The new version starts by itself when you are not using it. Open tabs and playback are kept.",
           "zdaj": "Restart now"},
    "de": {"naslov": "{program} {razlicica} ist installiert",
           "besedilo": "Die neue Version startet von selbst, wenn Sie sie nicht verwenden. Offene Tabs und Wiedergabe bleiben erhalten.",
           "zdaj": "Jetzt neu starten"},
    "es": {"naslov": "{program} {razlicica} está instalado",
           "besedilo": "La nueva versión se inicia sola cuando no la estés usando. Las pestañas abiertas y la reproducción se conservan.",
           "zdaj": "Reiniciar ahora"},
    "fr": {"naslov": "{program} {razlicica} est installé",
           "besedilo": "La nouvelle version démarre d'elle-même quand vous ne l'utilisez pas. Les onglets ouverts et la lecture sont conservés.",
           "zdaj": "Redémarrer maintenant"},
    "it": {"naslov": "{program} {razlicica} è installato",
           "besedilo": "La nuova versione si avvia da sola quando non la usi. Le schede aperte e la riproduzione vengono mantenute.",
           "zdaj": "Riavvia ora"},
}


def besedila(jezik: str, program: str, razlicica: str) -> Dict[str, str]:
    b = BESEDILA.get((jezik or "en")[:2].lower(), BESEDILA["en"])
    return {k: v.format(program=program, razlicica=razlicica) for k, v in b.items()}


def velja(koren: str, okolje: Optional[dict] = None) -> bool:
    """Samo namescen paket .deb: Flatpak in AppImage se posodobita drugace (stara mapa ostane nespremenjena), izvorne
    kode (razvoj) pa ne zaganjamo znova sami."""
    okolje = os.environ if okolje is None else okolje
    if okolje.get("FLATPAK_ID") or okolje.get("APPIMAGE"):
        return False
    if okolje.get("SAFEER_NOVA_RAZLICICA_MAPA"):      # preizkusi
        return True
    return os.path.abspath(koren).startswith("/usr/lib/")


def beri(pot: str) -> str:
    try:
        with open(pot, encoding="utf-8") as d:
            return d.read().strip()[:64]
    except OSError:
        return ""


def namescanje_tece(proc: str = "/proc", imena: Sequence[str] = NAMESCANJE) -> bool:
    """Ali tece dpkg ali apt (namestitev se ni koncana: postinst, sprozilci, druge pakete)."""
    try:
        vnosi = os.listdir(proc)
    except OSError:
        return False
    for vnos in vnosi:
        if not vnos.isdigit():
            continue
        try:
            with open(os.path.join(proc, vnos, "comm"), encoding="utf-8", errors="replace") as d:
                if d.read().strip() in imena:
                    return True
        except OSError:
            continue
    return False


class Spremljevalec:
    """Javi novo razlicico v datoteki `pot`, ko je namestitev koncana: ob_novi(nova_razlicica) - najvec enkrat na razlicico."""

    def __init__(self, Gio, GLib, pot: str, trenutna: str, ob_novi: Callable[[str], None], zamik_s: int = ZAMIK_S,
                 namescanje: Callable[[], bool] = namescanje_tece) -> None:
        self.GLib = GLib
        self.pot, self.trenutna, self.ob_novi = pot, trenutna, ob_novi
        self.zamik_s = zamik_s
        self._namescanje = namescanje
        self._ime = os.path.basename(pot)
        self._casovnik = 0
        self.javljena = ""
        self._monitor = Gio.File.new_for_path(os.path.dirname(pot)).monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None)
        self._monitor.connect("changed", self._ob_spremembi)

    def _ob_spremembi(self, _monitor, datoteka, druga, _dogodek) -> None:
        imena = {d.get_basename() for d in (datoteka, druga) if d is not None}
        if self._ime in imena:
            self.nacrtuj()

    def nacrtuj(self) -> None:
        if self._casovnik:
            self.GLib.source_remove(self._casovnik)
        self._casovnik = self.GLib.timeout_add_seconds(self.zamik_s, self._preveri)

    def _preveri(self) -> bool:
        self._casovnik = 0
        if self._namescanje():
            self.nacrtuj()          # dpkg/apt se dela: pocakamo konec namestitve
            return False
        nova = beri(self.pot)
        if nova and nova != self.trenutna and nova != self.javljena:
            self.javljena = nova
            try:
                self.ob_novi(nova)
            except Exception as e:  # noqa: BLE001 - spremljanje ne sme podreti programa
                print("[Safeer] nova razlicica:", e, file=sys.stderr, flush=True)
        return False

    def ustavi(self) -> None:
        if self._casovnik:
            self.GLib.source_remove(self._casovnik)
            self._casovnik = 0
        try:
            self._monitor.cancel()
        except Exception:  # noqa: BLE001
            pass


class Cakanje:
    """Pocaka pravi trenutek za ponovni zagon in ga takrat izvede (glej opis modula).

    zaposleno() -> razlog ("" = nic ne tece); nedejaven_s() -> sekunde brez vnosa ali None (namizje ne pove);
    zaklenjeno() -> zaslon zaklenjen; izvedi() -> shrani stanje in konca. takoj: ne caka na nedejavnost."""

    def __init__(self, GLib, zaposleno: Callable[[], str], nedejaven_s: Callable[[], Optional[float]],
                 zaklenjeno: Callable[[], bool], izvedi: Callable[[], None], takoj=False,
                 ob_cakanju: Optional[Callable[[str], None]] = None, pogled_s: int = POGLED_S) -> None:
        self.GLib = GLib
        self.zaposleno, self.nedejaven_s, self.zaklenjeno, self.izvedi = zaposleno, nedejaven_s, zaklenjeno, izvedi
        self.takoj = takoj
        self.ob_cakanju = ob_cakanju
        self.pogled_s = pogled_s
        self.razlog_zadnji = None
        self.koncano = False
        self._vir = 0

    def razlog(self) -> str:
        """Zakaj se ne smemo zagnati znova ("" = zdaj je prav)."""
        z = self.zaposleno() or ""
        if z:
            return z
        takoj = self.takoj() if callable(self.takoj) else self.takoj
        if takoj or self.zaklenjeno():
            return ""
        n = self.nedejaven_s()
        if n is not None and n < NEDEJAVEN_S:
            return "uporabnik"
        return ""

    def zacni(self) -> None:
        if self._tik():
            self._vir = self.GLib.timeout_add_seconds(self.pogled_s, self._tik)

    def zdaj(self) -> None:
        """Izrecna zahteva uporabnika (gumb): brez cakanja na nedejavnost in zaposlenost."""
        self._koncaj_cakanje()
        self.koncano = True
        self.izvedi()

    def _koncaj_cakanje(self) -> None:
        if self._vir:
            self.GLib.source_remove(self._vir)
            self._vir = 0

    def _tik(self) -> bool:
        if self.koncano:
            return False
        try:
            razlog = self.razlog()
        except Exception as e:  # noqa: BLE001 - pri dvomu pocakamo
            razlog = "napaka: %s" % e
        if razlog:
            if razlog != self.razlog_zadnji:
                print("[Safeer] nova razlicica caka: %s" % razlog, file=sys.stderr, flush=True)
                if self.razlog_zadnji is None and self.ob_cakanju is not None:
                    self.ob_cakanju(razlog)
            self.razlog_zadnji = razlog
            return True
        self.koncano = True
        self._vir = 0
        self.izvedi()
        return False


# ---------------------------------------------------------------------------------------------- stanje namizja
def _klic(Gio, GLib, ime: str, pot: str, vmesnik: str, metoda: str, vrne: str):
    vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    izid = vodilo.call_sync(ime, pot, vmesnik, metoda, None, GLib.VariantType(vrne), Gio.DBusCallFlags.NONE, 800, None)
    return izid.unpack()[0]


def nedejavnost_s(Gio, GLib) -> Optional[float]:
    """Sekunde brez tipke in miske: Muffin (Cinnamon) ali Mutter (GNOME) prek vodila seje, sicer razsiritev
    XScreenSaver na X11. None, ce tega ne pove nobeno."""
    for ime, pot in (("org.cinnamon.Muffin.IdleMonitor", "/org/cinnamon/Muffin/IdleMonitor/Core"),
                     ("org.gnome.Mutter.IdleMonitor", "/org/gnome/Mutter/IdleMonitor/Core")):
        try:
            return float(_klic(Gio, GLib, ime, pot, ime, "GetIdletime", "(t)")) / 1000.0
        except Exception:  # noqa: BLE001 - tega namizja ni
            continue
    return _nedejavnost_x11()


def _nedejavnost_x11() -> Optional[float]:
    if not os.environ.get("DISPLAY"):
        return None
    try:
        import ctypes
        import ctypes.util

        class _Info(ctypes.Structure):
            _fields_ = [("window", ctypes.c_ulong), ("state", ctypes.c_int), ("kind", ctypes.c_int),
                        ("til_or_since", ctypes.c_ulong), ("idle", ctypes.c_ulong), ("eventMask", ctypes.c_ulong)]
        x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xss = ctypes.CDLL(ctypes.util.find_library("Xss") or "libXss.so.1")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(_Info)
        xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_Info)]
        zaslon = x11.XOpenDisplay(None)
        if not zaslon:
            return None
        try:
            info = xss.XScreenSaverAllocInfo()
            if not info or not xss.XScreenSaverQueryInfo(zaslon, x11.XDefaultRootWindow(zaslon), info):
                return None
            vrednost = float(info.contents.idle) / 1000.0
            x11.XFree(info)
            return vrednost
        finally:
            x11.XCloseDisplay(zaslon)
    except Exception:  # noqa: BLE001 - brez libXss ali X11
        return None


def zaslon_zaklenjen(Gio, GLib) -> bool:
    for ime, pot in (("org.cinnamon.ScreenSaver", "/org/cinnamon/ScreenSaver"),
                     ("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver"),
                     ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver")):
        try:
            return bool(_klic(Gio, GLib, ime, pot, ime, "GetActive", "(b)"))
        except Exception:  # noqa: BLE001
            continue
    return False


def zaposlenost_pogledov(Gtk, WebKit, okna: Optional[Iterable] = None) -> str:
    """Spletni pogledi v oknih procesa: zvok iz strani = »predvajanje«, kamera/mikrofon/deljenje zaslona = »klic«."""
    if okna is None:
        try:
            okna = list(Gtk.Window.list_toplevels())
        except Exception:  # noqa: BLE001
            okna = []
    nic = getattr(getattr(WebKit, "MediaCaptureState", None), "NONE", None)
    zvok = False
    sklad = list(okna)
    while sklad:
        g = sklad.pop()
        if isinstance(g, WebKit.WebView):
            for ime in ("get_camera_capture_state", "get_microphone_capture_state", "get_display_capture_state"):
                f = getattr(g, ime, None)
                try:
                    if f is not None and nic is not None and f() != nic:
                        return "klic"
                except Exception:  # noqa: BLE001
                    pass
            try:
                zvok = zvok or bool(g.is_playing_audio())
            except Exception:  # noqa: BLE001
                pass
        try:
            otrok = g.get_first_child()
        except Exception:  # noqa: BLE001
            otrok = None
        while otrok is not None:
            sklad.append(otrok)
            otrok = otrok.get_next_sibling()
    return "predvajanje" if zvok else ""


# ---------------------------------------------------------------------------------------------- shranjeno stanje
def pot_stanja(program: str) -> str:
    """Vsak program svojo datoteko (Safeer OS in Control v istem procesu: Control ne sme prebrati stanja Safeer OS)."""
    koren = os.environ.get("SAFEER_NOVA_RAZLICICA_MAPA") or os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
    return os.path.join(koren, program, "nova-razlicica.json")


def shrani_stanje(program: str, stanje: dict) -> bool:
    pot = pot_stanja(program)
    try:
        os.makedirs(os.path.dirname(pot), mode=0o700, exist_ok=True)
        zacasna = pot + ".tmp"
        fd = os.open(zacasna, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as d:
            json.dump(dict(stanje, cas=time.time()), d, ensure_ascii=False)
        os.replace(zacasna, pot)
        return True
    except OSError as e:
        print("[Safeer] stanje za novo razlicico:", e, file=sys.stderr, flush=True)
        return False


def preberi_stanje(program: str, razlicica: str = "") -> dict:
    """Shranjeno stanje (in datoteko izbrise); {} ce ga ni, je staro ali za drugo razlicico."""
    pot = pot_stanja(program)
    try:
        with open(pot, encoding="utf-8") as d:
            stanje = json.load(d)
    except (OSError, ValueError):
        return {}
    finally:
        try:
            os.remove(pot)
        except OSError:
            pass
    if not isinstance(stanje, dict) or time.time() - float(stanje.get("cas") or 0) > STANJE_VELJA_S:
        return {}
    if razlicica and stanje.get("v") and stanje.get("v") != razlicica:
        return {}
    return stanje


def zavihki(splet_objekti: Iterable) -> List[str]:
    """Naslovi odprtih zavihkov Spleta (http/https, brez podvojenih, najvec NAJVEC_ZAVIHKOV)."""
    izid: List[str] = []
    for splet in splet_objekti:
        for z in list(getattr(splet, "zavihki", None) or []):
            try:
                uri = str(z["pogled"].get_uri() or "")
            except Exception:  # noqa: BLE001
                continue
            if uri.lower().startswith(("http://", "https://")) and uri not in izid:
                izid.append(uri)
    return izid[:NAJVEC_ZAVIHKOV]


def lokalni_medij(uri: str) -> str:
    """Pot datoteke za obnovo predvajanja ("" za tokove: njihov polozaj hrani »Nadaljuj z ogledom«, naslovi pa imajo
    lahko zetone streznikov, ki jih ne shranjujemo)."""
    uri = str(uri or "")
    if uri.startswith("file://"):
        from urllib.parse import unquote, urlparse
        uri = unquote(urlparse(uri).path)
    return uri if uri.startswith("/") and os.path.isfile(uri) else ""


# ---------------------------------------------------------------------------------------------- nova razlicica
def nacin_zagona(argv: Sequence[str]) -> List[str]:
    return [a for a in argv if a in NACINI]


def znova(spremenljivka_nadzora: str, skripta: str, argv: Sequence[str]) -> int:
    """Po koncu stare razlicice: KODA_ZNOVA, ce nas je zagnal zaganjalnik (ta zazene novega), sicer exec nove kode."""
    if os.environ.get(spremenljivka_nadzora) == str(os.getppid()):
        return KODA_ZNOVA
    for tok in (sys.stdout, sys.stderr):
        try:
            tok.flush()
        except Exception:  # noqa: BLE001
            pass
    os.execv(sys.executable, [sys.executable, skripta, *nacin_zagona(argv)])
    return KODA_ZNOVA  # pragma: no cover - execv se ne vrne

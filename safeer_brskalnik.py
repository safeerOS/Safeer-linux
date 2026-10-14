#!/usr/bin/env python3
"""Safeer Browser za Linux na GTK4 in WebKitGTK 6.0 (nas WebKit s popravki): Splet (core/os_splet.VdelaniSplet) v
svojem oknu.

Lastnik, 14. 10. 2026: »vsi produkti z najnovejso tehnologijo, ki se dela na nasih napravah« - tudi Safeer Browser.
Splet in brskalnik sta tako ena koda: vsaka izboljsava spletne izkusnje je takoj v obeh (prej rocni prenos v
safeer_mint.py, GTK3). Podatki (prijave, piskotki, zaznamki, zgodovina) so v isti mapi kot prej (ConfigManager).

Uporaba: safeer_brskalnik.py [NASLOV ...]   - drugi zagon odpre naslove v oknu, ki ze tece (en primerek).
"""
from __future__ import annotations

import os
import sys

KOREN = os.path.dirname(os.path.abspath(__file__))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

if os.environ.get("FLATPAK_ID") and os.path.isdir("/app/host-bin"):
    # Kot packaging/safeer-os-launcher: orodja racunalnika (gio za »Odpri z«, povezave mailto: ...) prek ovojev in iste
    # mape podatkov kot .deb (prijave, zaznamki). Preizkus 14. 10.: brez tega je bil mailto »program ni najden«.
    # Pred uvozom core.config (CONFIG_DIR se doloci ob uvozu).
    if "/app/host-bin" not in os.environ.get("PATH", "").split(":"):
        os.environ["PATH"] = "/app/host-bin:" + os.environ.get("PATH", "")
    _dom = os.path.expanduser("~")
    os.environ["XDG_CONFIG_HOME"] = os.path.join(_dom, ".config")
    os.environ["XDG_DATA_HOME"] = os.path.join(_dom, ".local", "share")
    os.environ["XDG_CACHE_HOME"] = os.path.join(_dom, ".cache")

from core import pomnilnik  # noqa: E402
pomnilnik.omeji_arene(2)

import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402
from gi.repository import WebKit as WebKit2  # noqa: E402

pomnilnik.tlak_omrezja(WebKit2, 160)   # pred prvim pogledom (kot Safeer OS)

from core import log as safeer_log  # noqa: E402
from core.config import CONFIG_DIR, ConfigManager  # noqa: E402

APP_ID = "io.github.memelandfaner.SafeerBrowser"
JEZIKI = ("sl", "en", "de", "es", "fr", "it")


def razlicica() -> str:
    try:
        with open(os.path.join(KOREN, "packaging", "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def jezik() -> str:
    """Jezik vmesnika: nastavitev brskalnika (language), sicer jezik seje."""
    v = str(ConfigManager().get("language", "auto") or "auto")[:2].lower()
    if v in JEZIKI:
        return v
    for ime in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for del_ in (os.environ.get(ime) or "").split(":"):
            k = del_[:2].lower()
            if k in JEZIKI:
                return k
    return "en"


def naslovi_iz_argumentov(argv) -> list:
    """Naslovi in datoteke iz ukazne vrstice (privzeti brskalnik: xdg-open https://...)."""
    izhod = []
    for a in argv:
        if not a or a.startswith("-"):
            continue
        if a.startswith(("http://", "https://", "file://", "about:")):
            izhod.append(a)
        elif os.path.exists(a):
            izhod.append(GLib.filename_to_uri(os.path.abspath(a), None))
    return izhod


def shrani_sejo(config, naslovi, izbran: int = 0) -> None:
    """Odprti zavihki ob zaprtju okna (obnovijo se ob naslednjem zagonu, kot prej v safeer_mint.py) in zavihek, ki je
    bil izbran (preizkus 14. 10.: po zagonu je bil vedno izbran prvi)."""
    shranjeni = [(i, n) for i, n in enumerate(naslovi) if n.startswith(("http://", "https://"))][:30]
    config.set("splet_seja_izbran", next((k for k, (i, _n) in enumerate(shranjeni) if i == izbran), 0))
    config.set("splet_seja", [n for _i, n in shranjeni])


def izbran_v_seji(config, n: int) -> int:
    try:
        i = int(config.get("splet_seja_izbran", 0) or 0)
    except (TypeError, ValueError):
        i = 0
    return i if 0 <= i < n else 0


def nalozi_sejo(config) -> list:
    v = config.get("splet_seja", []) or []
    return [str(n) for n in v if isinstance(n, str) and n.startswith(("http://", "https://"))][:30]


class SafeerBrskalnik(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.okno = None
        self.splet = None

    # ------------------------------------------------------------------ okno
    def _ustvari(self) -> None:
        from core.os_splet import VdelaniSplet
        okno = Gtk.ApplicationWindow(application=self, title="Safeer Browser")
        okno.set_icon_name("safeer-browser")
        okno.set_default_size(1280, 820)
        self.splet = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit2, KOREN, jezik, None, stars=okno)
        okno.set_child(self.splet.gradnik)
        k = Gtk.EventControllerKey()
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", lambda _k, keyval, _koda, stanje: bool(self.splet.tipka(_Tipka(keyval, stanje))))
        okno.add_controller(k)
        okno.connect("close-request", self._ob_zaprtju)
        self.okno = okno
        seja = nalozi_sejo(self.splet.config)
        if seja:
            self.splet.odpri(seja[0])
            for n in seja[1:]:
                self.splet.nov_zavihek(n)
            self.splet.izberi(self.splet.zavihki[izbran_v_seji(self.splet.config, len(self.splet.zavihki))]["pogled"])

    def _ob_zaprtju(self, *_a) -> bool:
        try:
            tren = self.splet.trenutni()
            zavihki = self.splet.zavihki
            shrani_sejo(self.splet.config, [z["pogled"].get_uri() or "" for z in zavihki],
                        next((i for i, z in enumerate(zavihki) if z["pogled"] is tren), 0))
        except Exception as e:  # noqa: BLE001 - zaprtje mora uspeti tudi brez seje
            print("[Safeer Browser] seja:", e, flush=True)
        self.splet.koncaj_drm()
        return False

    def do_activate(self) -> None:
        if self.okno is None:
            self._ustvari()
        self.okno.present()

    def do_open(self, datoteke, _n, _namig) -> None:
        """Naslovi od drugod (privzeti brskalnik, drugi zagon): v oknu, ki tece; strani, ki jo ima uporabnik odprto,
        ne zamenja (VdelaniSplet.odpri_povezavo)."""
        prvic = self.okno is None
        if prvic:
            self._ustvari()
        for i, d in enumerate(datoteke):
            naslov = d.get_uri() or ""
            if prvic and i == 0 and not nalozi_sejo(self.splet.config):
                self.splet.odpri(naslov)
            else:
                self.splet.odpri_povezavo(naslov)
        self.okno.present()


class _Tipka:
    def __init__(self, keyval, state) -> None:
        self.keyval, self.state = keyval, state


def main() -> int:
    if "--version" in sys.argv[1:]:
        print("Safeer Browser " + razlicica())
        return 0
    safeer_log.install(CONFIG_DIR, razlicica())
    app = SafeerBrskalnik()
    argumenti = [sys.argv[0]] + naslovi_iz_argumentov(sys.argv[1:])
    return app.run(argumenti)


if __name__ == "__main__":
    sys.exit(main())

"""MPRIS za domaci predvajalnik Safeer OS.

Medijske tipke na tipkovnici, gumbi na slusalkah in Cinnamonov zvocni applet govorijo s predvajalniki prek
vmesnika MPRIS (org.mpris.MediaPlayer2). Brez njega Safeer OS za sistem ne obstaja: tipka »premor« ne naredi
nic, applet ne pokaze, kaj igra. Ta modul predvajalnik samo predstavi sistemu - ukazi gredo po isti poti kot
gumbi v oknu predvajalnika (klicatelj poda funkcijo `ukaz`), zato se shranjevanje napredka in vrsta obnasata enako.

Ime na vodilu imamo samo, dokler nekaj igra ali je v premoru; ustavljen predvajalnik se iz appleta umakne.
"""
from typing import Callable, Optional

IME = "org.mpris.MediaPlayer2.safeer"
POT = "/org/mpris/MediaPlayer2"
V_KOREN = "org.mpris.MediaPlayer2"
V_PREDVAJALNIK = "org.mpris.MediaPlayer2.Player"
BREZ_SKLADBE = "/org/mpris/MediaPlayer2/TrackList/NoTrack"
MIKRO = 1_000_000

XML = """<node>
 <interface name="org.mpris.MediaPlayer2">
  <method name="Raise"/>
  <method name="Quit"/>
  <property name="CanQuit" type="b" access="read"/>
  <property name="CanRaise" type="b" access="read"/>
  <property name="HasTrackList" type="b" access="read"/>
  <property name="Identity" type="s" access="read"/>
  <property name="DesktopEntry" type="s" access="read"/>
  <property name="SupportedUriSchemes" type="as" access="read"/>
  <property name="SupportedMimeTypes" type="as" access="read"/>
 </interface>
 <interface name="org.mpris.MediaPlayer2.Player">
  <method name="Next"/>
  <method name="Previous"/>
  <method name="Pause"/>
  <method name="PlayPause"/>
  <method name="Stop"/>
  <method name="Play"/>
  <method name="Seek"><arg name="Offset" type="x" direction="in"/></method>
  <method name="SetPosition"><arg name="TrackId" type="o" direction="in"/><arg name="Position" type="x" direction="in"/></method>
  <method name="OpenUri"><arg name="Uri" type="s" direction="in"/></method>
  <signal name="Seeked"><arg name="Position" type="x"/></signal>
  <property name="PlaybackStatus" type="s" access="read"/>
  <property name="Rate" type="d" access="readwrite"/>
  <property name="Metadata" type="a{sv}" access="read"/>
  <property name="Volume" type="d" access="readwrite"/>
  <property name="Position" type="x" access="read"/>
  <property name="MinimumRate" type="d" access="read"/>
  <property name="MaximumRate" type="d" access="read"/>
  <property name="CanGoNext" type="b" access="read"/>
  <property name="CanGoPrevious" type="b" access="read"/>
  <property name="CanPlay" type="b" access="read"/>
  <property name="CanPause" type="b" access="read"/>
  <property name="CanSeek" type="b" access="read"/>
  <property name="CanControl" type="b" access="read"/>
 </interface>
</node>"""

TIPI = {"CanQuit": "b", "CanRaise": "b", "HasTrackList": "b", "Identity": "s", "DesktopEntry": "s",
        "SupportedUriSchemes": "as", "SupportedMimeTypes": "as", "PlaybackStatus": "s", "Rate": "d", "Volume": "d",
        "Position": "x", "MinimumRate": "d", "MaximumRate": "d", "CanGoNext": "b", "CanGoPrevious": "b", "CanPlay": "b",
        "CanPause": "b", "CanSeek": "b", "CanControl": "b"}
TIPI_METAPODATKOV = {"mpris:trackid": "o", "mpris:length": "x", "mpris:artUrl": "s", "xesam:title": "s",
                     "xesam:artist": "as", "xesam:album": "s", "xesam:url": "s"}
STANJA = {"predvaja": "Playing", "premor": "Paused"}


def igra(podatki: dict) -> bool:
    """Ali je predvajalnik za sistem »ziv« (predvaja ali je v premoru)."""
    return (podatki or {}).get("stanje") in STANJA


def lastnosti(podatki: dict) -> dict:
    """Lastnosti vmesnika Player iz podatkov predvajalnika (Predvajalnik.podatki() + neobvezno izvajalec, slika, uri).

    Cista funkcija (brez D-Bus), da jo je mogoce preizkusiti. Polozaj ni med njimi: bere se sproti."""
    p = podatki or {}
    ziv = igra(p)
    indeks, skupaj = int(p.get("indeks", -1) or 0), int(p.get("skupaj", 0) or 0)
    trajanje = float(p.get("trajanje") or 0)
    v_zivo = p.get("vrsta") in ("tv", "radio")
    meta = {"mpris:trackid": "/si/safeer/os/skladba/%d" % max(0, indeks) if ziv else BREZ_SKLADBE}
    if ziv:
        meta["xesam:title"] = str(p.get("naslov") or "")[:300]
        izvajalec = str(p.get("izvajalec") or p.get("izvor") or "")[:200]
        if izvajalec:
            meta["xesam:artist"] = [izvajalec]
        if trajanje > 0 and not v_zivo:
            meta["mpris:length"] = int(trajanje * MIKRO)
        slika = str(p.get("slika") or "")
        if slika.startswith(("file://", "https://", "http://")):
            meta["mpris:artUrl"] = slika[:2048]
    return {
        "PlaybackStatus": STANJA.get(p.get("stanje"), "Stopped"),
        "Metadata": meta,
        "CanGoNext": ziv and (indeks < skupaj - 1 or bool(p.get("vrstaStrani"))),
        "CanGoPrevious": ziv and (indeks > 0 or bool(p.get("vrstaStrani"))),
        "CanPlay": ziv, "CanPause": ziv,
        "CanSeek": ziv and trajanje > 0 and not v_zivo,
    }


class Mpris:
    """Predstavi predvajalnik na sejnem vodilu. `podatki()` vrne stanje, `ukaz(ime, vrednost=None)` izvede dejanje
    (premor, naslednja, prejsnja, ustavi, skok, odpri) - oboje poda Safeer OS; klici pridejo na glavni niti."""

    def __init__(self, vodilo, podatki: Callable[[], dict], ukaz: Callable[..., bool],
                 identiteta: str = "Safeer OS", vnos: str = "safeer-os") -> None:
        from gi.repository import Gio, GLib
        self._Gio, self._GLib = Gio, GLib
        self._vodilo, self._podatki, self._ukaz = vodilo, podatki, ukaz
        self._identiteta, self._vnos = identiteta, vnos
        self._lastnik: Optional[int] = None
        self._zadnje: dict = {}
        info = Gio.DBusNodeInfo.new_for_xml(XML)
        self._registracije = [vodilo.register_object(POT, v, self._klic, self._beri, self._pisi) for v in info.interfaces]

    # ------------------------------------------------------------------ vrednosti
    def _varianta(self, ime: str, vrednost):
        if ime == "Metadata":
            return self._GLib.Variant("a{sv}", {k: self._GLib.Variant(TIPI_METAPODATKOV[k], v) for k, v in vrednost.items()})
        return self._GLib.Variant(TIPI[ime], vrednost)

    def _vse(self, vmesnik: str) -> dict:
        if vmesnik == V_KOREN:
            return {"CanQuit": False, "CanRaise": True, "HasTrackList": False, "Identity": self._identiteta,
                    "DesktopEntry": self._vnos, "SupportedUriSchemes": [], "SupportedMimeTypes": []}
        p = self._podatki() or {}
        izid = lastnosti(p)
        izid.update({"Rate": 1.0, "MinimumRate": 1.0, "MaximumRate": 1.0, "Volume": 1.0, "CanControl": True,
                     "Position": int(float(p.get("pozicija") or 0) * MIKRO)})
        return izid

    def _beri(self, _vodilo, _posiljatelj, _pot, vmesnik, ime):
        vrednosti = self._vse(vmesnik)
        return self._varianta(ime, vrednosti[ime]) if ime in vrednosti else None

    def _pisi(self, _vodilo, _posiljatelj, _pot, _vmesnik, _ime, _vrednost) -> bool:
        return True          # Rate in Volume: sprejmemo, a ne spreminjamo (glasnost vodi sistem)

    # ------------------------------------------------------------------ ukazi
    def _klic(self, _vodilo, _posiljatelj, _pot, vmesnik, metoda, parametri, klic) -> None:
        try:
            p = self._podatki() or {}
            stanje = p.get("stanje")
            if vmesnik == V_KOREN:
                if metoda == "Raise":
                    self._ukaz("odpri")
            elif metoda == "PlayPause" and igra(p):
                self._ukaz("premor")
            elif metoda == "Pause" and stanje == "predvaja":
                self._ukaz("premor")
            elif metoda == "Play" and stanje == "premor":
                self._ukaz("premor")
            elif metoda == "Stop" and igra(p):
                self._ukaz("ustavi")
            elif metoda == "Next" and igra(p):
                self._ukaz("naslednja")
            elif metoda == "Previous" and igra(p):
                self._ukaz("prejsnja")
            elif metoda in ("Seek", "SetPosition") and igra(p):
                argi = parametri.unpack()
                cilj = float(p.get("pozicija") or 0) + argi[0] / MIKRO if metoda == "Seek" else argi[1] / MIKRO
                if self._ukaz("skok", max(0.0, cilj)):
                    self._vodilo.emit_signal(None, POT, V_PREDVAJALNIK, "Seeked",
                                             self._GLib.Variant("(x)", (int(max(0.0, cilj) * MIKRO),)))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] MPRIS", metoda, e, flush=True)
        klic.return_value(None)

    # ------------------------------------------------------------------ spremembe
    def osvezi(self) -> None:
        """Poklici ob vsaki spremembi predvajalnika: prevzame ali spusti ime in sporoci spremenjene lastnosti."""
        p = self._podatki() or {}
        if igra(p) and self._lastnik is None:
            self._lastnik = self._Gio.bus_own_name_on_connection(self._vodilo, IME, self._Gio.BusNameOwnerFlags.NONE, None, None)
        nove = lastnosti(p)
        spremenjene = {k: v for k, v in nove.items() if self._zadnje.get(k) != v}
        self._zadnje = nove
        if spremenjene and self._lastnik is not None:
            telo = self._GLib.Variant("(sa{sv}as)", (V_PREDVAJALNIK, {k: self._varianta(k, v) for k, v in spremenjene.items()}, []))
            try:
                self._vodilo.emit_signal(None, POT, "org.freedesktop.DBus.Properties", "PropertiesChanged", telo)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] MPRIS sprememba:", e, flush=True)
        if not igra(p) and self._lastnik is not None:
            self._Gio.bus_unown_name(self._lastnik)
            self._lastnik = None

    def zapri(self) -> None:
        if self._lastnik is not None:
            self._Gio.bus_unown_name(self._lastnik)
            self._lastnik = None
        for r in self._registracije:
            try:
                self._vodilo.unregister_object(r)
            except Exception:  # noqa: BLE001
                pass
        self._registracije = []

"""Zaslon in vnos racunalnika na Waylandu prek xdg-desktop-portal (ScreenCast, RemoteDesktop) za Safeer Link.

Zakaj: na Waylandu (Ubuntu 24.04 GNOME, KDE, sway) program zaslona ne more prebrati sam in tujih oken ne more
upravljati - to dovoli samo uporabnik, prek portala. Prej je deljenje zaslona v Linku na Waylandu zajemalo XWayland:
crna slika, vnos pa je premikal samo okna XWayland (izmerjeno 18. 10. 2026, glej core/x11.py). Zdaj:

  * Seja.odpri(): portal vprasa uporabnika (GNOME: izbira zaslona in »Dovoli oddaljeno upravljanje«), nato pove
    vozlisce PipeWire in velikost zaslona. Ob prvem deljenju se izbira zapomni (persist_mode 2, zeton obnovitve v
    ~/.config/safeer-control/portal-zaslon.json): naslednjic brez vprasanja - uporabnik, ki gleda s televizorja ali
    telefona, za racunalnikom nima nikogar, ki bi kliknil »Deli«. Preklic v nastavitvah sistema zeton razveljavi.
  * Slike: PipeWire -> GStreamer (pipewiresrc) - za H.264 v loceni proces core/zajem_pipewire.py (ffmpeg, isti
    kodirniki kot na X11), za JPEG k Hubu SlikePipewire v tem procesu.
  * VnosPortal: isti seznam dovoljenega kot link_vnos.Vnos (podrazred), dogodki gredo v RemoteDesktop.Notify*.

Pravila: zahteve portala tecejo v klicateljevi niti z lastnim GMainContext (glavna zanka GTK ni blokirana); vse
napake so NapakaPortala s kodo za vmesnik; nic iz omrezja ne izbere zaslona ali naprave - to stori uporabnik v portalu.
"""

from __future__ import annotations

import itertools
import json
import os
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

from core.link_vnos import Vnos

PORTAL = "org.freedesktop.portal.Desktop"
POT = "/org/freedesktop/portal/desktop"
SC = "org.freedesktop.portal.ScreenCast"
RD = "org.freedesktop.portal.RemoteDesktop"
ZAHTEVA = "org.freedesktop.portal.Request"
SEJA = "org.freedesktop.portal.Session"

VIR_MONITOR = 1
KAZALEC_SKRIT, KAZALEC_VDELAN = 1, 2
NAPRAVE_TIPKOVNICA_KAZALEC = 1 | 2
OBSTOJNO = 2                    # persist_mode: dokler uporabnik ne preklice
#: Najdlje cakamo uporabnika na izbiro v portalu (prvo deljenje); potem dialog zapremo.
ROK_IZBIRE_S = 120.0
#: Gumbi miske v kodah evdev (linux/input-event-codes.h), kot jih hoce RemoteDesktop.NotifyPointerButton.
GUMBI_EVDEV = {"1": 0x110, "2": 0x112, "3": 0x111}      # levi, srednji, desni (xdotool 1/2/3)

_stevec = itertools.count(1)


class NapakaPortala(RuntimeError):
    """koda: ni_portala | zavrnjeno | rok | napaka."""

    def __init__(self, koda: str, opis: str = "") -> None:
        super().__init__(opis or koda)
        self.koda = koda


def _gio():
    from gi.repository import Gio, GLib
    return Gio, GLib


def _vodilo():
    Gio, _ = _gio()
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def lastnost(vmesnik: str, ime: str, vodilo=None):
    """Lastnost portala ali None (ni vodila, portala, vmesnika)."""
    Gio, GLib = _gio()
    try:
        v = (vodilo or _vodilo()).call_sync(PORTAL, POT, "org.freedesktop.DBus.Properties", "Get",
                                            GLib.Variant("(ss)", (vmesnik, ime)), GLib.VariantType("(v)"),
                                            Gio.DBusCallFlags.NONE, 2000, None)
        return v.unpack()[0]
    except Exception:  # noqa: BLE001
        return None


def zmoznosti(vodilo=None) -> dict:
    """Kaj portal te seje zna: zajem monitorja, vnos (RemoteDesktop), obnovitev izbire brez vprasanja."""
    vodilo = vodilo or _vodilo()
    sc = lastnost(SC, "version", vodilo) or 0
    viri = lastnost(SC, "AvailableSourceTypes", vodilo) or 0
    kazalci = lastnost(SC, "AvailableCursorModes", vodilo) or 0
    rd = lastnost(RD, "version", vodilo) or 0
    naprave = lastnost(RD, "AvailableDeviceTypes", vodilo) or 0
    return {"zajem": bool(sc) and bool(int(viri) & VIR_MONITOR), "vnos": bool(rd) and (int(naprave) & 3) == 3,
            "obnovi_zajem": int(sc) >= 4, "obnovi_vnos": int(rd) >= 2,
            "kazalec_vdelan": bool(int(kazalci) & KAZALEC_VDELAN)}


def gstreamer_pipewire() -> bool:
    """Ali ima GStreamer vticnik pipewiresrc (paket gstreamer1.0-pipewire)."""
    try:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)
        return Gst.ElementFactory.find("pipewiresrc") is not None
    except Exception:  # noqa: BLE001
        return False


def pot_zetonov() -> str:
    mapa = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "safeer-control")
    return os.path.join(mapa, "portal-zaslon.json")


def _beri_zetone(pot: str) -> dict:
    try:
        with open(pot, encoding="utf-8") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError):
        return {}


def _pisi_zeton(pot: str, kljuc: str, zeton: str) -> None:
    j = _beri_zetone(pot)
    if zeton:
        j[kljuc] = zeton
    else:
        j.pop(kljuc, None)
    try:
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        zacasna = pot + ".tmp"
        fd = os.open(zacasna, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(j, f)
        os.replace(zacasna, pot)
    except OSError as e:
        print("[portal] zeton:", e, flush=True)


def _v(podpis: str, vrednost):
    _, GLib = _gio()
    return GLib.Variant(podpis, vrednost)


class Seja:
    """Ena seja portala: zajem monitorja (in vnos, ce ga portal zna). Odpre jo klicateljeva nit, zapre zapri()."""

    def __init__(self, vnos: bool = True, pot: Optional[str] = None, vodilo=None, rok_s: float = ROK_IZBIRE_S) -> None:
        self.vodilo = vodilo or _vodilo()
        self.pot = pot or pot_zetonov()
        self.rok_s = rok_s
        z = zmoznosti(self.vodilo)
        if not z["zajem"]:
            raise NapakaPortala("ni_portala", "portal ScreenCast ni na voljo")
        self.zmore = z
        self.vnos = bool(vnos and z["vnos"])
        self.seja = ""
        self.fd = -1
        self.tok: Dict[str, int] = {}
        self._zapri_zaklep = threading.Lock()

    # ------------------------------------------------------------------ zahteve portala
    def _zahteva(self, vmesnik: str, metoda: str, argumenti: tuple, podpis: str, moznosti: dict,
                 rok_s: float = 30.0) -> dict:
        """Metoda z objektom Request: pocaka na signal Response v lastnem GMainContext te niti."""
        Gio, GLib = _gio()
        zeton = "safeer%d_%d" % (os.getpid(), next(_stevec))
        posiljatelj = self.vodilo.get_unique_name()[1:].replace(".", "_")
        pricakovana = "%s/request/%s/%s" % (POT, posiljatelj, zeton)
        moznosti = dict(moznosti, handle_token=_v("s", zeton))
        kontekst = GLib.MainContext.new()
        kontekst.push_thread_default()
        izid: dict = {}
        narocila = []

        def odziv(_c, _s, _p, _i, _sig, parametri, *_a) -> None:
            koda, rezultati = parametri.unpack()
            izid.setdefault("koda", int(koda))
            izid.setdefault("rezultati", rezultati)

        def naroci(pot_zahteve: str) -> None:
            narocila.append(self.vodilo.signal_subscribe(None, ZAHTEVA, "Response", pot_zahteve, None,
                                                         Gio.DBusSignalFlags.NONE, odziv))
        try:
            naroci(pricakovana)
            odgovor = self.vodilo.call_sync(PORTAL, POT, vmesnik, metoda, _v(podpis, argumenti + (moznosti,)),
                                            GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, 30000, None)
            dejanska = odgovor.unpack()[0]
            if dejanska != pricakovana:          # stari portali (< 0.9) imajo drugacno pot zahteve
                naroci(dejanska)
            konec = time.monotonic() + rok_s
            while "koda" not in izid:
                if time.monotonic() > konec:
                    try:
                        self.vodilo.call_sync(PORTAL, dejanska, ZAHTEVA, "Close", None, None,
                                              Gio.DBusCallFlags.NONE, 2000, None)
                    except Exception:  # noqa: BLE001
                        pass
                    raise NapakaPortala("rok", "uporabnik ni izbral zaslona")
                if not kontekst.iteration(False):
                    time.sleep(0.01)
        except NapakaPortala:
            raise
        except Exception as e:  # noqa: BLE001
            raise NapakaPortala("napaka", str(e)) from e
        finally:
            for n in narocila:
                self.vodilo.signal_unsubscribe(n)
            kontekst.pop_thread_default()
        if izid["koda"] == 1:
            raise NapakaPortala("zavrnjeno", "uporabnik je deljenje zavrnil")
        if izid["koda"] != 0:
            raise NapakaPortala("napaka", "portal: %s.%s koncal s kodo %d" % (vmesnik, metoda, izid["koda"]))
        return izid["rezultati"] or {}

    # ------------------------------------------------------------------ odpri / zapri
    def odpri(self) -> dict:
        """Seja, izbira (ali obnovitev) zaslona in PipeWire. Vrne tok {vozlisce, sirina, visina, x, y}."""
        Gio, GLib = _gio()
        zetoni = _beri_zetone(self.pot)
        kljuc = "vnos" if self.vnos else "zajem"
        vmesnik = RD if self.vnos else SC
        r = self._zahteva(vmesnik, "CreateSession", (), "(a{sv})",
                          {"session_handle_token": _v("s", "safeer%d" % next(_stevec))})
        self.seja = str(r.get("session_handle") or "")
        if not self.seja:
            raise NapakaPortala("napaka", "portal ni vrnil seje")
        try:
            obnovi = {}
            if zetoni.get(kljuc) and self.zmore["obnovi_" + kljuc]:
                obnovi["restore_token"] = _v("s", str(zetoni[kljuc]))
            if self.zmore["obnovi_" + kljuc]:
                obnovi["persist_mode"] = _v("u", OBSTOJNO)
            viri = {"types": _v("u", VIR_MONITOR), "multiple": _v("b", False),
                    "cursor_mode": _v("u", KAZALEC_VDELAN if self.zmore["kazalec_vdelan"] else KAZALEC_SKRIT)}
            if self.vnos:
                # Seja RemoteDesktop: obnovitev gre v SelectDevices (ScreenCast je v taki seji ne sprejme).
                self._zahteva(RD, "SelectDevices", (self.seja,), "(oa{sv})",
                              dict({"types": _v("u", NAPRAVE_TIPKOVNICA_KAZALEC)}, **obnovi))
                self._zahteva(SC, "SelectSources", (self.seja,), "(oa{sv})", viri)
            else:
                self._zahteva(SC, "SelectSources", (self.seja,), "(oa{sv})", dict(viri, **obnovi))
            r = self._zahteva(vmesnik, "Start", (self.seja, ""), "(osa{sv})", {}, rok_s=self.rok_s)
            _pisi_zeton(self.pot, kljuc, str(r.get("restore_token") or ""))
            tokovi = list(r.get("streams") or [])
            if not tokovi:
                raise NapakaPortala("napaka", "portal ni vrnil zaslona")
            vozlisce, lastnosti = tokovi[0]
            sirina, visina = tuple(lastnosti.get("size") or (0, 0))
            x, y = tuple(lastnosti.get("position") or (0, 0))
            if self.vnos and not (int(r.get("devices") or 0) & 2):
                self.vnos = False            # uporabnik je dovolil samo ogled
            odgovor, fdji = self.vodilo.call_with_unix_fd_list_sync(
                PORTAL, POT, SC, "OpenPipeWireRemote", _v("(oa{sv})", (self.seja, {})), GLib.VariantType("(h)"),
                Gio.DBusCallFlags.NONE, 10000, None, None)
            self.fd = fdji.get(odgovor.unpack()[0])
            self.tok = {"vozlisce": int(vozlisce), "sirina": int(sirina), "visina": int(visina),
                        "x": int(x), "y": int(y)}
            if not self.tok["sirina"] or not self.tok["visina"]:
                raise NapakaPortala("napaka", "portal ni povedal velikosti zaslona")
            print("[portal] zaslon %dx%d (vozlisce %d), vnos %s, obnovljivo %s"
                  % (sirina, visina, vozlisce, "da" if self.vnos else "ne", "da" if r.get("restore_token") else "ne"),
                  flush=True)
            return dict(self.tok)
        except NapakaPortala as e:
            if e.koda == "zavrnjeno":
                _pisi_zeton(self.pot, kljuc, "")      # zavrnjeno izbiro ne obnavljamo
            self.zapri()
            raise
        except Exception as e:  # noqa: BLE001
            self.zapri()
            raise NapakaPortala("napaka", str(e)) from e

    def zapri(self) -> None:
        with self._zapri_zaklep:
            seja, self.seja = self.seja, ""
            fd, self.fd = self.fd, -1
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if seja:
            Gio, _ = _gio()
            try:
                self.vodilo.call_sync(PORTAL, seja, SEJA, "Close", None, None, Gio.DBusCallFlags.NONE, 2000, None)
            except Exception:  # noqa: BLE001 - seja je ze zaprta (uporabnik je deljenje ustavil v sistemu)
                pass

    @property
    def odprta(self) -> bool:
        return bool(self.seja)

    # ------------------------------------------------------------------ vnos (RemoteDesktop)
    def _obvesti(self, metoda: str, podpis: str, argumenti: tuple) -> bool:
        """Dogodek brez cakanja na odgovor (NO_REPLY_EXPECTED): vrstni red ohrani povezava, nit vnosa ne caka."""
        if not (self.vnos and self.seja):
            return False
        Gio, _ = _gio()
        try:
            self.vodilo.call(PORTAL, POT, RD, metoda, _v(podpis, (self.seja, {}) + argumenti), None,
                             Gio.DBusCallFlags.NONE, -1, None, None)
            return True
        except Exception:  # noqa: BLE001
            return False

    def premik(self, dx: float, dy: float) -> bool:
        return self._obvesti("NotifyPointerMotion", "(oa{sv}dd)", (float(dx), float(dy)))

    def premik_na(self, x: float, y: float) -> bool:
        """x, y v logicnih tockah toka (velikost iz odpri())."""
        return self._obvesti("NotifyPointerMotionAbsolute", "(oa{sv}udd)",
                             (int(self.tok.get("vozlisce", 0)), float(x), float(y)))

    def gumb(self, koda: int, dol: bool) -> bool:
        return self._obvesti("NotifyPointerButton", "(oa{sv}iu)", (int(koda), 1 if dol else 0))

    def kolesce(self, korakov: int, vodoravno: bool = False) -> bool:
        return self._obvesti("NotifyPointerAxisDiscrete", "(oa{sv}ui)", (1 if vodoravno else 0, int(korakov)))

    def tipka(self, keysym: int, dol: bool) -> bool:
        return self._obvesti("NotifyKeyboardKeysym", "(oa{sv}iu)", (int(keysym), 1 if dol else 0))


# ---------------------------------------------------------------------------------------------- vnos
_IMENA_KRMILK = {"ctrl": "Control_L", "alt": "Alt_L", "shift": "Shift_L", "super": "Super_L"}


def keysym(ime: str) -> int:
    """Ime tipke X (Return, ctrl, XF86AudioPlay ...) -> keysym; 0, ce ga ni."""
    ime = _IMENA_KRMILK.get(ime.lower(), ime)
    try:
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        k = int(Gdk.keyval_from_name(ime))
        return 0 if k in (0, 0xFFFFFF) else k
    except Exception:  # noqa: BLE001
        return 0


def keysym_znaka(znak: str) -> int:
    try:
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        return int(Gdk.unicode_to_keyval(ord(znak)))
    except Exception:  # noqa: BLE001
        return 0


class VnosPortal(Vnos):
    """Vnos s televizorja na Waylandu: isti seznam dovoljenega in varovala kot Vnos (xdotool), dogodki pa gredo v
    portal RemoteDesktop. Ukaze, ki jih Vnos sestavi za xdotool, tu prevedemo v klice portala."""

    def __init__(self, seja: Seja) -> None:
        super().__init__(display=None, xdotool="")
        self.seja = seja

    @property
    def mozno(self) -> bool:
        return bool(self.seja is not None and self.seja.vnos and self.seja.odprta)

    def _pritisni(self, imena: List[str]) -> bool:
        kode = [keysym(i) for i in imena]
        if not all(kode):
            return False
        for k in kode:
            self.seja.tipka(k, True)
        for k in reversed(kode):
            self.seja.tipka(k, False)
        return True

    def _pozeni(self, argumenti) -> bool:
        if not self.mozno or not argumenti:
            return False
        a = [x for x in argumenti if x not in ("--clearmodifiers", "--")]
        ukaz = a[0]
        ok = False
        if ukaz == "key" and len(a) >= 2:
            ok = self._pritisni(a[-1].split("+"))
        elif ukaz in ("keydown", "keyup") and len(a) >= 2:
            k = keysym(a[-1])
            ok = bool(k) and self.seja.tipka(k, ukaz == "keydown")
        elif ukaz == "type" and len(a) >= 2:
            besedilo = a[-1]
            kode = [keysym_znaka(z) for z in besedilo]
            if kode and all(kode):
                for k in kode:
                    self.seja.tipka(k, True)
                    self.seja.tipka(k, False)
                ok = True
        elif ukaz == "mousemove_relative" and len(a) == 3:
            ok = self.seja.premik(float(a[1]), float(a[2]))
        elif ukaz == "mousemove" and len(a) == 3:
            ok = self.seja.premik_na(float(a[1]), float(a[2]))
        elif ukaz in ("mousedown", "mouseup") and len(a) == 2 and a[1] in GUMBI_EVDEV:
            ok = self.seja.gumb(GUMBI_EVDEV[a[1]], ukaz == "mousedown")
        elif ukaz == "click":
            ponovi = int(a[a.index("--repeat") + 1]) if "--repeat" in a else 1
            gumb = a[-1]
            if gumb in ("4", "5"):            # kolesce: 4 gor, 5 dol (v Waylandu pozitivno = navzdol)
                ok = self.seja.kolesce(ponovi if gumb == "5" else -ponovi)
            elif gumb in GUMBI_EVDEV:
                for _ in range(max(1, min(3, ponovi))):
                    self.seja.gumb(GUMBI_EVDEV[gumb], True)
                    self.seja.gumb(GUMBI_EVDEV[gumb], False)
                ok = True
        if ok:
            self.stevec += 1
        return ok


# ---------------------------------------------------------------------------------------------- slike
def ukaz_zajema(seja: Seja, sirina: int, visina: int, fps: int, ffmpeg_ukaz: List[str]) -> Tuple[List[str], dict]:
    """Ukaz za link_zaslon: core/zajem_pipewire.py (PipeWire -> surove slike) poda slike ffmpegu, ki jih kodira.

    Vrne (ukaz, dodatno za Popen): fd PipeWire podedujeta samo ta proces in ffmpeg ga ne vidi."""
    koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ukaz = [sys.executable, "-m", "core.zajem_pipewire", "--fd", str(seja.fd),
            "--vozlisce", str(seja.tok["vozlisce"]), "--sirina", str(int(sirina)), "--visina", str(int(visina)),
            "--fps", str(int(fps)), "--"] + list(ffmpeg_ukaz)
    return ukaz, {"pass_fds": (seja.fd,), "cwd": koren}


def vhod_ffmpeg(sirina: int, visina: int, fps: int) -> List[str]:
    """Vhod ffmpeg za surove slike BGRx iz core/zajem_pipewire.py (namesto x11grab)."""
    return ["-f", "rawvideo", "-pix_fmt", "bgr0", "-video_size", "%dx%d" % (sirina, visina),
            "-framerate", str(int(fps)), "-i", "pipe:0"]


class SlikePipewire:
    """Okvirji zaslona iz PipeWire v tem procesu (deljenje zaslona prek Huba, ~4 slike/s): zajemi() kot x11.Povezava."""

    def __init__(self, seja: Seja, najvec_px: int = 1280) -> None:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)
        self.Gst = Gst
        s, v = seja.tok["sirina"], seja.tok["visina"]
        m = min(1.0, float(najvec_px) / max(s, v))
        self.sirina, self.visina = max(2, int(s * m) // 2 * 2), max(2, int(v * m) // 2 * 2)
        opis = ("pipewiresrc fd=%d path=%d do-timestamp=true keepalive-time=500 ! videoconvert ! videoscale ! "
                "video/x-raw,format=RGB,width=%d,height=%d ! appsink name=izhod max-buffers=1 drop=true sync=false"
                % (seja.fd, seja.tok["vozlisce"], self.sirina, self.visina))
        self.cev = Gst.parse_launch(opis)
        self.izhod = self.cev.get_by_name("izhod")
        self.cev.set_state(Gst.State.PLAYING)

    def zajemi(self):
        vzorec = self.izhod.emit("try-pull-sample", 2 * self.Gst.SECOND)
        if vzorec is None:
            return None
        medpomnilnik = vzorec.get_buffer()
        struktura = vzorec.get_caps().get_structure(0)
        s, v = struktura.get_value("width"), struktura.get_value("height")
        ok, mapa = medpomnilnik.map(self.Gst.MapFlags.READ)
        if not ok:
            return None
        try:
            podatki = bytes(mapa.data)
        finally:
            medpomnilnik.unmap(mapa)
        vrstica = len(podatki) // v if v else 0
        if vrstica != s * 3:            # GStreamer poravna vrstice na 4 bajte
            podatki = b"".join(podatki[i * vrstica:i * vrstica + s * 3] for i in range(v))
        return s, v, podatki

    def zapri(self) -> None:
        try:
            self.cev.set_state(self.Gst.State.NULL)
        except Exception:  # noqa: BLE001
            pass


SPOROCILA = {
    "ni_portala": "To namizje ne ponuja deljenja zaslona (portal ScreenCast ni na voljo).",
    "zavrnjeno": "Deljenje zaslona je bilo na računalniku zavrnjeno.",
    "rok": "Na računalniku nihče ni potrdil deljenja zaslona. Potrdi ga enkrat za računalnikom - potem se zapomni.",
    "napaka": "Zaslona ni bilo mogoče zajeti.",
}


__all__ = ["Seja", "VnosPortal", "SlikePipewire", "NapakaPortala", "zmoznosti", "gstreamer_pipewire",
           "ukaz_zajema", "vhod_ffmpeg", "SPOROCILA"]

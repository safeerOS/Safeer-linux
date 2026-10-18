"""Brezglavi Wayland za preizkuse (sway z ozadjem headless, risanje pixman) - Safeer na Waylandu brez zaslona.

Zakaj sway: ima delno merilo (1,25/1,5/1,75), vec izhodov, priklop in odklop izhoda med delovanjem (create_output,
unplug) in grim za posnetke - vse, kar GNOME na Ubuntu 24.04 uporabniku ponudi, a brez grafične kartice. Vse tece v
svoji mapi (mktemp -d) z lastnim XDG_RUNTIME_DIR in lastnim vodilom D-Bus; ob koncu se procesi koncajo po PID in mapa
pobrise (AGENTS.md: noben preizkus ne pusti procesov).

    with Sway(merilo=1.5) as s:
        p = s.zazeni([sys.executable, "safeer_os.py"])
        s.pocakaj_okno("io.github.memelandfaner.SafeerOS")
        s.posnetek("/pot/posnetek.png")
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from typing import List, Optional

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


#: Spremenljivke, ki jih drugi preizkusi v istem procesu nastavijo (os_lupina.pripravi: QT_QPA_PLATFORM, preizkusi
#: QML: offscreen) - zivi program na Waylandu mora izbrati sam, kot ob pravem zagonu.
TUJE = ("DISPLAY", "WAYLAND_DISPLAY", "SWAYSOCK", "DBUS_SESSION_BUS_ADDRESS", "QT_QPA_PLATFORM", "GDK_BACKEND",
        "QT_XCB_GL_INTEGRATION", "QT_QPA_PLATFORMTHEME", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "SAFEER_LUPINA",
        "SAFEER_OS_BREZ_OKEN")


def cisto_okolje() -> dict:
    """os.environ brez zaslona, vodila in izbir ozadja Qt/GDK (TUJE)."""
    return {k: v for k, v in os.environ.items() if k not in TUJE}


def na_voljo() -> bool:
    return bool(shutil.which("sway") and shutil.which("swaymsg") and shutil.which("dbus-daemon"))


def _potomci(pid: int) -> List[int]:
    izid = []
    try:
        for nit in os.listdir("/proc/%d/task" % pid):
            with open("/proc/%d/task/%s/children" % (pid, nit)) as f:
                for otrok in f.read().split():
                    izid += _potomci(int(otrok)) + [int(otrok)]
    except OSError:
        pass
    return izid


def koncaj_drevo(pid: int, rok_s: float = 3.0) -> None:
    """Konca proces in vse potomce (po PID, ne pkill -f): najprej SIGTERM, po roku SIGKILL."""
    vsi = _potomci(pid) + [pid]
    for p in vsi:
        try:
            os.kill(p, signal.SIGTERM)
        except OSError:
            pass
    konec = time.monotonic() + rok_s
    while time.monotonic() < konec and any(_zivi(p) for p in vsi):
        time.sleep(0.1)
    for p in vsi:
        if _zivi(p):
            try:
                os.kill(p, signal.SIGKILL)
            except OSError:
                pass
    for p in vsi:
        try:
            os.waitpid(p, os.WNOHANG)
        except OSError:
            pass


def _zivi(pid: int) -> bool:
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().split(") ", 1)[1][0] != "Z"
    except (OSError, IndexError):
        return False


class Sway:
    def __init__(self, merilo: float = 1.0, sirina: int = 1920, visina: int = 1080, xwayland: bool = False,
                 pipewire: bool = False) -> None:
        self.merilo, self.sirina, self.visina, self.xwayland = merilo, sirina, visina, xwayland
        #: PipeWire, WirePlumber in xdg-desktop-portal-wlr (ScreenCast brez vprasanja: chooser_type=none)
        self.pipewire = pipewire
        self.mapa = ""
        self.okolje: dict = {}
        self._procesi: List[subprocess.Popen] = []
        self._programov = 0
        self._sway: Optional[subprocess.Popen] = None
        self._dbus: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------ zagon in konec
    def __enter__(self) -> "Sway":
        self.mapa = tempfile.mkdtemp(prefix="safeer-wayland-")
        run = os.path.join(self.mapa, "run")
        os.makedirs(run, mode=0o700)
        for m in ("cfg", "cache", "data"):
            os.makedirs(os.path.join(self.mapa, m))
        konf = os.path.join(self.mapa, "sway.conf")
        with open(konf, "w") as f:
            f.write("output HEADLESS-1 resolution %dx%d position 0 0 scale %s\n" % (self.sirina, self.visina, self.merilo))
            # Brez »output * bg«: swaybg bi tekel kot locen proces zunaj nasega drevesa procesov.
            f.write("xwayland %s\nfocus_follows_mouse no\n" % ("enable" if self.xwayland else "disable"))
        osnova = cisto_okolje()
        osnova.update({"XDG_RUNTIME_DIR": run, "WLR_BACKENDS": "headless", "WLR_RENDERER": "pixman",
                       "WLR_LIBINPUT_NO_DEVICES": "1"})
        try:
            self._dbus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=osnova, text=True)
            naslov = self._dbus.stdout.readline().strip()
            dnevnik = open(os.path.join(self.mapa, "sway.log"), "w")
            self._sway = subprocess.Popen(["sway", "-c", konf], env=dict(osnova, DBUS_SESSION_BUS_ADDRESS=naslov),
                                          stdout=dnevnik, stderr=dnevnik, stdin=subprocess.DEVNULL)
            dnevnik.close()
            konec = time.monotonic() + 10
            vticnica = ipc = ""
            while time.monotonic() < konec and self._sway.poll() is None:
                imena = os.listdir(run)
                vticnica = next((i for i in imena if i.startswith("wayland-") and not i.endswith(".lock")), "")
                ipc = next((i for i in imena if i.startswith("sway-ipc.")), "")
                if vticnica and ipc:
                    break
                time.sleep(0.05)
            if not (vticnica and ipc):
                raise RuntimeError("sway se ni zagnal")
            self.okolje = {k: v for k, v in osnova.items() if not k.startswith("WLR_")}
            self.okolje.update({"WAYLAND_DISPLAY": vticnica, "SWAYSOCK": os.path.join(run, ipc),
                                "XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "sway",
                                "DBUS_SESSION_BUS_ADDRESS": naslov,
                                "XDG_CONFIG_HOME": os.path.join(self.mapa, "cfg"),
                                "XDG_CACHE_HOME": os.path.join(self.mapa, "cache"),
                                "XDG_DATA_HOME": os.path.join(self.mapa, "data"),
                                "LIBGL_ALWAYS_SOFTWARE": "1", "SAFEER_OS_BREZ_FLATPAKA": "1"})
            self._pocakaj_izhod()
            if self.pipewire:
                self._zazeni_pipewire()
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def _zazeni_pipewire(self) -> None:
        """PipeWire in WirePlumber (otroka tega preizkusa) ter okolje aktivacije D-Bus za portal wlr."""
        mapa = os.path.join(self.okolje["XDG_CONFIG_HOME"], "xdg-desktop-portal-wlr")
        os.makedirs(mapa)
        with open(os.path.join(mapa, "config"), "w") as f:
            f.write("[screencast]\nchooser_type=none\noutput_name=HEADLESS-1\n")
        for program in ("pipewire", "wireplumber"):
            dnevnik = open(os.path.join(self.mapa, program + ".log"), "w")
            self._procesi.append(subprocess.Popen([program], env=self.okolje, stdout=dnevnik, stderr=dnevnik,
                                                  stdin=subprocess.DEVNULL))
            dnevnik.close()
            time.sleep(0.5)
        spremenljivke = ["%s=%s" % (k, self.okolje[k]) for k in ("WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP",
                                                                  "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR", "SWAYSOCK")]
        subprocess.run(["dbus-update-activation-environment"] + spremenljivke, env=self.okolje, timeout=10,
                       capture_output=True)
        konec = time.monotonic() + 10
        while time.monotonic() < konec:
            r = subprocess.run(["pw-cli", "info", "0"], env=self.okolje, capture_output=True, timeout=5)
            if r.returncode == 0:
                return
            time.sleep(0.2)
        raise RuntimeError("PipeWire se ni zagnal")

    def _pocakaj_izhod(self) -> None:
        konec = time.monotonic() + 5
        while time.monotonic() < konec:
            try:
                if self.izhodi():
                    return
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.1)

    def __exit__(self, *_a) -> None:
        for p in reversed(self._procesi):
            koncaj_drevo(p.pid)
        if self._sway is not None:
            koncaj_drevo(self._sway.pid)
        if self._dbus is not None:
            koncaj_drevo(self._dbus.pid)
        for p in self._procesi + [x for x in (self._sway, self._dbus) if x is not None]:
            try:
                p.wait(timeout=2)
            except Exception:  # noqa: BLE001
                pass
            for tok in (p.stdout, p.stderr):
                if tok is not None:
                    tok.close()
        if self.mapa:
            shutil.rmtree(self.mapa, ignore_errors=True)

    # ------------------------------------------------------------------ programi in sway
    def zazeni(self, ukaz: List[str], **okolje) -> subprocess.Popen:
        dnevnik = open(os.path.join(self.mapa, "program-%d.log" % self._programov), "w")
        self._programov += 1
        p = subprocess.Popen(ukaz, env=dict(self.okolje, **okolje), cwd=KOREN, stdout=dnevnik, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL)
        dnevnik.close()
        self._procesi.append(p)
        return p

    def dnevnik(self, i: int = 0) -> str:
        try:
            with open(os.path.join(self.mapa, "program-%d.log" % i), errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def msg(self, *argumenti: str, vrsta: str = "command"):
        r = subprocess.run(["swaymsg", "-r", "-t", vrsta] + list(argumenti), capture_output=True, text=True,
                           timeout=10, env=self.okolje)
        return json.loads(r.stdout or "null")

    def izhodi(self) -> list:
        return [i for i in (self.msg(vrsta="get_outputs") or []) if i.get("active")]

    def okna(self) -> list:
        """Vrhnja okna: [{app_id, name, shell, rect, fullscreen, output}]."""
        izid = []

        def hodi(n, izhod=""):
            if n.get("type") == "output":
                izhod = n.get("name", "")
            if n.get("type") in ("con", "floating_con") and (n.get("app_id") or n.get("window_properties")):
                izid.append({"app_id": n.get("app_id") or "", "name": n.get("name") or "", "shell": n.get("shell"),
                             "rect": n.get("rect"), "fullscreen": n.get("fullscreen_mode", 0), "output": izhod})
            for o in (n.get("nodes") or []) + (n.get("floating_nodes") or []):
                hodi(o, izhod)
        hodi(self.msg(vrsta="get_tree") or {})
        return izid

    def pocakaj_okno(self, app_id: str, rok_s: float = 40.0) -> Optional[dict]:
        konec = time.monotonic() + rok_s
        while time.monotonic() < konec:
            for o in self.okna():
                if o["app_id"] == app_id:
                    return o
            time.sleep(0.3)
        return None

    def posnetek(self, pot: str, izhod: str = "") -> bool:
        if not shutil.which("grim"):
            return False
        return subprocess.run(["grim"] + (["-o", izhod] if izhod else []) + [pot], env=self.okolje,
                              capture_output=True, timeout=20).returncode == 0

    def dodaj_izhod(self) -> str:
        pred = {i["name"] for i in self.izhodi()}
        self.msg("create_output")
        konec = time.monotonic() + 5
        while time.monotonic() < konec:
            novi = {i["name"] for i in self.izhodi()} - pred
            if novi:
                return novi.pop()
            time.sleep(0.1)
        return ""

    def odstrani_izhod(self, ime: str) -> None:
        self.msg("output", ime, "unplug")


def gnome_na_voljo() -> bool:
    return bool(shutil.which("mutter") and shutil.which("pipewire") and shutil.which("wireplumber")
                and shutil.which("dbus-daemon")
                and os.path.exists("/usr/share/dbus-1/services/org.freedesktop.impl.portal.desktop.gnome.service"))


class Mutter:
    """Brezglavi GNOME 46 (mutter --headless, kot Ubuntu 24.04) s PipeWire in portalom GNOME.

    posnetek() in tipke() gresta mimo portala, neposredno v mutter (org.gnome.Mutter.ScreenCast/RemoteDesktop) -
    kot preizkusni robot, ki v dialogu portala klikne »Deli«, ker za brezglavim racunalnikom ni nikogar."""

    def __init__(self, sirina: int = 1920, visina: int = 1080) -> None:
        self.sirina, self.visina = sirina, visina
        self.mapa = ""
        self.okolje: dict = {}
        self._procesi: List[subprocess.Popen] = []
        self._programov = 0
        self._dbus: Optional[subprocess.Popen] = None
        self._rd = ""

    def __enter__(self) -> "Mutter":
        self.mapa = tempfile.mkdtemp(prefix="safeer-gnome-")
        run = os.path.join(self.mapa, "run")
        os.makedirs(run, mode=0o700)
        for m in ("cfg", "cache", "data"):
            os.makedirs(os.path.join(self.mapa, m))
        osnova = cisto_okolje()
        osnova.update({"XDG_RUNTIME_DIR": run, "XDG_CURRENT_DESKTOP": "GNOME", "XDG_SESSION_TYPE": "wayland",
                       "XDG_CONFIG_HOME": os.path.join(self.mapa, "cfg"),
                       "XDG_CACHE_HOME": os.path.join(self.mapa, "cache"),
                       "XDG_DATA_HOME": os.path.join(self.mapa, "data"), "LIBGL_ALWAYS_SOFTWARE": "1",
                       "SAFEER_OS_BREZ_FLATPAKA": "1"})
        try:
            self._dbus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=osnova, text=True)
            osnova["DBUS_SESSION_BUS_ADDRESS"] = self._dbus.stdout.readline().strip()
            self.okolje = dict(osnova, WAYLAND_DISPLAY="wayland-safeer")
            for ukaz in (["pipewire"], ["wireplumber"],
                         ["mutter", "--wayland", "--headless", "--no-x11", "--wayland-display=wayland-safeer",
                          "--virtual-monitor", "%dx%d" % (self.sirina, self.visina)]):
                self._ozadje(ukaz, osnova)
                time.sleep(0.5)
            konec = time.monotonic() + 15
            while time.monotonic() < konec and not os.path.exists(os.path.join(run, "wayland-safeer")):
                time.sleep(0.1)
            subprocess.run(["dbus-update-activation-environment"] + ["%s=%s" % (k, self.okolje[k]) for k in (
                "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "XDG_CONFIG_HOME")],
                env=self.okolje, capture_output=True, timeout=10)
            if not self._ime_na_vodilu("org.gnome.Mutter.ScreenCast", 15):
                raise RuntimeError("mutter se ni zagnal")
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def _ozadje(self, ukaz: List[str], okolje: dict) -> None:
        dnevnik = open(os.path.join(self.mapa, os.path.basename(ukaz[0]) + ".log"), "w")
        self._procesi.append(subprocess.Popen(ukaz, env=okolje, stdout=dnevnik, stderr=dnevnik,
                                              stdin=subprocess.DEVNULL))
        dnevnik.close()

    def __exit__(self, *_a) -> None:
        povezava, self._povezava = getattr(self, "_povezava", None), None
        if povezava is not None:
            try:
                povezava.close_sync(None)
            except Exception:  # noqa: BLE001
                pass
        for p in reversed(self._procesi):
            koncaj_drevo(p.pid)
        if self._dbus is not None:
            koncaj_drevo(self._dbus.pid)
        for p in self._procesi + ([self._dbus] if self._dbus is not None else []):
            try:
                p.wait(timeout=2)
            except Exception:  # noqa: BLE001
                pass
            if p.stdout is not None:
                p.stdout.close()
        if self.mapa:
            shutil.rmtree(self.mapa, ignore_errors=True)

    # ------------------------------------------------------------------ vodilo
    def _gdbus(self, *argumenti: str, rok: int = 10) -> str:
        r = subprocess.run(["gdbus", "call", "--session"] + list(argumenti), capture_output=True, text=True,
                           timeout=rok, env=self.okolje)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip())
        return r.stdout.strip()

    def _ime_na_vodilu(self, ime: str, rok_s: float) -> bool:
        konec = time.monotonic() + rok_s
        while time.monotonic() < konec:
            try:
                if ime in self._gdbus("--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus",
                                      "--method", "org.freedesktop.DBus.ListNames"):
                    return True
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.2)
        return False

    def zazeni(self, ukaz: List[str], **okolje) -> subprocess.Popen:
        dnevnik = open(os.path.join(self.mapa, "program-%d.log" % self._programov), "w")
        self._programov += 1
        p = subprocess.Popen(ukaz, env=dict(self.okolje, **okolje), cwd=KOREN, stdout=dnevnik, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL)
        dnevnik.close()
        self._procesi.append(p)
        return p

    def dnevnik(self, i: int = 0) -> str:
        try:
            with open(os.path.join(self.mapa, "program-%d.log" % i), errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def gsettings(self, *argumenti: str) -> str:
        """gsettings v tej seji (dconf v zacasni mapi - nastavitve racunalnika ostanejo nedotaknjene)."""
        r = subprocess.run(["gsettings"] + list(argumenti), capture_output=True, text=True, timeout=10, env=self.okolje)
        return r.stdout.strip()

    # ------------------------------------------------------------------ robot: tipke in posnetek mimo portala
    def _vodilo(self):
        """Lastna povezava tega preizkusa z vodilom seje: seja RemoteDesktop v mutterju zivi, dokler zivi povezava."""
        if getattr(self, "_povezava", None) is None:
            from gi.repository import Gio
            self._povezava = Gio.DBusConnection.new_for_address_sync(
                self.okolje["DBUS_SESSION_BUS_ADDRESS"],
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, None)
        return self._povezava

    def _rd_klic(self, pot: str, metoda: str, argumenti=None, vrne: str = ""):
        from gi.repository import Gio, GLib
        vmesnik = "org.gnome.Mutter.RemoteDesktop" + (".Session" if pot != "/org/gnome/Mutter/RemoteDesktop" else "")
        return self._vodilo().call_sync("org.gnome.Mutter.RemoteDesktop", pot, vmesnik, metoda, argumenti,
                                        GLib.VariantType(vrne) if vrne else None, Gio.DBusCallFlags.NONE, 5000, None)

    def tipke(self, *keysymi: int, zamik_s: float = 0.15) -> None:
        """Pritisne tipke (keysym) prek org.gnome.Mutter.RemoteDesktop - kot uporabnik za tipkovnico."""
        from gi.repository import GLib
        if not self._rd:
            self._rd = self._rd_klic("/org/gnome/Mutter/RemoteDesktop", "CreateSession", None, "(o)").unpack()[0]
            self._rd_klic(self._rd, "Start")
        for k in keysymi:
            for dol in (True, False):
                self._rd_klic(self._rd, "NotifyKeyboardKeysym", GLib.Variant("(ub)", (int(k), dol)))
            time.sleep(zamik_s)

    def posnetek(self, pot: str) -> bool:
        """PNG zaslona prek org.gnome.Mutter.ScreenCast (RecordMonitor) in GStreamer (pipewiresrc, en kader)."""
        koda = r'''
import sys, gi
gi.require_version("Gst", "1.0")
from gi.repository import Gio, GLib, Gst
Gst.init(None)
v = Gio.bus_get_sync(Gio.BusType.SESSION, None)
def klic(pot, vm, m, a=None, vrne=None):
    return v.call_sync("org.gnome.Mutter.ScreenCast", pot, vm, m, a, GLib.VariantType(vrne) if vrne else None,
                       Gio.DBusCallFlags.NONE, 5000, None)
s = klic("/org/gnome/Mutter/ScreenCast", "org.gnome.Mutter.ScreenCast", "CreateSession",
         GLib.Variant("(a{sv})", ({},)), "(o)").unpack()[0]
t = klic(s, "org.gnome.Mutter.ScreenCast.Session", "RecordMonitor",
         GLib.Variant("(sa{sv})", ("", {"cursor-mode": GLib.Variant("u", 1)})), "(o)").unpack()[0]
izid = {}
v.signal_subscribe(None, "org.gnome.Mutter.ScreenCast.Stream", "PipeWireStreamAdded", t, None, 0,
                   lambda *a: izid.setdefault("vozlisce", a[5].unpack()[0]))
klic(s, "org.gnome.Mutter.ScreenCast.Session", "Start")
ctx = GLib.MainContext.default()
import time
k = time.monotonic() + 10
while "vozlisce" not in izid and time.monotonic() < k:
    ctx.iteration(False); time.sleep(0.02)
cev = Gst.parse_launch("pipewiresrc path=%d num-buffers=3 ! videoconvert ! pngenc snapshot=true ! filesink location=%s"
                       % (izid["vozlisce"], sys.argv[1]))
cev.set_state(Gst.State.PLAYING)
s2 = cev.get_bus().timed_pop_filtered(15 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
cev.set_state(Gst.State.NULL)
klic(s, "org.gnome.Mutter.ScreenCast.Session", "Stop")
sys.exit(0 if s2 is not None and s2.type == Gst.MessageType.EOS else 1)
'''
        import sys as _sys
        r = subprocess.run([_sys.executable, "-c", koda, pot], env=self.okolje, capture_output=True, timeout=40)
        return r.returncode == 0

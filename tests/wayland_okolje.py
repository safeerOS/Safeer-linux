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
    def __init__(self, merilo: float = 1.0, sirina: int = 1920, visina: int = 1080, xwayland: bool = False) -> None:
        self.merilo, self.sirina, self.visina, self.xwayland = merilo, sirina, visina, xwayland
        self.mapa = ""
        self.okolje: dict = {}
        self._procesi: List[subprocess.Popen] = []
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
        osnova = {k: v for k, v in os.environ.items()
                  if k not in ("DISPLAY", "WAYLAND_DISPLAY", "SWAYSOCK", "DBUS_SESSION_BUS_ADDRESS")}
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
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

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
        dnevnik = open(os.path.join(self.mapa, "program-%d.log" % len(self._procesi)), "w")
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

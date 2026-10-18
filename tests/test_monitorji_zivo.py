"""Vec monitorjev na X11 (Linux Mint): namizje QML Safeer OS (--delovna) sledi primarnemu monitorju, ko se monitor
med delovanjem priklopi ali odklopi - in Safeer OS pri tem ne pade.

Xvfb 2560x1024 z navideznima monitorjema RandR 1.5 (xrandr --setmonitor/--delmonitor, Qt xcb jih vidi kot zaslone).
Izmerjeno 18. 10. 2026: zacetek 2560x1024 na 0,0; LEVI primarni -> 1280x1024 na 0,0; odklop LEVI -> 1280x1024 na
1280,0 (DESNI); proces tece naprej."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOREN, "tests"))

POTREBNO = ("Xvfb", "xvfb-run", "xrandr", "xwininfo", "dbus-run-session")

SKRIPTA = r'''
import os, subprocess, sys, time
sys.path.insert(0, os.path.join(sys.argv[1], "tests"))
from wayland_okolje import koncaj_drevo
def geo():
    r = subprocess.run(["xwininfo", "-name", "Safeer OS namizje"], capture_output=True, text=True)
    v = {}
    for vrstica in r.stdout.splitlines():
        vrstica = vrstica.strip()
        for k in ("Absolute upper-left X", "Absolute upper-left Y", "Width", "Height"):
            if vrstica.startswith(k + ":"):
                v[k] = int(vrstica.split(":")[1])
    return (v.get("Absolute upper-left X"), v.get("Absolute upper-left Y"), v.get("Width"), v.get("Height"))
def pocakaj(pricakovano, rok=20):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        g = geo()
        if g == pricakovano:
            return g
        time.sleep(0.5)
    return geo()
os_ = subprocess.Popen(["dbus-run-session", "--", sys.executable, "safeer_os.py", "--delovna"], cwd=sys.argv[1],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    print("ZACETEK", pocakaj((0, 0, 2560, 1024), 60), flush=True)
    subprocess.run(["xrandr", "--setmonitor", "LEVI", "1280/340x1024/270+0+0", "none"], check=True)
    subprocess.run(["xrandr", "--setmonitor", "DESNI", "1280/340x1024/270+1280+0", "none"], check=True)
    print("DVA", pocakaj((0, 0, 1280, 1024)), flush=True)
    subprocess.run(["xrandr", "--delmonitor", "LEVI"], check=True)
    print("ODKLOP", pocakaj((1280, 0, 1280, 1024)), flush=True)
    print("TECE", os_.poll() is None, flush=True)
finally:
    koncaj_drevo(os_.pid)
'''


@unittest.skipUnless(all(shutil.which(p) for p in POTREBNO), "brez Xvfb, xrandr, xwininfo ali dbus-run-session")
class PriklopMonitorja(unittest.TestCase):
    def test_namizje_sledi_primarnemu_monitorju(self):
        with tempfile.TemporaryDirectory() as d:
            okolje = {k: v for k, v in os.environ.items()
                      if k not in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "DISPLAY", "DBUS_SESSION_BUS_ADDRESS")}
            okolje.update({"XDG_CONFIG_HOME": os.path.join(d, "c"), "XDG_CACHE_HOME": os.path.join(d, "k"),
                           "XDG_DATA_HOME": os.path.join(d, "p"), "SAFEER_OS_BREZ_FLATPAKA": "1"})
            r = subprocess.run(["xvfb-run", "-a", "-s", "-screen 0 2560x1024x24", sys.executable, "-c", SKRIPTA, KOREN],
                               capture_output=True, text=True, timeout=150, env=okolje)
        izid = {v.split()[0]: v.split(" ", 1)[1] for v in r.stdout.splitlines() if v[:1].isupper()}
        print(izid)
        self.assertEqual(izid.get("ZACETEK"), "(0, 0, 2560, 1024)", r.stderr[-1500:])
        self.assertEqual(izid.get("DVA"), "(0, 0, 1280, 1024)")
        self.assertEqual(izid.get("ODKLOP"), "(1280, 0, 1280, 1024)")
        self.assertEqual(izid.get("TECE"), "True", "odklop monitorja ne podre Safeer OS")


if __name__ == "__main__":
    unittest.main()

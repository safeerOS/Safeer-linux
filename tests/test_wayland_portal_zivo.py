"""Zivi preizkus na brezglavem GNOME 46 (mutter + xdg-desktop-portal-gnome, kot Ubuntu 24.04): deljenje zaslona in
vnos v Safeer Linku prek portala (core/portal_zaslon.py, core/zajem_pipewire.py).

Robot (tests/wayland_okolje.Mutter.tipke) v dialogu portala vklopi »Allow Remote Interaction« in pritisne »Share«,
kot bi uporabnik za racunalnikom. Druga seja se mora odpreti BREZ dialoga (zeton obnovitve). Vnos s »televizorja«
(VnosPortal) mora vpisati besedilo v pravo okno GTK4 na tem zaslonu. Brez mutterja/PipeWire se preizkus preskoci.
Izmerjeno 18. 10. 2026 (vsebnik Ubuntu 24.04, mutter 46.2): glej izpis preizkusa (-s). Vnos mora biti po vrsti:
brez cakanja na odgovor portala je »Safeer 127« prislo kot »Saer 127ef«."""

import os
import shutil
import sys
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOREN, "tests"))

import wayland_okolje  # noqa: E402

TAB, PRESLEDEK = 0xFF09, 0x20
#: Dialog portala GNOME 46 (»Remote Desktop«): Tab, Tab = »Allow Remote Interaction«, presledek ga vklopi,
#: trikrat Tab do »Share« in presledek (izmerjeno z posnetki 18. 10. 2026).
POTRDI_Z_VNOSOM = (TAB, TAB, PRESLEDEK, TAB, TAB, TAB, PRESLEDEK)

OKNO = r'''
import gi, sys
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
def aktiviraj(app):
    w = Gtk.ApplicationWindow(application=app, title="Preizkus vnosa")
    e = Gtk.Entry()
    def konec(_e):
        print("VNOS:" + e.get_text(), flush=True)
        app.quit()
    e.connect("activate", konec)
    w.set_child(e)
    w.fullscreen()
    w.present()
    e.grab_focus()
a = Gtk.Application(application_id="org.safeer.PreizkusVnosa")
a.connect("activate", aktiviraj)
a.run([])
'''

SEJA = r'''
import os, subprocess, sys, time
sys.path.insert(0, os.getcwd())
from core import portal_zaslon as pz
pot = os.path.join(os.environ["XDG_CONFIG_HOME"], "safeer-control", "portal-zaslon.json")
t = time.monotonic()
s = pz.Seja(vnos=True, pot=pot, rok_s=60)
tok = s.odpri()
print("PRVA_MS", int((time.monotonic() - t) * 1000), "TOK", tok["sirina"], tok["visina"], "VNOS", s.vnos, flush=True)
# H.264 kot za televizor: zajem_pipewire (PipeWire -> BGRx) | ffmpeg x264
ff = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"] + pz.vhod_ffmpeg(1280, 720, 30) + [
      "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-f", "h264", "-"]
ukaz, dodatno = pz.ukaz_zajema(s, 1280, 720, 30, ff)
p = subprocess.Popen(ukaz, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **dodatno)
os.set_blocking(p.stdout.fileno(), False)
zacetek, prebrano, prvi, podatki = time.monotonic(), 0, None, b""
while time.monotonic() - zacetek < 3:
    try:
        k = p.stdout.read(65536)
    except BlockingIOError:
        k = None
    if k:
        prebrano += len(k)
        podatki += k[:64] if len(podatki) < 64 else b""
        prvi = prvi or time.monotonic() - zacetek
    time.sleep(0.01)
p.terminate()
p.wait(5)
print("H264", prebrano, "PRVI_MS", int((prvi or 9) * 1000), "NAL", podatki[:4] == b"\x00\x00\x00\x01" or podatki[:3] == b"\x00\x00\x01",
      "KODA", p.returncode, flush=True)
sl = pz.SlikePipewire(s, 1280)
z = sl.zajemi()
sl.zapri()
svetlih = sum(1 for i in range(0, len(z[2]), 3 * 101) if max(z[2][i:i + 3]) > 16) if z else 0
print("JPEG_OKVIR", z[0] if z else 0, z[1] if z else 0, "SVETLIH", svetlih, flush=True)
v = pz.VnosPortal(s)
v.izvedi({"vrsta": "tocka", "x": tok["sirina"] // 2, "y": tok["visina"] // 2})
v.izvedi({"vrsta": "klik", "gumb": "levi"})
time.sleep(0.3)
v.izvedi({"vrsta": "besedilo", "besedilo": "Safeer 127"})
time.sleep(0.3)
v.izvedi({"vrsta": "tipka", "tipka": "ok"})
print("VNOSOV", v.stevec, flush=True)
t = time.monotonic()
for i in range(100):
    v.izvedi({"vrsta": "premik", "dx": 1 if i % 2 else -1, "dy": 0})
print("PREMIK_MS", round((time.monotonic() - t) * 10, 2), flush=True)     # povprecje na dogodek
time.sleep(1)
s.zapri()
t = time.monotonic()
s2 = pz.Seja(vnos=True, pot=pot, rok_s=8)
s2.odpri()
print("DRUGA_MS", int((time.monotonic() - t) * 1000), "VNOS", s2.vnos, flush=True)
s2.zapri()
'''


@unittest.skipUnless(wayland_okolje.gnome_na_voljo() and shutil.which("ffmpeg"), "brez mutterja, PipeWire ali ffmpeg")
class PortalGnome(unittest.TestCase):
    def test_zajem_vnos_in_obnovitev(self):
        with wayland_okolje.Mutter() as m:
            okno = m.zazeni([sys.executable, "-c", OKNO])
            time.sleep(3)
            seja = m.zazeni([sys.executable, "-c", SEJA])
            time.sleep(4)                       # dialog portala
            m.tipke(*POTRDI_Z_VNOSOM)
            seja.wait(60)
            okno.wait(10)
            izpis, vnos = m.dnevnik(1), m.dnevnik(0)
            print(izpis, vnos)
            vrstice = {v.split()[0]: v.split() for v in izpis.splitlines() if v and v.split()[0].isupper()}
            self.assertIn("PRVA_MS", vrstice, izpis)
            self.assertEqual(vrstice["PRVA_MS"][3:5], ["1920", "1080"])
            self.assertEqual(vrstice["PRVA_MS"][6], "True", "robot je vklopil oddaljeno upravljanje")
            self.assertGreater(int(vrstice["H264"][1]), 1000, "ffmpeg je dobil slike iz PipeWire")
            self.assertEqual(vrstice["H264"][5], "True", "tok H.264 se zacne z enoto NAL")
            self.assertEqual(vrstice["JPEG_OKVIR"][1:3], ["1280", "720"])
            self.assertGreater(int(vrstice["JPEG_OKVIR"][4]), 100, "okvir ni crn (ozadje GNOME)")
            self.assertIn("VNOS:Safeer 127", vnos, "besedilo s televizorja je prislo v okno GTK4 (po vrsti)")
            self.assertLess(float(vrstice["PREMIK_MS"][1]), 20.0, "dogodek miske prek portala pod 20 ms")
            self.assertIn("DRUGA_MS", vrstice, "druga seja brez dialoga (zeton obnovitve)")
            self.assertEqual(vrstice["DRUGA_MS"][3], "True")


if __name__ == "__main__":
    unittest.main()

"""Za tests/test_kanali_programi.py: proces kot Safeer OS vstavi okno laznega programa (WM_CLASS iz argumenta) v svoje
okno GTK4, izpise »vstavljeno« in caka, da ga preizkus ubije (SIGKILL - kot padec Safeer OS)."""
import os
import sys
import time

sys.path.insert(0, sys.argv[2])
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from core import vstavi_okno  # noqa: E402


def main() -> int:
    Gtk.init()
    x = vstavi_okno.X11()
    okno = Gtk.Window()
    okno.set_default_size(600, 400)
    mesto = Gtk.DrawingArea()
    mesto.set_hexpand(True)
    mesto.set_vexpand(True)
    okno.set_child(mesto)
    okno.present()
    k = GLib.MainContext.default()
    rok = time.monotonic() + 10
    while time.monotonic() < rok and not (mesto.get_mapped() and x.najdi([sys.argv[1]])):
        k.iteration(False)
        time.sleep(0.01)
    tuje = x.najdi([sys.argv[1]])
    v = vstavi_okno.VstavljenoOkno(Gtk, GLib, mesto)
    v.vstavi(tuje)
    nase = vstavi_okno.Mesto(Gtk, mesto).xid_starsa()
    rok = time.monotonic() + 10
    while time.monotonic() < rok and x.stars(tuje) != nase:
        k.iteration(False)
        time.sleep(0.01)
    print("vstavljeno" if x.stars(tuje) == nase else "ni", tuje, flush=True)
    while True:
        k.iteration(True)
    return os.EX_OK


if __name__ == "__main__":
    sys.exit(main())

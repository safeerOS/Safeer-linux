"""Lazni namizni program za preizkuse vstavljanja okna (tests/test_kanali_programi.py): okno GTK4 z vnosnim poljem in
razredom okna (WM_CLASS) »safeer-lazni-program«. Natipkano besedilo izpise na standardni izhod (vrstica »vnos:...«),
naslov okna je »(N) Lazni program«, kjer je N iz argumenta - za branje stevila neprebranih iz naslova okna."""
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

GLib.set_prgname("safeer-lazni-program")
GLib.set_application_name("Lazni program")


def main() -> int:
    Gtk.init()
    okno = Gtk.Window(title="(%s) Lazni program" % (sys.argv[1] if len(sys.argv) > 1 else "0"))
    okno.set_default_size(400, 300)
    vnos = Gtk.Entry()
    vnos.connect("changed", lambda v: print("vnos:" + v.get_text(), flush=True))
    okno.set_child(vnos)
    okno.connect("close-request", lambda *_: (zanka.quit(), False)[1])
    okno.present()
    vnos.grab_focus()
    print("pripravljen", flush=True)
    zanka = GLib.MainLoop()
    zanka.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Ucni tek za PGO WebKitGTK: v oknu GTK4 z WebKitom 6.0 pozene Speedometer 3.1 in pocaka na rezultat.

Uporaba (v instrumentirani gradnji Flatpaka, glej packaging/webkit/pgo.py in linux-packages.yml, posel webkit-pgo-ucenje):
  python3 pgo_trening.py URL [NAJDLJE_MINUT]
URL je lokalna kopija Speedometra 3.1 z ?startAutomatically&iterationCount=N (brez omrezja). Ob koncu se okno zapre in
WebKit pomoznim procesom poslje SIGTERM, ob katerem zapisejo profil (.profraw, pot iz LLVM_PROFILE_FILE).
Izhod 0 = Speedometer je izpisal veljaven rezultat, 1 = napaka ali cas je potekel.
"""
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib, Gtk, WebKit  # noqa: E402

URL = sys.argv[1]
ROK = time.monotonic() + 60 * float(sys.argv[2] if len(sys.argv) > 2 else 90)
STANJE = "(() => { const s = document.getElementById('summary'); const r = document.getElementById('result-number');" \
         " return (s ? s.className : '') + '|' + (r ? r.textContent : ''); })()"
izid = {"koda": 1, "konec": False}


def ob_zagonu(app):
    okno = Gtk.ApplicationWindow(application=app, default_width=1280, default_height=900, title="Safeer PGO")
    pogled = WebKit.WebView()
    okno.set_child(pogled)
    okno.present()
    pogled.load_uri(URL)
    zacetek = time.monotonic()

    def konec():
        if izid["konec"]:
            return
        izid["konec"] = True
        # Spletni proces dobi SIGTERM (z ENABLE_LLVM_PROFILE_GENERATION, ProcessLauncherGLib.cpp) in zapise profil;
        # glavna zanka tece se 3 s, da se to zgodi pred zaprtjem okna.
        pogled.terminate_web_process()
        GLib.timeout_add_seconds(3, lambda: (okno.destroy(), app.quit(), GLib.SOURCE_REMOVE)[-1])

    def ob_stanju(_pogled, rezultat):
        try:
            razred, stevilo = pogled.evaluate_javascript_finish(rezultat).to_string().split("|", 1)
        except GLib.Error as napaka:
            print("pgo_trening: branje stanja:", napaka.message, flush=True)
            return
        # #summary ima razred "valid" ze v index.html; rezultat je koncan, ko je #result-number izpolnjen
        # (stevilo ali "Error", resources/main.mjs).
        if stevilo.strip() and not izid["konec"]:
            print("pgo_trening: Speedometer 3.1 %s %s po %.0f s" % (razred, stevilo, time.monotonic() - zacetek), flush=True)
            izid["koda"] = 0 if razred == "valid" and stevilo.strip() != "Error" else 1
            konec()
            return

    def preveri():
        if time.monotonic() > ROK:
            print("pgo_trening: cas je potekel", flush=True)
            konec()
            return GLib.SOURCE_REMOVE
        if izid["konec"]:
            return GLib.SOURCE_REMOVE
        pogled.evaluate_javascript(STANJE, -1, None, None, None, ob_stanju)
        return GLib.SOURCE_CONTINUE

    GLib.timeout_add_seconds(10, preveri)


# Flatpak dovoli programu na seji D-Bus samo ime programa in njegova podimena: drugo ime (prej ...SafeerPgo) je
# registracijo zavrnilo in app.run() se je koncal brez okna (CI 38709018765). NON_UNIQUE: ime ni potrebno.
app = Gtk.Application(application_id="io.github.memelandfaner.SafeerBrowser.Pgo", flags=Gio.ApplicationFlags.NON_UNIQUE)
app.connect("activate", ob_zagonu)
koda = app.run([])
if koda:
    print("pgo_trening: Gtk.Application.run je vrnil %d" % koda, flush=True)
# Omrezni proces se konca, ko se zapre povezava s tem procesom, in profil zapise ob izhodu (atexit); na to pocaka posel CI.
sys.exit(izid["koda"])

"""Omrezni proces WebKita se konca ravno, ko se stran zacne nalagati (lastnik 20. 10. 2026: lupa -> Google ->
»Strani trenutno ni mogoce odpreti«; v sled.log »WebKit encountered an internal error ... internallyFailedLoad«).
Spletni proces zahteve ne preda nikamor, WebKit javi WebKitErrorDomain 300; NetworkErrorHandler jo mora sam ponoviti.
Brez tekme (14. 11. 2026): omrezni proces je med nalaganjem zamrznjen (SIGSTOP) in nato koncan (SIGKILL), zato zahteva
pred koncem ne pride do streznika (pred=0), ponovitev pa pride enkrat (po=1). Prej SIGTERM tik pred load_uri: polni tek na
testnem PC je 10 od 10 poskusov zgresil (spletni proces je konec opazil prej in zahtevo dal novemu omreznemu procesu).
Tece v svojem procesu (konca omrezni proces), v pravem WebKitGTK 6.0 na Xvfb; brez zaslona ali WebKita se preskoci."""
import os
import subprocess
import sys
import textwrap
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OTROK = textwrap.dedent(r'''
    import os, signal, socket, sys, threading, time
    sys.path.insert(0, sys.argv[1])
    import gi
    gi.require_version("Gtk", "4.0"); gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit
    from core.network_errors import NetworkErrorHandler
    from core.os_splet import omrezni_procesi
    v = socket.socket(); v.bind(("127.0.0.1", 0)); v.listen(16); vrata = v.getsockname()[1]
    zahteve = []
    def streznik():
        while True:
            c, _ = v.accept()
            with c:
                d = c.recv(65536)
                if not d:
                    continue
                zahteve.append(d.split(b" ")[1].decode("ascii", "replace"))
                t = b"<title>ok</title>ok"
                c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: %d\r\n\r\n" % len(t) + t)
    threading.Thread(target=streznik, daemon=True).start()
    Gtk.init()
    p = WebKit.WebView(network_session=WebKit.NetworkSession.new_ephemeral())
    o = Gtk.Window(); o.set_child(p); o.present()
    naslovi = []
    p.connect("notify::title", lambda w, _s: naslovi.append(w.get_title() or ""))
    zanka = GLib.MainLoop()
    st = {"faza": "prva", "poskus": 0, "notranja": 0, "zacetek": None, "pidi": [], "pot": "", "pred": -1, "rez": None}
    def napaka(_w, _d, _u, e):
        if e.domain == "WebKitErrorDomain" and e.code == 300:
            st["notranja"] += 1
        return False
    p.connect("load-failed", napaka)       # PRED NetworkErrorHandler: ta vrne True in ustavi signal; ta samo opazuje
    def zacetek(_w, dogodek):
        if dogodek == WebKit.LoadEvent.STARTED and st["zacetek"] is None:
            st["zacetek"] = time.monotonic()
    p.connect("load-changed", zacetek)
    NetworkErrorHandler(p, "sl")
    def ubij(sig):
        for pid in st["pidi"]:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
    def poskus():
        st["poskus"] += 1; naslovi.clear(); st["zacetek"] = None
        st["pidi"] = sorted(omrezni_procesi())
        if not st["pidi"]:
            print("IZID brez omreznega procesa", flush=True); zanka.quit(); return
        # Omrezni proces zamrznemo PRED nalaganjem: spletni proces mu zahtevo preda, ta je ne poslje nikamor, nato se
        # konca. Prej (SIGTERM tik pred load_uri) je bila tekma - spletni proces je konec vcasih opazil prej in zahtevo
        # dal novemu omreznemu procesu brez napake (testni PC 14. 11. 2026, polni tek: 10 od 10 poskusov brez napake).
        ubij(signal.SIGSTOP)
        st["rez"] = threading.Timer(5.0, ubij, (signal.SIGKILL,)); st["rez"].start()   # ce bi UI cakal omrezni proces
        st["pot"] = "/druga%d" % st["poskus"]
        p.load_uri("http://127.0.0.1:%d%s" % (vrata, st["pot"]))
        st["faza"] = "zamrznjen"
    def korak():
        if st["faza"] == "prva" and "ok" in naslovi and not p.is_loading():
            poskus()
        elif st["faza"] == "zamrznjen" and st["zacetek"] is not None and time.monotonic() - st["zacetek"] > 0.5:
            st["pred"] = zahteve.count(st["pot"])       # zamrznjen omrezni proces zahteve ne more poslati
            ubij(signal.SIGKILL); st["rez"].cancel()
            st["faza"] = "ponovitev"
        elif st["faza"] == "ponovitev" and "ok" in naslovi and not p.is_loading():
            if st["notranja"] or st["poskus"] >= 3:
                print("IZID ok notranja=%s poskusov=%d pred=%d po=%d" % (bool(st["notranja"]), st["poskus"], st["pred"],
                      zahteve.count(st["pot"])), flush=True)
                zanka.quit(); return False
            poskus()
        return True
    GLib.timeout_add(20, korak)
    GLib.timeout_add(30000, lambda: (print("IZID rok", st, naslovi, flush=True), zanka.quit(), False)[2])
    p.load_uri("http://127.0.0.1:%d/prva" % vrata)
    zanka.run()
''')


def _webkit():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import WebKit  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(_webkit(), "potrebuje WebKitGTK")
class OmrezniProcesKoncan(unittest.TestCase):
    def test_nalaganje_ob_koncu_omreznega_procesa_se_ponovi(self):
        r = subprocess.run([sys.executable, "-c", OTROK, KOREN], capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, GTK_A11Y="none"))
        izpis = r.stdout + r.stderr
        # Preizkus mora res zadeti primer lastnika (notranja napaka WebKita), sicer ne dokazuje nicesar; po njej se je
        # stran nalozila sama, ze v prvem poskusu, zahteva pa je do streznika prisla samo enkrat (ponovitev).
        self.assertIn("IZID ok notranja=True poskusov=1 pred=0 po=1", r.stdout, izpis[-3000:])


if __name__ == "__main__":
    unittest.main()

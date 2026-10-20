"""Omrezni proces WebKita se konca ravno, ko se stran zacne nalagati (lastnik 20. 10. 2026: lupa -> Google ->
»Strani trenutno ni mogoce odpreti«; v sled.log »WebKit encountered an internal error ... internallyFailedLoad«).
Spletni proces zahteve ne preda nikamor, WebKit javi WebKitErrorDomain 300; NetworkErrorHandler jo mora sam ponoviti.
Tece v svojem procesu (konca omrezni proces), v pravem WebKitGTK 6.0 na Xvfb; brez zaslona ali WebKita se preskoci."""
import os
import subprocess
import sys
import textwrap
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OTROK = textwrap.dedent(r'''
    import os, socket, sys, threading
    sys.path.insert(0, sys.argv[1])
    import gi
    gi.require_version("Gtk", "4.0"); gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit
    from core.network_errors import NetworkErrorHandler
    from core.os_splet import omrezni_procesi
    v = socket.socket(); v.bind(("127.0.0.1", 0)); v.listen(16); vrata = v.getsockname()[1]
    def streznik():
        while True:
            c, _ = v.accept()
            with c:
                if not c.recv(65536):
                    continue
                t = b"<title>ok</title>ok"
                c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: %d\r\n\r\n" % len(t) + t)
    threading.Thread(target=streznik, daemon=True).start()
    Gtk.init()
    p = WebKit.WebView(network_session=WebKit.NetworkSession.new_ephemeral())
    o = Gtk.Window(); o.set_child(p); o.present()
    naslovi = []
    p.connect("notify::title", lambda w, _s: naslovi.append(w.get_title() or ""))
    zanka = GLib.MainLoop(); stanje = {"faza": 0, "poskus": 0, "notranja": False}
    def napaka(_w, _d, _u, e):
        if e.domain == "WebKitErrorDomain" and e.code == 300:
            stanje["notranja"] = True
        return False
    p.connect("load-failed", napaka)       # PRED NetworkErrorHandler: ta vrne True in ustavi signal; ta samo opazuje
    NetworkErrorHandler(p, "sl")
    def korak():
        if stanje["faza"] == 0 and "ok" in naslovi:
            # Konec omreznega procesa ravno ob nalaganju: tekma - ponovimo, dokler je WebKit ne javi (najvec 10x).
            if stanje["notranja"] or stanje["poskus"] >= 10:
                stanje["faza"] = 1
                return True
            stanje["poskus"] += 1; naslovi.clear()
            for pid in omrezni_procesi():
                os.kill(pid, 15)
            p.load_uri("http://127.0.0.1:%d/druga%d" % (vrata, stanje["poskus"]))
        elif stanje["faza"] == 1:
            print("IZID ok notranja=%s poskusov=%d" % (stanje["notranja"], stanje["poskus"]), flush=True)
            zanka.quit(); return False
        return True
    GLib.timeout_add(50, korak)
    GLib.timeout_add(20000, lambda: (print("IZID rok", naslovi, flush=True), zanka.quit(), False)[2])
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
        # stran nalozila sama (faza 0 caka na »ok« po vsakem koncu omreznega procesa).
        self.assertIn("IZID ok notranja=True", r.stdout, izpis[-3000:])


if __name__ == "__main__":
    unittest.main()

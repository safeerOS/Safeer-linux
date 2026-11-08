#!/usr/bin/env python3
"""Ali nas WebKitGTK (safeer-webkit) uveljavi HSTS za podvire in okvirje (8. 11. 2026).

NetworkDataTaskSoup::shouldAllowHSTSProtocolUpgrade() vrne isTopLevelNavigation() && !m_isBlockingCookies,
Applova omilitev 2 pa omeji samo podvire do BLOKIRANIH domen (pricakovano ||). Preizkus pokaze, ali se
http:// podvir do gostitelja z znano politiko HSTS nadgradi na https.

Samo zanka (::1 / 127.0.0.1). Politiko HSTS vnaprej zapisemo v hsts-storage.sqlite (libsoup HSTSEnforcerDB),
zato TLS ni potreben. Vsaka vrsta zahteve ima svoja vrata: streznik zapise HTTP (ni nadgrajeno) ali TLS
(nadgrajeno - prvi bajt 0x16 = TLS ClientHello).
Uporaba: tools/nas_webkit.sh xvfb-run -a python3 tests/hsts_podviri_preizkus.py <zacasna mapa>
Zadnja vrstica izpisa: JSON {vrsta: [HTTP|TLS|PISKOTEK V CISTEM HTTP, ...]} (tests/test_webkit_hsts_podviri.py).
"""
import json, os, socket, socketserver, sys, threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
gi.require_version("Soup", "3.0")
from gi.repository import GLib, Gtk, Soup, WebKit

mapa = sys.argv[1]
podatki = os.path.join(mapa, "podatki")
predpomnilnik = os.path.join(mapa, "predpomnilnik")
os.makedirs(podatki, exist_ok=True)
os.makedirs(os.path.join(predpomnilnik, "HSTS"), exist_ok=True)   # WebKit bere predpomnilnik/HSTS/hsts-storage.sqlite (izmerjeno 8. 11.)

# Politika HSTS za hsts.localhost (brez poddomen), kot da jo je streznik poslal prej prek HTTPS.
baza = Soup.HSTSEnforcerDB.new(os.path.join(predpomnilnik, "HSTS", "hsts-storage.sqlite"))
baza.set_policy(Soup.HSTSPolicy.new("hsts.localhost", 3600, False))
print("POLITIKA", [p.get_domain() for p in baza.get_policies(False)], flush=True)
del baza

izid = {}          # vrsta -> set("HTTP"/"TLS")
zaklep = threading.Lock()


def strezi(vrsta, telo, tip):
    class H(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                prvi = self.request.recv(1, socket.MSG_PEEK)
            except OSError:
                return
            with zaklep:
                izid.setdefault(vrsta, set()).add("TLS" if prvi == b"\x16" else "HTTP")
            if prvi == b"\x16":
                return
            zahteva = self.request.recv(65536).decode("latin-1")
            if "seja=preizkus" in zahteva:
                with zaklep:
                    izid.setdefault(vrsta, set()).add("PISKOTEK V CISTEM HTTP")
            glava = ("HTTP/1.1 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % (tip, len(telo))).encode()
            self.request.sendall(glava + telo)

    class S6(socketserver.ThreadingTCPServer):
        address_family = socket.AF_INET6
        allow_reuse_address = True
        daemon_threads = True

    class S4(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    s6 = S6(("::1", 0), H)
    vrata = s6.server_address[1]
    s4 = S4(("127.0.0.1", vrata), H)
    for s in (s6, s4):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    return vrata


GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")
v_zgoraj = strezi("navigacija", b"<html>zgoraj</html>", "text/html")
v_slika = strezi("slika", GIF, "image/gif")
v_skripta = strezi("skripta", b"document.title='skripta';", "application/javascript")
v_okvir = strezi("okvir", b"<html>okvir</html>", "text/html")
stran = ("<html><body>stran"
         "<img src='http://hsts.localhost:%d/s.gif'>"
         "<script src='http://hsts.localhost:%d/s.js'></script>"
         "<iframe src='http://hsts.localhost:%d/o'></iframe></body></html>" % (v_slika, v_skripta, v_okvir)).encode()
v_stran = strezi("stran (www.hsts.localhost)", stran, "text/html")

seja = WebKit.NetworkSession.new(podatki, predpomnilnik)
print("HSTS mapa", seja.get_website_data_manager().get_base_cache_directory(), flush=True)
app = Gtk.Application(application_id="si.safeer.preizkus.hsts")


def zazeni(a):
    okno = Gtk.ApplicationWindow(application=a)
    w = WebKit.WebView(network_session=seja)
    okno.set_child(w)
    okno.present()
    # Navaden (ne Secure) piskotek za hsts.localhost - HSTS naj prepreci, da gre po cistem HTTP.
    seja.get_cookie_manager().add_cookie(Soup.Cookie.new("seja", "preizkus", "hsts.localhost", "/", 3600), None, None, None)
    koraki = ["http://hsts.localhost:%d/" % v_zgoraj, "http://www.hsts.localhost:%d/" % v_stran]

    def naslednji():
        if koraki:
            u = koraki.pop(0)
            print("NALAGAM", u, flush=True)
            w.load_uri(u)
            GLib.timeout_add_seconds(6, naslednji)
        else:
            a.quit()
        return False

    naslednji()


app.connect("activate", zazeni)
app.run([])

print("REZULTAT (HTTP = ni nadgrajeno na https, TLS = nadgrajeno po HSTS):")
for vrsta in ("navigacija", "stran (www.hsts.localhost)", "slika", "skripta", "okvir"):
    print("  %-26s %s" % (vrsta, ",".join(sorted(izid.get(vrsta, {"brez zahteve"})))), flush=True)
print("JSON " + json.dumps({k: sorted(v) for k, v in izid.items()}), flush=True)

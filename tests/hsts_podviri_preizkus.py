#!/usr/bin/env python3
"""Ali nas WebKitGTK (safeer-webkit) uveljavi HSTS za podvire in okvirje (8. 11. 2026).

NetworkDataTaskSoup::shouldAllowHSTSProtocolUpgrade() je v 2.54.2 isTopLevelNavigation() && !m_isBlockingCookies,
Applova omilitev 2 pa omeji samo podvire do BLOKIRANIH domen (pricakovano ||). Preizkus pokaze, ali se
http:// podvir do gostitelja z znano politiko HSTS nadgradi na https, ali POST po nadgradnji ostane POST s
telesom (sinteticna preusmeritev 302 bi ga spremenila v GET brez telesa - slepi pregled 8. 11.) in kateri Origin
dobi streznik.

Samo zanka (::1 / 127.0.0.1). Politiko HSTS vnaprej zapisemo v <predpomnilnik>/HSTS/hsts-storage.sqlite (libsoup
HSTSEnforcerDB). Vsaka vrsta zahteve ima svoja vrata: streznik zapise HTTP (ni nadgrajeno) ali TLS (nadgrajeno -
prvi bajt 0x16 = TLS ClientHello); zahtevo TLS sprejme s samopodpisanim potrdilom (seja WebKita z IGNORE samo za
ta preizkus) in zapise metodo, telo in Origin.
Uporaba: tools/nas_webkit.sh xvfb-run -a python3 tests/hsts_podviri_preizkus.py <zacasna mapa>
Zadnja vrstica izpisa: JSON {vrsta: [...]} (tests/test_webkit_hsts_podviri.py).
"""
import json, os, socket, socketserver, ssl, subprocess, sys, threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
gi.require_version("Soup", "3.0")
from gi.repository import GLib, Gtk, Soup, WebKit

mapa = sys.argv[1]
podatki = os.path.join(mapa, "podatki")
predpomnilnik = os.path.join(mapa, "predpomnilnik")
os.makedirs(podatki, exist_ok=True)
os.makedirs(os.path.join(predpomnilnik, "HSTS"), exist_ok=True)   # WebKit bere <predpomnilnik>/HSTS/hsts-storage.sqlite (izmerjeno 8. 11.)

# Politika HSTS za hsts.localhost (brez poddomen), kot da jo je streznik poslal prej prek HTTPS.
baza = Soup.HSTSEnforcerDB.new(os.path.join(predpomnilnik, "HSTS", "hsts-storage.sqlite"))
baza.set_policy(Soup.HSTSPolicy.new("hsts.localhost", 3600, False))
print("POLITIKA", [p.get_domain() for p in baza.get_policies(False)], flush=True)
del baza

# Samopodpisano potrdilo za nadgrajene zahteve (samo ta preizkus).
potrdilo, kljuc = os.path.join(mapa, "p.pem"), os.path.join(mapa, "k.pem")
subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=hsts.localhost",
                "-keyout", kljuc, "-out", potrdilo], check=True, capture_output=True)
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.load_cert_chain(potrdilo, kljuc)

izid = {}          # vrsta -> set(...)
zaklep = threading.Lock()


def zapisi(vrsta, kaj):
    with zaklep:
        izid.setdefault(vrsta, set()).add(kaj)


def preberi_zahtevo(s):
    podatki_z = b""
    while b"\r\n\r\n" not in podatki_z and len(podatki_z) < 65536:
        k = s.recv(65536)
        if not k:
            break
        podatki_z += k
    glava, _, telo = podatki_z.partition(b"\r\n\r\n")
    vrstice = glava.decode("latin-1").split("\r\n")
    glave = {v.split(":", 1)[0].strip().lower(): v.split(":", 1)[1].strip() for v in vrstice[1:] if ":" in v}
    dolzina = int(glave.get("content-length", "0") or 0)
    while len(telo) < dolzina:
        k = s.recv(65536)
        if not k:
            break
        telo += k
    return vrstice[0].split(" ")[0] if vrstice and vrstice[0] else "", glave, telo


def strezi(vrsta, telo, tip):
    class H(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                prvi = self.request.recv(1, socket.MSG_PEEK)
            except OSError:
                return
            if not prvi:   # povezava brez podatkov (npr. vnaprejsnja povezava) ni zahteva - ne steje (CodeRabbit 8. 11.)
                return
            s = self.request
            if prvi == b"\x16":
                try:
                    s = tls.wrap_socket(self.request, server_side=True)
                except (ssl.SSLError, OSError):
                    zapisi(vrsta, "TLS (rokovanje ni uspelo)")
                    return
                zapisi(vrsta, "TLS")
            else:
                zapisi(vrsta, "HTTP")
            metoda, glave, prejeto = preberi_zahtevo(s)
            if "seja=preizkus" in glave.get("cookie", "") and prvi != b"\x16":
                zapisi(vrsta, "PISKOTEK V CISTEM HTTP")
            if vrsta.startswith("api"):
                zapisi(vrsta, "ORIGIN " + glave.get("origin", "(ni)"))
            if vrsta == "api":
                zapisi(vrsta, "METODA " + metoda)
                zapisi(vrsta, "TELO OK" if prejeto == b"telo-preizkusa" else "TELO %d B" % len(prejeto))
            dodatno = ""
            if vrsta.startswith("api"):
                dodatno = "Access-Control-Allow-Origin: %s\r\n" % glave.get("origin", "*")
            odgovor = ("HTTP/1.1 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\n%sConnection: close\r\n\r\n"
                       % (tip, len(telo), dodatno)).encode()
            try:
                s.sendall(odgovor + telo)
            except OSError:
                pass

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
v_skripta = strezi("skripta", b"window.skriptaNalozena=1;", "application/javascript")
v_okvir = strezi("okvir", b"<html>okvir</html>", "text/html")
v_api = strezi("api", b"ok", "text/plain")
v_api2 = strezi("api2 (redirect error)", b"ok", "text/plain")
stran = ("<html><body>stran"
         "<img src='http://hsts.localhost:%d/s.gif'>"
         "<script src='http://hsts.localhost:%d/s.js'></script>"
         "<iframe src='http://hsts.localhost:%d/o'></iframe>"
         # Medizvorni fetch (www.hsts.localhost -> hsts.localhost): POST s telesom in GET z redirect:'error'.
         # Nadgradnja HSTS ni preusmeritev (Fetch), zato oba uspeta, Origin pa ostane izvor strani.
         "<script>Promise.all(["
         "fetch('http://hsts.localhost:%d/api',{method:'POST',body:'telo-preizkusa',headers:{'Content-Type':'text/plain'}})"
         ".then(function(r){return r.text();}),"
         "fetch('http://hsts.localhost:%d/api2',{redirect:'error'}).then(function(r){return r.text();})])"
         ".then(function(t){document.title='FETCH:'+t.join('|');})"
         ".catch(function(e){document.title='FETCH-NAPAKA:'+e;});</script></body></html>"
         % (v_slika, v_skripta, v_okvir, v_api, v_api2)).encode()
v_stran = strezi("stran (www.hsts.localhost)", stran, "text/html")

seja = WebKit.NetworkSession.new(podatki, predpomnilnik)
seja.set_tls_errors_policy(WebKit.TLSErrorsPolicy.IGNORE)   # samo lazni strezniki tega preizkusa na zanki
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
            zapisi("fetch (naslov strani)", w.get_title() or "(brez)")
            a.quit()
        return False

    naslednji()


app.connect("activate", zazeni)
app.run([])

print("REZULTAT (HTTP = ni nadgrajeno na https, TLS = nadgrajeno po HSTS):")
for vrsta in ("navigacija", "stran (www.hsts.localhost)", "slika", "skripta", "okvir", "api", "api2 (redirect error)",
              "fetch (naslov strani)"):
    print("  %-26s %s" % (vrsta, ",".join(sorted(izid.get(vrsta, {"brez zahteve"})))), flush=True)
print("JSON " + json.dumps({k: sorted(v) for k, v in izid.items()} | {"_izvor_strani": "http://www.hsts.localhost:%d" % v_stran}), flush=True)

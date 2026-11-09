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
baza.set_policy(Soup.HSTSPolicy.new("hsts2.localhost", 3600, True))   # includeSubDomains: a.hsts2.localhost (9. 11.)
print("POLITIKA", [p.get_domain() for p in baza.get_policies(False)], flush=True)
del baza

# Potrdilo za nadgrajene zahteve. SAFEER_HSTS_POTRDILA = mapa s streznik.crt in streznik.key, podpisanima s preizkusnim
# CA, ki mu sistem zaupa (samo za *.localhost, nameConstraints) - takrat brez IGNORE in POST/Origin se preverita do konca.
# Brez nje samopodpisano potrdilo: libsoup ga pri gostitelju HSTS zavrne (RFC 6797 8.4), fetch zato ne stece do konca.
zaupano = os.environ.get("SAFEER_HSTS_POTRDILA", "")
if zaupano and os.path.isfile(os.path.join(zaupano, "streznik.crt")):
    potrdilo, kljuc = os.path.join(zaupano, "streznik.crt"), os.path.join(zaupano, "streznik.key")
else:
    zaupano = ""
    potrdilo, kljuc = os.path.join(mapa, "p.pem"), os.path.join(mapa, "k.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=hsts.localhost",
                    "-keyout", kljuc, "-out", potrdilo], check=True, capture_output=True)
print("POTRDILO", "zaupano" if zaupano else "samopodpisano", flush=True)
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
            if vrsta.startswith("api") or vrsta in CORS_VRSTE:
                # CORS dovoli izvor strani (tudi EventSource, 9. 11.: brez tega pade ze pri preverbi CORS, ne pri HSTS).
                dodatno = ("Access-Control-Allow-Origin: %s\r\nAccess-Control-Allow-Methods: GET, POST\r\n"
                           "Access-Control-Allow-Headers: content-type\r\n" % glave.get("origin", "*"))
            if vrsta in CORS_VRSTE:
                zapisi(vrsta, "METODA " + metoda)
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
# Razsirjeno (9. 11. 2026, lastnik: preveri cim vec, kar dopusca lokalno okolje): druge vrste zahtev do istega gostitelja.
# Slepi pregled 9. 11. 2026: viri v nacinu CORS, ki niso Fetch/XHR (preflight, crossorigin, modul, beacon JSON, izvor null).
CORS_VRSTE = ("eventsource", "preflight (fetch JSON)", "slika crossorigin", "modul skripta", "beacon JSON", "izvor null (sandbox)")
RAZSIRJENO = ("css", "pisava", "ozadje css", "video", "avdio", "xhr", "eventsource", "beacon", "websocket",
              "obrazec v okvirju", "predhodno nalaganje", "poddomena (includeSubDomains)", "eventsource (stanje v strani)") + CORS_VRSTE + ("stanja v strani",)
v_css = strezi("css", b"body{color:black}", "text/css")
v_pisava = strezi("pisava", b"x", "font/woff2")
v_ozadje = strezi("ozadje css", GIF, "image/gif")
v_video = strezi("video", b"x", "video/mp4")
v_avdio = strezi("avdio", b"x", "audio/mpeg")
v_xhr = strezi("xhr", b"ok", "text/plain")
v_es = strezi("eventsource", b"data: x\n\n", "text/event-stream")
v_beacon = strezi("beacon", b"", "text/plain")
v_ws = strezi("websocket", b"", "text/plain")
v_obrazec = strezi("obrazec v okvirju", b"<html>ok</html>", "text/html")
v_pred = strezi("predhodno nalaganje", b"x", "text/plain")
v_pod = strezi("poddomena (includeSubDomains)", GIF, "image/gif")
v_pf = strezi("preflight (fetch JSON)", b"ok", "text/plain")
v_ico = strezi("slika crossorigin", GIF, "image/gif")
v_mod = strezi("modul skripta", b"window.izidi.modul='nalozen';", "text/javascript")
v_bj = strezi("beacon JSON", b"", "text/plain")
v_nul = strezi("izvor null (sandbox)", b"ok", "text/plain")
stran = ("<html><body>stran"
         "<img src='http://hsts.localhost:%d/s.gif'>"
         "<script src='http://hsts.localhost:%d/s.js'></script>"
         "<iframe src='http://hsts.localhost:%d/o'></iframe>"
         "<link rel=stylesheet href='http://hsts.localhost:%d/s.css'>"
         "<style>@font-face{font-family:P;src:url(http://hsts.localhost:%d/p.woff2)}"
         "#p{font-family:P;background:url(http://hsts.localhost:%d/o.gif)}</style><div id=p>pisava</div>"
         "<video src='http://hsts.localhost:%d/v.mp4' preload=auto muted></video>"
         "<audio src='http://hsts.localhost:%d/a.mp3' preload=auto></audio>"
         "<link rel=prefetch href='http://hsts.localhost:%d/pred'>"
         "<img src='http://a.hsts2.localhost:%d/p.gif'>"
         "<iframe name=cilj style='display:none'></iframe>"
         "<form id=f method=post target=cilj action='http://hsts.localhost:%d/obrazec'><input name=x value=1></form>"
         "<script>try{var x=new XMLHttpRequest();x.open('GET','http://hsts.localhost:%d/x');x.send();}catch(e){}"
         "try{var es=new EventSource('http://hsts.localhost:%d/es');es.onopen=function(){window.esIzid='odprto';};"
         "es.onerror=function(){if(!window.esIzid)window.esIzid='napaka';};}catch(e){window.esIzid='izjema '+e;}"
         "try{navigator.sendBeacon('http://hsts.localhost:%d/b','b');}catch(e){}"
         "try{new WebSocket('ws://hsts.localhost:%d/ws');}catch(e){}"
         "try{document.getElementById('f').submit();}catch(e){}</script>"
         "<script>window.izidi={};"
         "fetch('http://hsts.localhost:%d/pf',{method:'POST',body:'{}',headers:{'Content-Type':'application/json'}})"
         ".then(function(r){return r.text();}).then(function(){izidi.preflight='ok';},function(e){izidi.preflight='napaka';});"
         "try{navigator.sendBeacon('http://hsts.localhost:%d/bj',new Blob(['{}'],{type:'application/json'}));}catch(e){}"
         "window.addEventListener('message',function(e){izidi.nul=String(e.data);});</script>"
         "<img crossorigin=anonymous src='http://hsts.localhost:%d/c.gif' onload=\"izidi.crossorigin='ok'\" onerror=\"izidi.crossorigin='napaka'\">"
         "<script type=module src='http://hsts.localhost:%d/m.js' onerror=\"izidi.modul='napaka'\"></script>"
         "<iframe sandbox=allow-scripts srcdoc=\"<script>fetch('http://hsts.localhost:%d/n').then(function(r){return r.text();})"
         ".then(function(){parent.postMessage('ok','*');},function(){parent.postMessage('napaka','*');});</script>\"></iframe>"
         # Medizvorni fetch (www.hsts.localhost -> hsts.localhost): POST s telesom in GET z redirect:'error'.
         # Nadgradnja HSTS ni preusmeritev (Fetch), zato oba uspeta, Origin pa ostane izvor strani.
         "<script>Promise.all(["
         "fetch('http://hsts.localhost:%d/api',{method:'POST',body:'telo-preizkusa',headers:{'Content-Type':'text/plain'}})"
         ".then(function(r){return r.text();}),"
         "fetch('http://hsts.localhost:%d/api2',{redirect:'error'}).then(function(r){return r.text();})])"
         ".then(function(t){document.title='FETCH:'+t.join('|');})"
         ".catch(function(e){document.title='FETCH-NAPAKA:'+e;});</script></body></html>"
         % (v_slika, v_skripta, v_okvir, v_css, v_pisava, v_ozadje, v_video, v_avdio, v_pred, v_pod, v_obrazec,
            v_xhr, v_es, v_beacon, v_ws, v_pf, v_bj, v_ico, v_mod, v_nul, v_api, v_api2)).encode()
v_stran = strezi("stran (www.hsts.localhost)", stran, "text/html")

seja = WebKit.NetworkSession.new(podatki, predpomnilnik)
if not zaupano:
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

            def po_branju(pogled, rezultat):
                try:
                    zapisi("eventsource (stanje v strani)", pogled.evaluate_javascript_finish(rezultat).to_string())
                except Exception as e:
                    zapisi("eventsource (stanje v strani)", "branje ni uspelo: %s" % e)
                a.quit()

            def po_branju2(pogled, rezultat):
                try:
                    zapisi("stanja v strani", pogled.evaluate_javascript_finish(rezultat).to_string())
                except Exception as e:
                    zapisi("stanja v strani", "branje ni uspelo: %s" % e)
                pogled.evaluate_javascript("String(window.esIzid||'ni dogodka')", -1, None, None, None, po_branju)

            w.evaluate_javascript("JSON.stringify(window.izidi||{})", -1, None, None, None, po_branju2)
        return False

    naslednji()


app.connect("activate", zazeni)
app.run([])

print("REZULTAT (HTTP = ni nadgrajeno na https, TLS = nadgrajeno po HSTS):")
for vrsta in ("navigacija", "stran (www.hsts.localhost)", "slika", "skripta", "okvir", "api", "api2 (redirect error)",
              "fetch (naslov strani)") + RAZSIRJENO:
    print("  %-26s %s" % (vrsta, ",".join(sorted(izid.get(vrsta, {"brez zahteve"})))), flush=True)
print("JSON " + json.dumps({k: sorted(v) for k, v in izid.items()} | {"_izvor_strani": "http://www.hsts.localhost:%d" % v_stran,
                                                                     "_zaupano": bool(zaupano)}), flush=True)
